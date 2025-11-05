# Artifact Generation Infrastructure - Usage Guide

## Overview

The artifact generation infrastructure provides a plugin-based system for generating AI-powered artifacts from meeting transcripts and documents. It supports multiple LLM providers (OpenAI, Anthropic) and uses a template-based prompt system.

## Architecture

### Components

1. **ArtifactGenerator (base.py)**: Abstract base class with plugin registry
2. **ArtifactResult**: Data class containing generated content and metadata
3. **Generators**: Specialized implementations for different artifact types
   - SummaryGenerator: Extract summaries, key points, and participants
   - EntitiesGenerator: Extract people, teams, and organizations
   - DecisionsGenerator: Extract decisions with decisors and justifications

### Plugin Registry

The plugin registry enables:
- Auto-discovery of generators at runtime
- Dynamic registration of custom generators
- Retrieval of generators by artifact kind

## Installation

All required files are located in:
```
src/services/artifact_generation/
├── __init__.py                    # Module initialization with auto-discovery
├── base.py                        # ArtifactGenerator and ArtifactResult
├── summary_generator.py           # Summary artifact generator
├── entities_generator.py          # Entities extraction generator
├── decisions_generator.py         # Decisions extraction generator
└── prompts/                       # Prompt templates
    ├── summary_v1.txt
    ├── entities_v1.txt
    └── decisions_v1.txt
```

## Usage Examples

### Basic Usage

```python
from src.services.artifact_generation import ArtifactGenerator, ArtifactResult
from src.services.llm.factory import LLMProviderFactory

# Initialize LLM provider
provider = LLMProviderFactory.create("openai", "gpt-4o")

# Get generator by kind
generator_class = ArtifactGenerator.get_generator("summary")
generator = generator_class()

# Generate artifact
result = generator.generate(
    context="Meeting transcript about Q4 planning...",
    llm_provider=provider,
    source_type="meeting",
    metadata={"meeting_id": "123", "duration": "45 minutes"}
)

# Access results
print(result.content["summary"])
print(result.content["key_points"])
print(f"Cost: ${result.metadata['cost']:.4f}")
```

### Using Different Generators

#### Summary Generator

```python
from src.services.artifact_generation import SummaryGenerator
from src.services.llm.factory import LLMProviderFactory

provider = LLMProviderFactory.create("openai", "gpt-4o")
generator = SummaryGenerator()

result = generator.generate(
    context="Alice and Bob discussed the Q4 roadmap...",
    llm_provider=provider,
    source_type="meeting"
)

# Result structure:
# {
#   "summary": "Brief overview...",
#   "key_points": ["Point 1", "Point 2"],
#   "participants": ["Alice", "Bob"]
# }
```

#### Entities Generator

```python
from src.services.artifact_generation import EntitiesGenerator
from src.services.llm.factory import LLMProviderFactory

provider = LLMProviderFactory.create("openai", "gpt-4o")
generator = EntitiesGenerator()

result = generator.generate(
    context="Alice from Engineering Team discussed partnership with Acme Corp...",
    llm_provider=provider,
    source_type="meeting"
)

# Result structure:
# {
#   "entities": [
#     {
#       "name": "Alice",
#       "type": "person",
#       "context": "from Engineering Team",
#       "mentions": 3
#     },
#     {
#       "name": "Engineering Team",
#       "type": "team",
#       "context": "Alice's team",
#       "mentions": 2
#     }
#   ]
# }
```

#### Decisions Generator

```python
from src.services.artifact_generation import DecisionsGenerator
from src.services.llm.factory import LLMProviderFactory

provider = LLMProviderFactory.create("anthropic", "claude-3-5-sonnet-20241022")
generator = DecisionsGenerator()

result = generator.generate(
    context="Alice decided to use PostgreSQL for better performance...",
    llm_provider=provider,
    source_type="meeting"
)

# Result structure:
# {
#   "decisions": [
#     {
#       "decisor": "Alice",
#       "decision": "Use PostgreSQL for production",
#       "justification": "Better performance for our use case",
#       "timestamp": "00:15:30"  # Optional
#     }
#   ]
# }
```

### Multi-Provider Support

```python
from src.services.llm.factory import LLMProviderFactory
from src.services.artifact_generation import get_generator

# Use OpenAI for summaries
openai_provider = LLMProviderFactory.create("openai", "gpt-4o")
summary_gen = get_generator("summary")()
summary_result = summary_gen.generate(context, openai_provider)

# Use Anthropic for decisions
anthropic_provider = LLMProviderFactory.create(
    "anthropic",
    "claude-3-5-sonnet-20241022"
)
decisions_gen = get_generator("decisions_index")()
decisions_result = decisions_gen.generate(context, anthropic_provider)
```

### Accessing Generation Metadata

