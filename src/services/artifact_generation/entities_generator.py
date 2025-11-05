"""Entities extraction artifact generator for meetings and documents."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.services.artifact_generation.base import ArtifactGenerator, ArtifactResult
from src.services.llm.base import ChatMessage, LLMProvider


class EntitiesGenerator(ArtifactGenerator):
    """Generate entities index artifacts (people, teams, organizations).

    Extracts:
        - People mentioned in content
        - Teams and groups
        - Organizations and companies
        - Context and mention counts for each entity

    Example:
        >>> from src.services.llm.factory import LLMProviderFactory
        >>> provider = LLMProviderFactory.create("openai", "gpt-4o")
        >>> generator = EntitiesGenerator()
        >>> result = generator.generate(
        ...     context="Alice from Engineering Team discussed the Acme project...",
        ...     llm_provider=provider,
        ...     source_type="meeting"
        ... )
        >>> print(len(result.content["entities"]))
        3  # Alice, Engineering Team, Acme
    """

    @property
    def artifact_kind(self) -> str:
        """Return artifact type identifier."""
        return "entities_index"

    def generate(
        self, context: str, llm_provider: LLMProvider, **kwargs: Any
    ) -> ArtifactResult:
        """Generate entities index artifact from context.

        Args:
            context: Input text content (meeting transcript, document text, etc.)
            llm_provider: LLM provider instance for generation
            **kwargs: Additional parameters:
                - source_type (str): Type of content ("meeting", "document", etc.)
                - metadata (dict): Additional context metadata

        Returns:
            ArtifactResult with entities list and generation metadata

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
        self._validate_entities_structure(content_dict)

        # Deduplicate entities (case-insensitive)
        content_dict["entities"] = self._deduplicate_entities(
            content_dict["entities"]
        )

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
            "max_tokens": 2000,
            "prompt_template": "entities_v1.txt",
            "source_type": source_type,
            "entity_count": len(content_dict["entities"]),
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
            Path(__file__).parent / "prompts" / "entities_v1.txt"
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

    def _validate_entities_structure(self, content: dict[str, Any]) -> None:
        """Validate that entities JSON has required structure.

        Args:
            content: Parsed JSON content

        Raises:
            KeyError: If required fields are missing
            ValueError: If field types are incorrect
        """
        # Check required top-level field
        if "entities" not in content:
            raise KeyError(
                f"Missing required field 'entities' in JSON. "
                f"Got fields: {list(content.keys())}"
            )

        # Validate entities is a list
        if not isinstance(content["entities"], list):
            raise ValueError(
                f"Field 'entities' must be a list, got {type(content['entities'])}"
            )

        # Validate each entity structure
        for idx, entity in enumerate(content["entities"]):
            if not isinstance(entity, dict):
                raise ValueError(
                    f"Entity at index {idx} must be a dict, got {type(entity)}"
                )

            required_entity_fields = ["name", "type", "context", "mentions"]
            for field in required_entity_fields:
                if field not in entity:
                    raise KeyError(
                        f"Entity at index {idx} missing required field '{field}'. "
                        f"Got fields: {list(entity.keys())}"
                    )

            # Validate entity field types
            if not isinstance(entity["name"], str):
                raise ValueError(
                    f"Entity 'name' must be a string at index {idx}"
                )

            if not isinstance(entity["type"], str):
                raise ValueError(
                    f"Entity 'type' must be a string at index {idx}"
                )

            if not isinstance(entity["context"], str):
                raise ValueError(
                    f"Entity 'context' must be a string at index {idx}"
                )

            if not isinstance(entity["mentions"], int):
                raise ValueError(
                    f"Entity 'mentions' must be an integer at index {idx}"
                )

    def _deduplicate_entities(
        self, entities: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Deduplicate entities using case-insensitive name matching.

        When duplicates are found, merge their mention counts and combine contexts.

        Args:
            entities: List of entity dictionaries

        Returns:
            Deduplicated list of entities
        """
        # Build a mapping of lowercase name -> entity
        entity_map: dict[str, dict[str, Any]] = {}

        for entity in entities:
            name_lower = entity["name"].lower()

            if name_lower in entity_map:
                # Merge with existing entity
                existing = entity_map[name_lower]
                existing["mentions"] += entity["mentions"]

                # Combine contexts if different
                if entity["context"] not in existing["context"]:
                    existing["context"] += f"; {entity['context']}"
            else:
                # Add new entity
                entity_map[name_lower] = entity.copy()

        # Return deduplicated list
        return list(entity_map.values())


# Auto-register this generator
ArtifactGenerator.register_generator("entities_index", EntitiesGenerator)
