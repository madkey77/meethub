"""Summary artifact generator for meetings and documents."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.services.artifact_generation.base import ArtifactGenerator, ArtifactResult
from src.services.llm.base import ChatMessage, LLMProvider


class SummaryGenerator(ArtifactGenerator):
    """Generate summary artifacts with key points and participant identification.

    Extracts:
        - Concise summary (2-3 sentences)
        - Key points (3-7 items)
        - Participants (for meetings)

    Example:
        >>> from src.services.llm.factory import LLMProviderFactory
        >>> provider = LLMProviderFactory.create("openai", "gpt-4o")
        >>> generator = SummaryGenerator()
        >>> result = generator.generate(
        ...     context="Meeting transcript about Q4 planning...",
        ...     llm_provider=provider,
        ...     source_type="meeting",
        ...     metadata={"meeting_id": "123", "duration": "45 minutes"}
        ... )
        >>> print(result.content["summary"])
        "Team discussed Q4 objectives and resource allocation..."
    """

    @property
    def artifact_kind(self) -> str:
        """Return artifact type identifier."""
        return "summary"

    def generate(
        self, context: str, llm_provider: LLMProvider, **kwargs: Any
    ) -> ArtifactResult:
        """Generate summary artifact from context.

        Args:
            context: Input text content (meeting transcript, document text, etc.)
            llm_provider: LLM provider instance for generation
            **kwargs: Additional parameters:
                - source_type (str): Type of content ("meeting", "document", etc.)
                - metadata (dict): Additional context metadata

        Returns:
            ArtifactResult with summary content and generation metadata

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
                temperature=0.7,
                max_tokens=2000,
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
        self._validate_summary_structure(content_dict)

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
            "temperature": 0.7,
            "max_tokens": 2000,
            "prompt_template": "summary_v1.txt",
            "source_type": source_type,
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
            Path(__file__).parent / "prompts" / "summary_v1.txt"
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

    def _validate_summary_structure(self, content: dict[str, Any]) -> None:
        """Validate that summary JSON has required structure.

        Args:
            content: Parsed JSON content

        Raises:
            KeyError: If required fields are missing
            ValueError: If field types are incorrect
        """
        # Check required fields
        required_fields = ["summary", "key_points"]
        for field in required_fields:
            if field not in content:
                raise KeyError(
                    f"Missing required field '{field}' in summary JSON. "
                    f"Got fields: {list(content.keys())}"
                )

        # Validate field types
        if not isinstance(content["summary"], str):
            raise ValueError(
                f"Field 'summary' must be a string, got {type(content['summary'])}"
            )

        if not isinstance(content["key_points"], list):
            raise ValueError(
                f"Field 'key_points' must be a list, got {type(content['key_points'])}"
            )

        # Participants field is optional
        if "participants" in content and not isinstance(content["participants"], list):
            raise ValueError(
                f"Field 'participants' must be a list, got {type(content['participants'])}"
            )


# Auto-register this generator
ArtifactGenerator.register_generator("summary", SummaryGenerator)
