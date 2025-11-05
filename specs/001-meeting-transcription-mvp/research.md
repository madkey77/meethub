# Research & Technology Decisions

**Feature**: RAG-Enhanced Meeting Intelligence System
**Date**: 2025-11-04
**Context**: This document captures research findings and technical decisions made during Phase 0 planning.

## Overview

This research phase addresses technology selections, integration patterns, and best practices for building a RAG-enhanced meeting intelligence system that extends existing Google Meet + Deepgram infrastructure.

---

## Decision 1: Vector Database Selection

**Decision**: ChromaDB (embedded vector store)

**Rationale**:
- **Local-first**: Embedded mode requires no separate server process, aligns with local deployment requirement
- **RAG experimentation**: Easy access to distance metrics, filtering parameters, and retrieval strategies for tuning
- **Python-native**: First-class Python API, integrates seamlessly with LangChain
- **Metadata filtering**: Supports project-based, date-based filtering for scoped retrieval
- **Performance**: Handles 100k-1M vectors efficiently on commodity hardware (16GB RAM)
- **Persistence**: Automatic persistence to disk, survives restarts
- **Speaker metadata preservation**: ChromaDB metadata fields can store Deepgram speaker labels and timestamps alongside embeddings

**Alternatives Considered**:
- **Qdrant**: Better performance and scalability, but requires separate Docker container. Overkill for MVP scale (10k documents, 100k chunks).
- **SQLite-vss**: Lightest option, but limited query capabilities and slower for large vector sets. Better for <10k vectors.
- **FAISS**: High performance but no metadata filtering, requires custom persistence layer.

**Implementation Notes**:
- Use persistent client: `chromadb.PersistentClient(path="./data/chroma_db")`
- Single collection with metadata filtering (project_id, file_id, meeting_id) for flexible queries
- Embedding model consistency: Store model name in collection metadata to prevent mismatches
- Distance metric: Cosine similarity (default) for semantic search

**Migration Path**: If scale exceeds ChromaDB limits (~1M vectors), migration to Qdrant is straightforward via LangChain's vector store abstraction.

---

## Decision 2: RAG Framework Selection

**Decision**: LangChain

**Rationale**:
- **Comprehensive ecosystem**: Pre-built loaders for PDF, DOCX, JSON, markdown; text splitters; retrieval chains
- **LLM abstraction**: Easy swapping between OpenAI and Anthropic via LLM_PROVIDER_PREFERENCE, extensible for future providers
- **Vector store integrations**: Native ChromaDB support with metadata filtering
- **Chain templates**: `RetrievalQA` and `ConversationalRetrievalChain` for chat with memory
- **Community support**: Extensive documentation, examples, and troubleshooting resources
- **Extensibility**: Can customize loaders, splitters, and prompts while leveraging framework infrastructure

**Alternatives Considered**:
- **LlamaIndex**: Simpler, more focused on RAG. Easier learning curve but less flexibility for non-RAG workflows (e.g., custom pipelines, agents). LangChain's broader scope better supports future extensibility.
- **Custom implementation**: Full control, minimal dependencies. Would require building document loaders, text splitters, and retrieval logic from scratch. Not justified for MVP given LangChain maturity.

**Implementation Notes**:
- Use `UnstructuredFileLoader` for PDFs (with OCR fallback via pytesseract)
- Use `Docx2txtLoader` for DOCX files
- Use `JSONLoader` with JMESPath for chat backup JSON parsing
- Text splitting: `RecursiveCharacterTextSplitter` with 1200 char chunks, 200 char overlap (configurable per file type)
- Retrieval: `VectorStoreRetriever` with configurable top-K and metadata filters