```python
result = generator.generate(context, provider)

# Access metadata
metadata = result.metadata
print(f"Provider: {metadata['provider']}")
print(f"Model: {metadata['model']}")
print(f"Tokens: {metadata['total_tokens']}")
print(f"Cost: ${metadata['cost']:.4f}")
print(f"Temperature: {metadata['temperature']}")
print(f"Prompt Template: {metadata['prompt_template']}")
```

### Listing Available Generators

```python
from src.services.artifact_generation import list_generators

# List all registered generators
kinds = list_generators()
print(f"Available generators: {kinds}")
# Output: ['summary', 'entities_index', 'decisions_index']
```

### Error Handling

```python
from src.services.artifact_generation import get_generator
from src.services.llm.factory import LLMProviderFactory
import json

provider = LLMProviderFactory.create("openai", "gpt-4o")
generator = get_generator("summary")()

try:
    result = generator.generate(
        context="Meeting transcript...",
        llm_provider=provider
    )
except ValueError as e:
    print(f"Validation error: {e}")
except RuntimeError as e:
    print(f"LLM generation failed: {e}")
except json.JSONDecodeError as e:
    print(f"Invalid JSON response from LLM: {e}")
except KeyError as e:
    print(f"Missing required field in response: {e}")
```

## Plugin Registry Details

### Auto-Discovery

Auto-discovery happens automatically on module import:

```python
from src.services.artifact_generation import ArtifactGenerator

# Generators are already discovered and registered
kinds = ArtifactGenerator.list_registered()
```

### Manual Registration

You can register custom generators:

```python
from src.services.artifact_generation import ArtifactGenerator, ArtifactResult
from src.services.llm.base import LLMProvider

class CustomGenerator(ArtifactGenerator):
    @property
    def artifact_kind(self) -> str:
        return "custom_artifact"

    def generate(self, context: str, llm_provider: LLMProvider, **kwargs):
        # Your implementation
        return ArtifactResult(
            content={"custom_data": "..."},
            metadata={"provider": "openai", "model": "gpt-4o"},
            schema_version="1.0",
            artifact_kind=self.artifact_kind
        )

# Register the custom generator
ArtifactGenerator.register_generator("custom_artifact", CustomGenerator)

# Use it
generator = ArtifactGenerator.get_generator("custom_artifact")()
```

## Prompt Templates

Prompt templates use simple string substitution with `{variable}` placeholders:

### Template Variables

Common variables:
- `{content}`: The input text to analyze
- `{source_type}`: Type of content ("meeting", "document", etc.)
- `{metadata}`: Additional context information

### Customizing Prompts

To use a custom prompt:

1. Create a new template file in `prompts/` directory
2. Update the generator to reference the new template
3. Use the same variable names for consistency

Example custom template (`prompts/summary_v2.txt`):
```
Analyze this {source_type}:

{content}

Provide a detailed summary with:
- Executive summary (2-3 sentences)
- Key topics discussed
- Action items identified
- Participants involved

Respond in JSON format only.
```

## Testing

### Unit Tests

```python
import pytest
from src.services.artifact_generation import SummaryGenerator, ArtifactResult
from unittest.mock import Mock

def test_summary_generator():
    # Mock LLM provider
    mock_provider = Mock()
    mock_provider.generate.return_value = Mock(
        content='{"summary": "Test", "key_points": ["Point 1"]}',
        provider="openai",
        model="gpt-4o",
        prompt_tokens=100,
        completion_tokens=50
    )
    mock_provider.estimate_cost.return_value = 0.01

    # Test generation
    generator = SummaryGenerator()
    result = generator.generate("Test content", mock_provider)

    assert result.artifact_kind == "summary"
    assert "summary" in result.content
    assert result.metadata["cost"] == 0.01
```

## Performance Considerations

- **Token usage**: Monitored via metadata (prompt_tokens, completion_tokens)
- **Cost estimation**: Automatically calculated per generation
- **Temperature settings**:
  - Summary: 0.7 (more creative)
  - Entities: 0.5 (more consistent)
  - Decisions: 0.5 (more consistent)
- **Max tokens**:
  - Summary: 2000
  - Entities: 2000
  - Decisions: 2500

## Implementation Status

✅ **Completed Tasks (T034-T037)**:

- **T034**: `base.py` with ArtifactGenerator, ArtifactResult, and plugin registry
- **T035**: `summary_generator.py` with SummaryGenerator
- **T036**: `entities_generator.py` with EntitiesGenerator
- **T037**: `decisions_generator.py` with DecisionsGenerator

All generators include:
- Prompt template loading from files
- JSON response validation
- Error handling
- Cost calculation
- Auto-registration

## Files Created

```
src/services/artifact_generation/
├── __init__.py                         (3.6 KB)
├── base.py                             (7.1 KB)
├── summary_generator.py                (6.7 KB)
├── entities_generator.py               (9.0 KB)
├── decisions_generator.py              (8.1 KB)
└── prompts/
    ├── summary_v1.txt                  (811 B)
    ├── entities_v1.txt                 (1.1 KB)
    └── decisions_v1.txt                (1.3 KB)

Total: 8 files, ~38 KB
```
