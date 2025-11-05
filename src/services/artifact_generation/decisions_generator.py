"""Decisions extraction artifact generator for meetings and documents."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.services.artifact_generation.base import ArtifactGenerator, ArtifactResult
from src.services.llm.base import ChatMessage, LLMProvider


class DecisionsGenerator(ArtifactGenerator):
    """Generate decisions index artifacts from meetings and documents.

    Extracts:
        - Decision makers (who decided)
        - Decision details (what was decided)
        - Justifications (why it was decided)
        - Timestamps (when available, from meeting transcripts)

    Example:
        >>> from src.services.llm.factory import LLMProviderFactory
        >>> provider = LLMProviderFactory.create("anthropic", "claude-3-5-sonnet-20241022")
        >>> generator = DecisionsGenerator()
        >>> result = generator.generate(
        ...     context="Alice decided to use PostgreSQL because of better performance...",
        ...     llm_provider=provider,
        ...     source_type="meeting"
        ... )
        >>> print(result.content["decisions"][0]["decisor"])
        "Alice"
    """

    @property
    def artifact_kind(self) -> str:
        """Return artifact type identifier."""
        return "decisions_index"

    def generate(
        self, context: str, llm_provider: LLMProvider, **kwargs: Any
    ) -> ArtifactResult:
        """Generate decisions index artifact from context.

        Args:
            context: Input text content (meeting transcript, document text, etc.)
            llm_provider: LLM provider instance for generation
            **kwargs: Additional parameters:
                - source_type (str): Type of content ("meeting", "document", etc.)
                - metadata (dict): Additional context metadata
                - include_timestamps (bool): Whether to extract timestamps (default: True for meetings)

        Returns:
            ArtifactResult with decisions list and generation metadata

        Raises:
            ValueError: If context is empty
            RuntimeError: If LLM generation fails
            json.JSONDecodeError: If LLM response is not valid JSON
            KeyError: If required JSON fields are missing
        """
        if not context or not context.strip():
            raise ValueError("Context cannot be empty")

        # Extract optional parameters
        source_type = kwargs.get("source_type", "document")
        metadata = kwargs.get("metadata", {})

        # Load prompt template
        prompt_template = self._load_prompt_template()

        # Format prompt with variables
        prompt = prompt_template.format(
            content=context,
            source_type=source_type,
            metadata=self._format_metadata(metadata),
        )

        # Call LLM provider
        try:
            llm_result = llm_provider.generate(
                messages=[ChatMessage(role="user", content=prompt)],
                temperature=0.5,  # Lower temperature for more consistent extraction
                max_tokens=2500,
            )
        except Exception as e:
            raise RuntimeError(f"LLM generation failed: {e}") from e

        # Parse JSON response
        try:
            content_dict = json.loads(llm_result.content)
        except json.JSONDecodeError as e:
            raise json.JSONDecodeError(
                f"LLM response is not valid JSON: {llm_result.content[:200]}...",
                e.doc,
                e.pos,
            ) from e

        # Validate JSON structure
        self._validate_decisions_structure(content_dict)

        # Calculate cost
        cost = llm_provider.estimate_cost(
            llm_result.prompt_tokens, llm_result.completion_tokens
        )

        # Build result metadata
        result_metadata = {
            "provider": llm_result.provider,
            "model": llm_result.model,
            "prompt_tokens": llm_result.prompt_tokens,
            "completion_tokens": llm_result.completion_tokens,
            "total_tokens": llm_result.prompt_tokens + llm_result.completion_tokens,
            "cost": cost,
            "temperature": 0.5,
            "max_tokens": 2500,
            "prompt_template": "decisions_v1.txt",
            "source_type": source_type,
            "decision_count": len(content_dict["decisions"]),
        }

        return ArtifactResult(
            content=content_dict,
            metadata=result_metadata,
            schema_version="1.0",
            artifact_kind=self.artifact_kind,
        )

    def _load_prompt_template(self) -> str:
        """Load prompt template from file.

        Returns:
            Template string with placeholders

        Raises:
            FileNotFoundError: If template file doesn't exist
        """
        template_path = (
            Path(__file__).parent / "prompts" / "decisions_v1.txt"
        )

        if not template_path.exists():
            raise FileNotFoundError(
                f"Prompt template not found: {template_path}"
            )

        return template_path.read_text(encoding="utf-8")

    def _format_metadata(self, metadata: dict[str, Any]) -> str:
        """Format metadata dict as human-readable string.

        Args:
            metadata: Metadata dictionary

        Returns:
            Formatted metadata string
        """
        if not metadata:
            return "No additional metadata provided"

        lines = [f"{key}: {value}" for key, value in metadata.items()]
        return "\n".join(lines)

    def _validate_decisions_structure(self, content: dict[str, Any]) -> None:
        """Validate that decisions JSON has required structure.

        Args:
            content: Parsed JSON content

        Raises:
            KeyError: If required fields are missing
            ValueError: If field types are incorrect
        """
        # Check required top-level field
        if "decisions" not in content:
            raise KeyError(
                f"Missing required field 'decisions' in JSON. "
                f"Got fields: {list(content.keys())}"
            )

        # Validate decisions is a list
        if not isinstance(content["decisions"], list):
            raise ValueError(
                f"Field 'decisions' must be a list, got {type(content['decisions'])}"
            )

        # Validate each decision structure
        for idx, decision in enumerate(content["decisions"]):
            if not isinstance(decision, dict):
                raise ValueError(
                    f"Decision at index {idx} must be a dict, got {type(decision)}"
                )

            # Required fields for each decision
            required_decision_fields = ["decisor", "decision", "justification"]
            for field in required_decision_fields:
                if field not in decision:
                    raise KeyError(
                        f"Decision at index {idx} missing required field '{field}'. "
                        f"Got fields: {list(decision.keys())}"
                    )

            # Validate decision field types
            if not isinstance(decision["decisor"], str):
                raise ValueError(
                    f"Decision 'decisor' must be a string at index {idx}"
                )

            if not isinstance(decision["decision"], str):
                raise ValueError(
                    f"Decision 'decision' must be a string at index {idx}"
                )

            if not isinstance(decision["justification"], str):
                raise ValueError(
                    f"Decision 'justification' must be a string at index {idx}"
                )

            # Optional timestamp field
            if "timestamp" in decision and not isinstance(
                decision["timestamp"], str
            ):
                raise ValueError(
                    f"Decision 'timestamp' must be a string at index {idx}"
                )


# Auto-register this generator
ArtifactGenerator.register_generator("decisions_index", DecisionsGenerator)
