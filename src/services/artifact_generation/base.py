"""Abstract interface for artifact generators with plugin registry."""

from __future__ import annotations

import abc
import importlib
import inspect
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Type

from src.services.llm.base import LLMProvider


@dataclass(slots=True)
class ArtifactResult:
    """Result payload returned by ArtifactGenerator.generate.

    Attributes:
        content: JSON-serializable artifact data (e.g., summary dict, entities list)
        metadata: Generation metadata (provider, model, tokens, cost, etc.)
        schema_version: Artifact schema version (e.g., "1.0")
        artifact_kind: Artifact type identifier (e.g., "summary", "decisions_index")

    Example:
        >>> result = ArtifactResult(
        ...     content={"summary": "Meeting about Q4 planning", "key_points": ["Budget review"]},
        ...     metadata={"provider": "openai", "model": "gpt-4o", "tokens": 1500, "cost": 0.03},
        ...     schema_version="1.0",
        ...     artifact_kind="summary"
        ... )
    """

    content: dict[str, Any]
    metadata: dict[str, Any]
    schema_version: str
    artifact_kind: str


class ArtifactGenerator(abc.ABC):
    """Abstract base class for artifact generators with plugin registry.

    Subclasses must implement:
        - artifact_kind: str class attribute defining the artifact type
        - generate(): method to produce artifacts from content

    Plugin registry enables dynamic discovery and registration of generators.

    Example:
        >>> # Register a generator
        >>> ArtifactGenerator.register_generator("summary", SummaryGenerator)
        >>>
        >>> # Get a registered generator
        >>> generator_class = ArtifactGenerator.get_generator("summary")
        >>> generator = generator_class()
        >>>
        >>> # Auto-discover all generators in the artifact_generation directory
        >>> ArtifactGenerator.auto_discover()
    """

    # Plugin registry: maps artifact_kind -> generator class
    _registry: dict[str, Type[ArtifactGenerator]] = {}

    @property
    @abc.abstractmethod
    def artifact_kind(self) -> str:
        """Return the artifact type identifier (e.g., 'summary', 'entities_index')."""

    @abc.abstractmethod
    def generate(
        self, context: str, llm_provider: LLMProvider, **kwargs: Any
    ) -> ArtifactResult:
        """Generate artifact from context using the provided LLM provider.

        Args:
            context: Input text content to analyze (meeting transcript, document, etc.)
            llm_provider: LLM provider instance for text generation
            **kwargs: Additional generation parameters (source_type, metadata, etc.)

        Returns:
            ArtifactResult with generated content and metadata

        Raises:
            ValueError: If context is empty or invalid
            RuntimeError: If LLM generation fails
            json.JSONDecodeError: If LLM response is not valid JSON

        Example:
            >>> from src.services.llm.factory import LLMProviderFactory
            >>> provider = LLMProviderFactory.create("openai", "gpt-4o")
            >>> generator = SummaryGenerator()
            >>> result = generator.generate(
            ...     context="Meeting transcript...",
            ...     llm_provider=provider,
            ...     source_type="meeting",
            ...     metadata={"meeting_id": "123"}
            ... )
        """

    @classmethod
    def register_generator(
        cls, kind: str, generator_class: Type[ArtifactGenerator]
    ) -> None:
        """Register a generator class for a specific artifact kind.

        Args:
            kind: Artifact type identifier (e.g., "summary", "entities_index")
            generator_class: Generator class implementing ArtifactGenerator

        Raises:
            ValueError: If kind is empty or generator_class is not a subclass

        Example:
            >>> ArtifactGenerator.register_generator("summary", SummaryGenerator)
        """
        if not kind:
            raise ValueError("Artifact kind cannot be empty")

        if not inspect.isclass(generator_class) or not issubclass(
            generator_class, ArtifactGenerator
        ):
            raise ValueError(
                f"Generator class must be a subclass of ArtifactGenerator, "
                f"got {generator_class}"
            )

        cls._registry[kind] = generator_class

    @classmethod
    def get_generator(cls, kind: str) -> Type[ArtifactGenerator]:
        """Retrieve a registered generator class by artifact kind.

        Args:
            kind: Artifact type identifier

        Returns:
            Generator class for the specified kind

        Raises:
            KeyError: If no generator is registered for the specified kind

        Example:
            >>> generator_class = ArtifactGenerator.get_generator("summary")
            >>> generator = generator_class()
        """
        if kind not in cls._registry:
            available = ", ".join(cls._registry.keys())
            raise KeyError(
                f"No generator registered for artifact kind '{kind}'. "
                f"Available: {available or 'none'}"
            )

        return cls._registry[kind]

    @classmethod
    def auto_discover(cls) -> None:
        """Auto-discover and import generator modules from the artifact_generation directory.

        Scans src/services/artifact_generation/ for *_generator.py files,
        imports them dynamically, and registers discovered generators.

        Import errors are logged but don't halt discovery.

        Example:
            >>> # Auto-discover all generators on startup
            >>> ArtifactGenerator.auto_discover()
            >>> # Now all *_generator.py files are imported and registered
        """
        # Get the directory containing this base.py file
        base_dir = Path(__file__).parent

        # Scan for *_generator.py files
        for generator_file in base_dir.glob("*_generator.py"):
            module_name = generator_file.stem  # e.g., "summary_generator"

            try:
                # Import the module dynamically
                # Module path: src.services.artifact_generation.{module_name}
                importlib.import_module(
                    f"src.services.artifact_generation.{module_name}"
                )
            except Exception as e:
                # Log import errors but continue discovery
                print(
                    f"Warning: Failed to import generator module '{module_name}': {e}"
                )
                continue

    @classmethod
    def list_registered(cls) -> list[str]:
        """Return list of all registered artifact kinds.

        Returns:
            List of artifact kind identifiers

        Example:
            >>> ArtifactGenerator.auto_discover()
            >>> kinds = ArtifactGenerator.list_registered()
            >>> print(kinds)
            ['summary', 'entities_index', 'decisions_index']
        """
        return list(cls._registry.keys())
