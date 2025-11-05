# Implementation Plan: RAG-Enhanced Meeting Intelligence System

**Branch**: `001-meeting-transcription-mvp` | **Date**: 2025-11-04 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/001-meeting-transcription-mvp/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/commands/plan.md` for the execution workflow.

## Summary

Extend existing Google Meet + Deepgram transcription infrastructure (KEEP all existing services) to add RAG capabilities for intelligent querying across meetings and documents. System combines automated meeting pipeline (Google Meet API polling → recording downloads → Deepgram transcription with speaker diarization) with manual file ingestion (PDF, DOCX, markdown, JSON) into a unified RAG system. Key technical approach: Bridge pattern connects existing transcription to RAG pipeline, dual-provider LLM architecture (OpenAI and Anthropic) with user-selectable configuration enables experimentation, plugin system for artifact generators/chunking strategies enables fast prototyping. Technology stack: Python 3.11+ + FastAPI + ChromaDB (embedded vector store) + LangChain + Streamlit UI + OpenAI/Anthropic LLMs.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**:
- **Existing (KEEP)**: Deepgram SDK 5.x (transcription), google-api-python-client (Meet/Drive APIs), structlog (logging), SQLAlchemy (ORM)
- **New**: FastAPI 0.100+ (REST API), ChromaDB 0.4+ (vector store), LangChain 0.1+ (RAG framework), Streamlit 1.28+ (UI), OpenAI SDK 1.0+ (GPT-4o + embeddings), Anthropic SDK (Claude models)

**Storage**:
- SQLite (development) / PostgreSQL (production) for relational data (meetings, files, jobs)
- ChromaDB embedded persistent client for vector embeddings (local-first)
- Local filesystem for audio files, uploaded documents, generated artifacts

**Testing**: pytest 7.x with plugins (pytest-asyncio, pytest-cov, pytest-mock)

**Target Platform**: Linux server (local development: Ubuntu/WSL, production: Docker container)

**Project Type**: Single project with CLI + API + UI components

**Performance Goals**:
- API response times: <2s for standard requests, <10s for transcription initiation
- Transcription processing: Status updates every 30s, 10min timeout
- RAG queries: <5s for cached results, <30s for fresh analysis with LLM generation
- Embedding generation: <1s per 1000 tokens (batch processing)
- Vector search: <500ms for top-K retrieval from 100k chunks

**Constraints**:
- Cloud LLM dependency: At least one LLM provider (OpenAI or Anthropic) must be configured
- Database queries: <100ms for standard lookups (indexed appropriately)
- Memory: ChromaDB can handle 100k-1M vectors on 16GB RAM
- Disk: ~5GB for vector storage (100k chunks)
- Extensible architecture: LLMProvider interface supports future local model integration (e.g., Ollama) without code refactoring

**Scale/Scope**:
- MVP target: 10 users, 100 meetings, 10k documents, 100k text chunks
- Post-MVP: 100 users, 1k meetings, 100k documents, 1M chunks
- Codebase: ~15k LOC (8k existing + 7k new)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

### Principle I: AI-First Development
✅ **PASS** - All code will be generated via Speckit workflow (`/speckit.specify` → `/speckit.plan` → `/speckit.tasks` → `/speckit.implement`)

### Principle II: Regression Prevention (NON-NEGOTIABLE)
✅ **PASS** - Test requirements specified:
- **Unit tests**: Business logic for chunking, LLM provider abstraction, artifact generation rules
- **Integration tests**: FastAPI endpoints, ChromaDB operations, LLM API calls (mocked + real)
- **E2E tests**: Meeting upload → transcription → RAG ingestion → chat query → artifact generation
- **Contract tests**: API contracts validated against OpenAPI schema (generated in Phase 1)

Test strategy: Tests written during implementation (per tasks.md), coverage tracked with pytest-cov, all tests must pass before task completion.

### Principle III: Production Readiness
✅ **PASS** - Production quality requirements addressed:
- **Error handling**: Custom exception hierarchy (existing: DeepgramAPIError, GoogleMeetAPIError; new: RAGError, EmbeddingError), clear error messages for LLM failures (missing API keys, invalid configuration, provider unavailability)
- **Logging**: Structured logging with structlog (existing infrastructure reused), request correlation IDs for RAG pipeline tracking
- **Monitoring**: Health check endpoints (FastAPI /health), metrics for transcription/RAG job durations, success/failure rates
- **Data integrity**: SQLAlchemy models with constraints, input validation via Pydantic schemas, SHA-256 hash verification for file changes
- **Security**: Authentication required (existing google_auth.py reused), API keys via environment variables, input sanitization for file uploads

Performance standards from constitution met by Technical Context constraints.

### Principle IV: Integration Testing
✅ **PASS** - Integration test strategy defined for critical boundaries:
- **Deepgram API** (existing): Audio transcription with speaker diarization (test with sample audio)
- **Google Meet/Drive APIs** (existing): Recording polling and download (test with test Google Workspace account)
- **OpenAI/Anthropic APIs** (new): Embedding generation and text generation (mocked for unit, real for integration)
- **ChromaDB operations** (new): Vector storage, retrieval, metadata filtering (test with persistent client)
- **Database transactions** (new): Concurrent file ingestion, job state transitions (test with SQLite in-memory)
- **File uploads** (new): Multipart form data, format validation, size limits (test with FastAPI TestClient)

### Principle V: Observability
✅ **PASS** - Observability requirements met:
- **Structured logging**: Reuse existing structlog configuration (JSON logs with timestamp, level, service, request_id), add RAG-specific fields (job_id, file_id, chunk_count, provider_name)
- **State transitions logged**: File uploaded → ingestion queued → chunks created → embeddings generated → artifacts created → job completed
- **Error context logged**: User action (e.g., "upload PDF"), input parameters (file size, project_id), error details (API error code, stack trace)
- **No sensitive data**: Audio content, meeting transcripts, document text excluded from logs (only IDs and metadata)
- **Metrics**: Request counts/response times per endpoint, transcription/RAG job durations, LLM provider latencies, cache hit rates for artifacts
- **Request tracing**: Correlation IDs propagated through: API request → RAG pipeline → LLM calls → database operations

### Principle VI: MVP Discipline
✅ **PASS** - MVP scope justified:
- **User Story 0 (P0 - Prerequisite)**: Validates existing Google Meet + Deepgram pipeline continues working (not a new feature, a validation checkpoint)
- **User Story 1 (P1)**: Manual file ingestion with multi-source processing - MVP core capability
- **User Story 2 (P1)**: Multi-provider LLM experimentation - CRITICAL for user requirement "test different models from different companies easily"
- **User Story 3 (P1)**: Declarative artifact generation - Delivers immediate value (summaries, entities, decisions)
- **User Stories 4-7 (P2-P3)**: Enhancements deferred to post-MVP feedback
- **Complexity justified**: Multi-provider abstraction and plugin system are REQUIRED by user for experimentation and modularity (not over-engineering)
- **Prefer proven libraries**: LangChain (mature RAG framework), ChromaDB (production-ready vector store), FastAPI (standard Python API framework)
- **Managed services**: Deepgram (existing), OpenAI/Anthropic (managed LLMs) required for MVP; extensible architecture supports future local model integration

### Principle VII: Security & Privacy
✅ **PASS** - Security and privacy requirements addressed:
- **Authentication**: Reuse existing google_auth.py OAuth2 flow, all endpoints require authentication (except /health)
- **Authorization**: Users can only access their own meetings/documents (enforced via Project entity and user_id filtering)
- **Audio files**: Encrypted at rest via filesystem permissions (production: cloud storage with encryption at rest), secure upload via FastAPI multipart forms
- **Transcriptions**: Access-controlled via Meeting.project_id foreign key, no public sharing endpoints in MVP
- **API keys**: Environment variables only (OPENAI_API_KEY, ANTHROPIC_API_KEY, DEEPGRAM_API_KEY, GOOGLE_CLIENT_SECRET), never committed
- **Input validation**: Pydantic schemas for all API inputs, file upload validation (MIME type, size limits: 100MB for audio, 50MB for documents)
- **Privacy**: Minimal data collection (only meeting metadata and transcriptions), no third-party analytics, clear data retention policy (soft delete default)
- **Compliance**: GDPR-ready (data deletion via soft delete flag, audit logging for sensitive operations)

### Phase 1 Re-Evaluation Checkpoint
✅ **PASS** - Re-evaluated after Phase 1 design artifact generation. No new violations introduced.

**Design Artifacts Reviewed**:
- ✅ data-model.md (17 entities: 4 existing preserved/extended, 13 new)
- ✅ contracts/api-spec.yaml (OpenAPI 3.0, 30+ endpoints, complete DTOs)
- ✅ quickstart.md (comprehensive setup and integration guide)
- ✅ research.md (7 technology decisions documented)

**Constitution Compliance Verification**:

1. **Principle II (Regression Prevention)**: Design supports comprehensive testing
   - data-model.md includes validation rules for all entities
   - api-spec.yaml provides contract for contract testing
   - Existing Meeting, Participant, Transcript, ProcessingJob entities preserved (no breaking changes)
   - New entities (File, Chunk, Embedding, etc.) have clear schemas for test fixtures

2. **Principle III (Production Readiness)**: Design includes production-quality features
   - Error handling: api-spec.yaml defines all error responses (400, 401, 404, 409, 500)
   - Logging: JobRun/JobStep entities track structured logs and metrics
   - Monitoring: Health check endpoints, job metrics (chunks_created, embeddings_created, cost_usd)
   - Data integrity: SHA-256 hashing (FileVersion), foreign key constraints, soft deletes
   - Security: OAuth2 security scheme in api-spec.yaml, input validation in schemas

3. **Principle IV (Integration Testing)**: Design facilitates integration testing
   - Clearly defined API contracts (OpenAPI spec)
   - Existing Deepgram/Google APIs integration preserved
   - New LLM provider interfaces (OpenAI, Anthropic) have test doubles documented in research.md
   - ChromaDB operations testable via persistent client

4. **Principle V (Observability)**: Design enables comprehensive observability
   - JobRun entity includes metrics: chunks_created, embeddings_created, artifacts_created, tokens_used, cost_usd
   - JobStep entity includes structured_logs (JSON), step_output, error_details
   - ArtifactVersion includes LLM provenance: llm_provider, llm_model, prompt_tokens, completion_tokens
   - All entities have created_at/updated_at for timeline reconstruction

5. **Principle VI (MVP Discipline)**: Design maintains MVP focus
   - data-model.md clearly separates EXISTING (4), EXTEND (3), NEW (12) entities
   - Existing infrastructure fully preserved (no rewrites)
   - Bridge pattern (MeetingRAGBridge) is minimal connector, not complex abstraction
   - Plugin system uses simple directory-based discovery (no framework overhead)
   - ChromaDB embedded mode (no separate service to manage)

6. **Principle VII (Security & Privacy)**: Design addresses security requirements
   - api-spec.yaml includes OAuth2 security scheme (references existing google_auth.py)
   - File upload size limits documented (100MB audio, 50MB documents)
   - Soft delete pattern preserves data for GDPR compliance
   - Meeting content access controlled via project_id filtering
   - No sensitive data in logged fields (structured_logs exclude transcript content)

**Conclusion**: All design artifacts comply with constitution. No principle violations detected. Ready to proceed to Phase 2 (Task Generation).

## Project Structure

### Documentation (this feature)

```text
specs/[###-feature]/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md        # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
├── contracts/           # Phase 1 output (/speckit.plan command)
└── tasks.md             # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
src/
├── models/                    # SQLAlchemy ORM models
│   ├── meeting.py            # EXISTING (extend with RAG fields)
│   ├── participant.py        # EXISTING (keep as-is)
│   ├── transcript.py         # EXISTING (extend with RAG fields)
│   ├── processing_job.py     # EXISTING (keep as-is, coexists with JobRun)
│   ├── file.py               # NEW: File entity for RAG ingestion
│   ├── file_version.py       # NEW: FileVersion entity
│   ├── chunk.py              # NEW: Chunk entity with speaker metadata
│   ├── embedding.py          # NEW: Embedding entity
│   ├── job_run.py            # NEW: JobRun entity for RAG pipeline
│   ├── job_step.py           # NEW: JobStep entity
│   ├── artifact.py           # NEW: Artifact and ArtifactVersion entities
│   ├── processing_rule.py    # NEW: ProcessingRule entity
│   ├── project.py            # NEW: Project entity
│   └── backfill_job.py       # NEW: BackfillJob entity
├── services/                  # Business logic services
│   ├── google_meet.py        # EXISTING (keep as-is)
│   ├── google_drive.py       # EXISTING (keep as-is)
│   ├── transcription.py      # EXISTING (keep as-is)
│   ├── meeting_processor.py  # EXISTING (keep as-is)
│   ├── scheduler.py          # EXISTING (keep as-is)
│   ├── meeting_rag_bridge.py # NEW: Bridge existing pipeline to RAG
│   ├── file_ingestion.py     # NEW: Multi-format file ingestion
│   ├── chunking/              # NEW: Chunking strategies (plugin system)
│   │   ├── base.py           # ChunkingStrategy interface
│   │   ├── meeting_chunker.py # Meeting-specific chunking (preserve speakers)
│   │   └── document_chunker.py # Generic document chunking
│   ├── embedding/             # NEW: Embedding providers
│   │   ├── base.py           # EmbeddingProvider interface
│   │   └── multi_provider.py # Unified embedding service
│   ├── llm/                   # NEW: LLM provider abstraction
│   │   ├── base.py           # LLMProvider abstract class
│   │   ├── openai_provider.py
│   │   ├── anthropic_provider.py
│   │   └── factory.py        # LLMProviderFactory (supports openai|anthropic)
│   ├── artifact_generation/   # NEW: Artifact generators (plugin system)
│   │   ├── base.py           # ArtifactGenerator interface
│   │   ├── summary_generator.py
│   │   ├── entities_generator.py
│   │   └── decisions_generator.py
│   ├── rag_pipeline.py       # NEW: RAG orchestration pipeline
│   ├── vector_store.py       # NEW: ChromaDB wrapper
│   └── chat_service.py       # NEW: RAG query + citation service
├── api/                       # NEW: FastAPI REST API
│   ├── main.py               # FastAPI app initialization
│   ├── dependencies.py       # Dependency injection
│   ├── middleware.py         # Auth, logging, CORS
│   ├── routes/
│   │   ├── health.py
│   │   ├── files.py          # File upload/ingestion endpoints
│   │   ├── jobs.py           # Job tracking endpoints
│   │   ├── artifacts.py      # Artifact query endpoints
│   │   ├── chat.py           # RAG chat endpoints
│   │   └── backfill.py       # Backfill endpoints
│   └── schemas/              # Pydantic request/response schemas
│       ├── file_schemas.py
│       ├── job_schemas.py
│       ├── artifact_schemas.py
│       └── chat_schemas.py
├── ui/                        # NEW: Streamlit UI
│   ├── app.py                # Main entry point
│   ├── pages/
│   │   ├── 1_File_Upload.py
│   │   ├── 2_Jobs_Dashboard.py
│   │   ├── 3_Chat.py
│   │   └── 4_Artifacts.py
│   └── components/           # Reusable UI components
│       ├── citation_card.py
│       └── job_status_badge.py
├── cli/                       # EXISTING CLI (extend)
│   ├── __init__.py
│   └── process_meeting.py    # EXISTING (keep as-is)
├── utils/                     # Utility modules
│   ├── logging.py            # EXISTING (keep as-is)
│   ├── retry.py              # EXISTING (keep as-is)
│   ├── exceptions.py         # EXISTING (extend with RAG exceptions)
│   ├── google_auth.py        # EXISTING (keep as-is)
│   ├── validators.py         # EXISTING (extend with file validators)
│   └── file_watcher.py       # NEW: File system watcher for ingestion
└── config.py                  # EXISTING (extend with RAG settings)

tests/
├── unit/                      # Unit tests
│   ├── models/
│   ├── services/
│   │   ├── llm/              # LLM provider tests (mocked APIs)
│   │   ├── chunking/
│   │   └── artifact_generation/
│   └── utils/
├── integration/               # Integration tests
│   ├── api/                  # FastAPI endpoint tests
│   ├── rag_pipeline/         # End-to-end RAG pipeline tests
│   ├── vector_store/         # ChromaDB integration tests
│   └── external_apis/        # Real API calls (OpenAI, Anthropic)
├── contract/                  # Contract tests
│   └── api_contract_test.py  # OpenAPI schema validation
└── fixtures/                  # Test data
    ├── sample_audio.mp3
    ├── sample_document.pdf
    └── sample_transcript.json

config/
└── rules.yaml                 # NEW: Declarative artifact generation rules

data/                          # Local data directory (gitignored)
├── chroma_db/                # ChromaDB persistent storage
├── uploads/                  # Uploaded files
├── recordings/               # Downloaded meeting recordings
└── artifacts/                # Generated artifacts
```

**Structure Decision**: Single project structure (Option 1) selected. Rationale:
- Existing codebase already uses single project layout (src/, tests/)
- All components (API, UI, CLI) share same database and services
- Python monorepo simplifies dependency management and deployment
- Clear separation: models (data), services (business logic), api (REST), ui (Streamlit), cli (commands), utils (shared)
- Plugin systems (chunking/, llm/, artifact_generation/) use directory-based discovery for extensibility

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

**Status**: ✅ No violations - all complexity justified by user requirements and constitution principles.
