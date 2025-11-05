"""Artifact generation service with plugin-based generator system.

This module provides:
    - ArtifactGenerator: Abstract base class for artifact generators
    - ArtifactResult: Result container for generated artifacts
    - Plugin registry: Auto-discovery and registration of generators

Usage:
    >>> from src.services.artifact_generation import ArtifactGenerator, ArtifactResult
    >>> from src.services.llm.factory import LLMProviderFactory
    >>>
    >>> # Auto-discover all generators
    >>> ArtifactGenerator.auto_discover()
    >>>
    >>> # Get a generator by kind
    >>> generator_class = ArtifactGenerator.get_generator("summary")
    >>> generator = generator_class()
    >>>
    >>> # Generate an artifact
    >>> provider = LLMProviderFactory.create("openai", "gpt-4o")
    >>> result = generator.generate(
    ...     context="Meeting transcript...",
    ...     llm_provider=provider,
    ...     source_type="meeting"
    ... )
    >>> print(result.content["summary"])

Available generators (after auto_discover):
    - summary: Extract summary, key points, and participants
    - entities_index: Extract people, teams, and organizations
    - decisions_index: Extract decisions with decisors and justifications
"""

from src.services.artifact_generation.base import (
    ArtifactGenerator,
    ArtifactResult,
)

# Import all generator modules to ensure registration
# Note: Generators auto-register themselves on import
from src.services.artifact_generation.summary_generator import SummaryGenerator
from src.services.artifact_generation.entities_generator import EntitiesGenerator
from src.services.artifact_generation.decisions_generator import DecisionsGenerator

# Auto-discover generators on module import
# This ensures all *_generator.py files are loaded and registered
ArtifactGenerator.auto_discover()

# Public API
__all__ = [
    "ArtifactGenerator",
    "ArtifactResult",
    "SummaryGenerator",
    "EntitiesGenerator",
    "DecisionsGenerator",
]


# Convenience functions
def get_generator(kind: str) -> type[ArtifactGenerator]:
    """Get a registered generator class by artifact kind.

    Args:
        kind: Artifact type identifier (e.g., "summary", "entities_index")

    Returns:
        Generator class for the specified kind

    Raises:
        KeyError: If no generator is registered for the specified kind

    Example:
        >>> generator_class = get_generator("summary")
        >>> generator = generator_class()
    """
    return ArtifactGenerator.get_generator(kind)


def register_generator(kind: str, generator_class: type[ArtifactGenerator]) -> None:
    """Register a custom generator class.

    Args:
        kind: Artifact type identifier
        generator_class: Generator class implementing ArtifactGenerator

    Example:
        >>> class CustomGenerator(ArtifactGenerator):
        ...     @property
        ...     def artifact_kind(self) -> str:
        ...         return "custom"
        ...     def generate(self, context, llm_provider, **kwargs):
        ...         # Implementation
        ...         pass
        >>> register_generator("custom", CustomGenerator)
    """
    ArtifactGenerator.register_generator(kind, generator_class)


def list_generators() -> list[str]:
    """Return list of all registered artifact kinds.

    Returns:
        List of artifact kind identifiers

    Example:
        >>> kinds = list_generators()
        >>> print(kinds)
        ['summary', 'entities_index', 'decisions_index']
    """
    return ArtifactGenerator.list_registered()