**Best Practices**:
- Version pin LangChain to avoid breaking changes (ecosystem evolves rapidly)
- Use LangSmith (optional) for prompt debugging and tracing in development
- Implement custom retry logic for LLM calls (LangChain's default is limited)

---

## Decision 3: Chat Interface Selection

**Decision**: Streamlit

**Rationale**:
- **Zero frontend code**: Build entire UI in Python, no React/Vue/HTML/CSS/JS required
- **Rapid iteration**: Live reload during development, instant UI updates
- **Built-in components**: Chat input, file uploader, tables, charts, metrics cards
- **Session state**: Easy management of chat history and user context
- **Multi-page apps**: Dashboard, chat, file browser, artifact viewer all in one app
- **Deployment simplicity**: Single command (`streamlit run app.py`), no build step

**Alternatives Considered**:
- **Open WebUI**: Full-featured chat interface with local LLM support. Heavyweight, separate service, harder to customize for artifact linking and job tracking.
- **Chatbot UI**: Modern, lightweight. Requires React development and API integration work.
- **Custom React/Vue**: Maximum flexibility. Requires frontend development, build tooling, state management. Deferred to future iteration.
- **Gradio**: Similar to Streamlit but less mature multi-page support. Streamlit has better table/data display.

**Implementation Notes**:
- Multi-page structure: `src/ui/app.py` as main entry point, `src/ui/pages/` directory for each view
- Shared state: Use `st.session_state` for chat history, selected project, filters
- API integration: Call FastAPI backend via `httpx` or `requests`
- Real-time updates: Use `st.rerun()` for job status polling
- Citations: Render as markdown links with `st.markdown()` and custom CSS for click tracking

**Migration Path**: Streamlit code can coexist with future custom frontend. FastAPI layer provides clean separation, allowing gradual migration.

---

## Decision 4: Dual-Provider LLM Integration Strategy

**Decision**: Dual-provider abstraction with OpenAI and Anthropic support, user-selectable via configuration

**Rationale**:
- **User requirement**: "It should be possible to test diferent models from diferent companies easily"
- **Experimentation focus**: System is experimental, need to compare quality/cost/latency across providers
- **User control**: Providers are equal alternatives selected via LLM_PROVIDER_PREFERENCE environment variable, not automatic fallback
- **Extensibility**: Strategy pattern + Factory pattern enables adding future providers (e.g., Ollama for local models) without refactoring
- **Quality comparison**: OpenAI GPT-4o (best general quality, default) vs Anthropic Claude (strong reasoning, long context)

**Provider Matrix** (MVP Scope):

| Provider | Models | Use Case | Cost | Latency |
|----------|--------|----------|------|---------|
| OpenAI | GPT-4o, GPT-4o-mini, text-embedding-3-large | General-purpose, default provider | $5/1M input, $15/1M output | ~2s |
| Anthropic | Claude 3.5 Sonnet, Claude 3 Opus | High-quality reasoning, long context | $3/1M input, $15/1M output | ~3s |

**Future Extension Path**:
- **Ollama** (local models): Can be added by implementing `OllamaProvider` class, updating factory to support `ollama` provider name, and adding OLLAMA_BASE_URL to .env
- No refactoring required—LLMProvider interface designed for extensibility

**Implementation Strategy**:
- **Abstract interface**: `LLMProvider` base class with `generate(prompt, **kwargs)` and `embed(texts)` methods
- **Provider implementations**: OpenAIProvider, AnthropicProvider (MVP scope only)
- **Factory pattern**: `LLMProviderFactory.create(provider_name, model_name, **config)` instantiates provider based on LLM_PROVIDER_PREFERENCE
- **Configuration-driven**: Global provider selection via LLM_PROVIDER_PREFERENCE env var (default: openai), per-artifact override via rules.yaml
- **No automatic failover**: If selected provider fails (API down, invalid key), system raises clear error. User must manually switch providers by updating .env

**API Integration Notes**:
- **OpenAI**: Use `openai` SDK v1.0+ with async client for embeddings and generation
- **Anthropic**: Use `anthropic` SDK with async client
- **Retry logic**: Provider-specific retries (OpenAI: 3 attempts, exponential backoff over 5min; Anthropic: 2 attempts, linear backoff over 3min)
- **Timeout**: 30s for chat queries, 60s for artifact generation, 10s for embeddings
- **Validation**: System validates selected provider's API key on startup, fails fast with clear error if missing

**Cost Estimation** (for 10k documents, 100k chunks):
- **Embeddings**: 100k chunks × 300 tokens avg × $0.13/1M tokens (OpenAI text-embedding-3-large) = ~$4
- **Artifact generation**: 10k documents × 2k tokens output × $15/1M tokens (GPT-4o) = ~$300
- **Chat queries**: 100 queries/day × 365 days × 1k tokens × $5/1M tokens = ~$180/year
- **Total MVP cost**: ~$500 for full corpus + 1 year of queries (OpenAI only)

**Environment Configuration**:
```bash
# LLM Provider Selection (required)
LLM_PROVIDER_PREFERENCE=openai  # Options: openai | anthropic (default: openai)

# OpenAI Configuration
OPENAI_API_KEY=sk-...
OPENAI_EMBEDDING_MODEL=text-embedding-3-large
OPENAI_CHAT_MODEL=gpt-4o
OPENAI_MAX_RETRIES=3
OPENAI_TIMEOUT=30

# Anthropic Configuration
ANTHROPIC_API_KEY=sk-ant-...
ANTHROPIC_CHAT_MODEL=claude-3-5-sonnet-20241022
ANTHROPIC_MAX_RETRIES=2
ANTHROPIC_TIMEOUT=30
```

**Provider Switching Example**:
```bash
# To switch from OpenAI to Anthropic:
# 1. Update .env: LLM_PROVIDER_PREFERENCE=anthropic
# 2. Ensure ANTHROPIC_API_KEY is configured
# 3. Restart application
# All new artifact generation will use Anthropic Claude
```

---

## Decision 5: Bridge Pattern for Meeting-to-RAG Integration

**Decision**: MeetingRAGBridge service to connect existing transcription pipeline to RAG ingestion

**Rationale**:
- **Preserve existing infrastructure**: User explicitly requested "keep the transcription service for the videos and audios of meetings"
- **Loose coupling**: Bridge pattern prevents tight coupling between existing transcription code and new RAG code
- **Dual job tracking**: ProcessingJob (existing, for transcription) coexists with JobRun (new, for RAG) without forced unification
- **Independent evolution**: Can modify transcription or RAG pipelines without affecting the other
- **Testability**: Can test transcription and RAG pipelines independently, then integration via bridge

**Architecture**:
```
Google Meet API → GoogleMeetService.poll_ended_meetings()
                ↓
Google Drive API → GoogleMeetService.download_recording()
                ↓
Deepgram API → TranscriptionService.transcribe() → Transcript (DB)
                ↓
MeetingRAGBridge.on_transcription_complete(transcript_id)
                ↓
                ├─> File.create(source="meeting", source_id=transcript.meeting_id)
                ├─> FileVersion.create(content_hash=sha256(transcript.full_text))
                └─> IngestionEvent.create() → RAGPipeline.process()
```

**Bridge Responsibilities**:
1. Listen for transcription completion events (via ProcessingJob status change or explicit callback)
2. Create File entity linking to Meeting
3. Create FileVersion with transcript content (preserve Deepgram response JSON for speaker metadata)
4. Trigger RAG pipeline ingestion via IngestionEvent

**Speaker Metadata Preservation**:
- Deepgram response includes `utterances` array with speaker labels (Speaker 0, Speaker 1, etc.)
- Bridge passes utterances to chunking service
- MeetingChunker creates chunks with `speaker` and `timestamp` metadata
- Metadata stored in ChromaDB alongside embeddings
- Chat queries can filter by speaker or highlight speaker attribution in responses

**Implementation Notes**:
- Bridge runs as background task (scheduled or event-driven)
- Idempotency: Check if File already exists for Meeting before creating
- Error handling: If RAG ingestion fails, log error but don't fail transcription
- Configuration: Enable/disable bridge via `ENABLE_RAG_BRIDGE=true` environment variable

---

## Decision 6: Plugin System for Extensibility

**Decision**: Directory-based plugin discovery for artifact generators and chunking strategies

**Rationale**:
- **User requirement**: "The project should be modular as it is experimental and we need to prototype fast"
- **Fast prototyping**: Add new artifact type by dropping Python file in `src/services/artifact_generation/` directory
- **No registration boilerplate**: Plugins auto-discovered via convention (inherit from base class, implement interface)
- **Experimentation-friendly**: Test different chunking strategies (character-based, sentence-based, semantic) without modifying core code
- **Configuration-driven**: Select plugins via rules.yaml without code changes

**Plugin Types**:

1. **Chunking Strategies** (`src/services/chunking/`):
   - Interface: `ChunkingStrategy` with `chunk(content, metadata) -> List[Chunk]` method
   - Implementations: `MeetingChunker` (preserve speakers), `DocumentChunker` (generic)
   - Selection: Auto-detect based on file type (meeting → MeetingChunker, document → DocumentChunker)

2. **Artifact Generators** (`src/services/artifact_generation/`):
   - Interface: `ArtifactGenerator` with `generate(file_version, context) -> str` method
   - Implementations: `SummaryGenerator`, `EntitiesGenerator`, `DecisionsGenerator`
   - Selection: Configured per file type in rules.yaml

**Discovery Mechanism**:
```python
# Example: Artifact generator discovery
import importlib
import inspect
from pathlib import Path

def discover_generators():
    generators = {}
    plugin_dir = Path("src/services/artifact_generation")
    for file in plugin_dir.glob("*_generator.py"):
        module = importlib.import_module(f"src.services.artifact_generation.{file.stem}")
        for name, obj in inspect.getmembers(module, inspect.isclass):
            if issubclass(obj, ArtifactGenerator) and obj != ArtifactGenerator:
                generators[name] = obj
    return generators
```

**Configuration Example** (rules.yaml):
```yaml
artifact_generation_rules:
  - file_type: "meeting"
    artifacts:
      - kind: "summary"
        generator: "SummaryGenerator"
        llm_provider: "openai"
        llm_model: "gpt-4o"
      - kind: "entities_index"
        generator: "EntitiesGenerator"
        llm_provider: "anthropic"
        llm_model: "claude-3-5-sonnet-20241022"

  - file_type: "document"
    artifacts:
      - kind: "summary"
        generator: "SummaryGenerator"
        llm_provider: "openai"
        llm_model: "gpt-4o-mini"
```

---

## Decision 7: Incremental Processing Strategy

**Decision**: SHA-256 hash-based change detection with incremental artifact regeneration

**Rationale**:
- **Efficiency**: Reprocessing entire corpus on every change wastes resources (API costs, compute time)
- **User experience**: Fast feedback loop for updated files (regenerate only affected artifacts)
- **Correctness**: Hash-based detection ensures changes are never missed (file modification time can be unreliable)

**Implementation Strategy**:

1. **File Change Detection**:
   - Compute SHA-256 hash of file content on upload/update
   - Compare with latest FileVersion.content_hash in database
   - If hash differs, create new FileVersion and trigger ingestion

2. **Incremental Artifact Updates**:
   - When new FileVersion created, invalidate only artifacts derived from that file
   - Regenerate invalidated artifacts using existing RAG pipeline
   - Preserve artifacts for unchanged files

3. **Vector Store Updates**:
   - Delete old chunks for updated FileVersion from ChromaDB
   - Generate new chunks and embeddings
   - Insert new chunks with same file_id (preserves query history)

**Cost Optimization**:
- Track artifact generation cost per FileVersion (LLM tokens used)
- Skip artifact regeneration if content change is minor (e.g., <5% diff)
- Cache LLM responses for identical prompts (TTL: 24 hours)

**Implementation Notes**:
- Use Python `hashlib.sha256()` for content hashing
- Store previous hash in FileVersion.previous_version_id for diff tracking
- Soft delete old chunks (Chunk.deleted=true) to preserve audit trail

---

## Summary

All technical unknowns from the specification have been addressed:

1. **Vector Database**: ChromaDB (embedded, local-first, handles MVP scale)
2. **RAG Framework**: LangChain (comprehensive, LLM-agnostic, extensible)
3. **Chat Interface**: Streamlit (rapid prototyping, Python-only, multi-page support)
4. **Dual-Provider LLMs**: OpenAI (default) + Anthropic with user-selectable configuration via LLM_PROVIDER_PREFERENCE, Strategy + Factory pattern for extensibility
5. **Meeting Integration**: Bridge pattern connects existing transcription to RAG pipeline
6. **Extensibility**: Directory-based plugin discovery for artifact generators and chunking strategies
7. **Incremental Processing**: SHA-256 hash-based change detection for efficiency

Ready to proceed to Phase 1: Design.
