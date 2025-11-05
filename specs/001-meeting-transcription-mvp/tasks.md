# Tasks: RAG-Enhanced Meeting Intelligence System

**Feature Branch**: `001-meeting-transcription-mvp`
**Input**: Design documents from `/specs/001-meeting-transcription-mvp/`
**Created**: 2025-11-04

**Prerequisites**:
- spec.md (8 user stories: US0-P0, US1-P1, US2-P1, US3-P1, US4-P2, US5-P3, US6-P3, US7-P2)
- plan.md (technology stack, project structure, constitution compliance)
- data-model.md (17 entities: 4 existing, 13 new)
- contracts/api-spec.yaml (30+ endpoints)
- research.md (7 technology decisions)
- quickstart.md (setup scenarios)

**Tests**: Tests are INCLUDED per constitution requirement (Principle II: Regression Prevention - NON-NEGOTIABLE)

**Organization**: Tasks grouped by user story to enable independent implementation and testing of each story.

---

## Format: `- [ ] T### [P?] [Story?] Description with file/path`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: User story label (e.g., [US0], [US1], [US2]) - ONLY for user story phase tasks
- File paths are absolute from repository root
- NO story labels for Setup, Foundational, or Polish phases

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization, dependencies, and basic structure

- [X] T001 Install Python 3.11+ dependencies: FastAPI, ChromaDB, LangChain, Streamlit, OpenAI SDK, Anthropic SDK in requirements.txt
- [X] T002 [P] Create project structure directories: src/models/, src/services/, src/api/, src/ui/, tests/unit/, tests/integration/, tests/contract/, config/, data/
- [X] T003 [P] Setup Alembic for database migrations: alembic init alembic, configure alembic.ini with SQLite connection string
- [X] T004 [P] Create .env.example with all required environment variables: LLM_PROVIDER_PREFERENCE, OPENAI_API_KEY, ANTHROPIC_API_KEY, DEEPGRAM_API_KEY, DATABASE_URL, CHROMADB_PATH
- [X] T005 [P] Setup pytest configuration in pytest.ini with coverage settings, test paths, and pytest-asyncio mode
- [X] T006 [P] Create docker-compose.yml for optional containerized deployment with ChromaDB persistent volume
- [X] T007 [P] Configure pre-commit hooks for code formatting (black), linting (ruff), and type checking (mypy)
- [X] T008 [P] Create .gitignore with entries for Python cache, venv, .env, ChromaDB data, uploaded files
- [X] T009 Update src/config.py to include RAG-specific settings: MAX_CONCURRENT_JOBS, CHROMADB_COLLECTION_NAME, CHUNK_SIZE, CHUNK_OVERLAP
- [X] T010 Create config/rules.yaml template with sample artifact generation rules for meetings and documents

**Checkpoint**: Project structure and dependencies ready

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story implementation

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

### Database Schema & Core Models

- [X] T011 Extend src/models/meeting.py to add RAG fields: file_id (FK), rag_ingestion_status (Enum), indexes on file_id and rag_ingestion_status
- [X] T012 Extend src/models/transcript.py to add RAG fields: deepgram_response (JSON), chunk_count (Integer), embedding_generated_at (DateTime), index on embedding_generated_at
- [X] T013 Extend src/models/project.py (if exists) or create new to add RAG fields: display_name, description, ingestion_folder_path, artifact_retention_days, metadata (JSON)
- [X] T014 [P] Create src/models/file.py with File entity: file_id (PK), relative_path, mime_type, source_type (Enum), project_id (FK), current_version_id (FK), deleted, created_at, updated_at
- [X] T015 [P] Create src/models/file_version.py with FileVersion entity: version_id (PK), file_id (FK), content_hash (SHA-256), file_size_bytes, content_locator, is_current, discovered_at
- [X] T016 [P] Create src/models/chunk.py with Chunk entity: chunk_id (PK), file_version_id (FK), chunk_index, text_content, char_offset_start, char_offset_end, metadata (JSON), deleted, created_at
- [X] T017 [P] Create src/models/embedding.py with Embedding entity: embedding_id (PK), chunk_id (FK, UNIQUE), embedding_model, vector_db_id, collection_name, created_at
- [X] T018 [P] Create src/models/job_run.py with JobRun entity: job_id (PK), pipeline_name, status (Enum), input_file_version_id (FK), backfill_job_id (FK), retry_count, metrics (JSON), started_at, completed_at, created_at
- [X] T019 [P] Create src/models/job_step.py with JobStep entity: step_id (PK), job_run_id (FK), step_name, status (Enum), log_output (JSON), error_message, error_type, started_at, completed_at
- [X] T020 [P] Create src/models/artifact.py with Artifact and ArtifactVersion entities per data-model.md specification
- [X] T021 [P] Create src/models/artifact_link.py with ArtifactLink entity: link_id (PK), artifact_version_id (FK), file_version_id (FK), role_type (Enum), contribution_weight, link_metadata (JSON), created_at
- [X] T022 [P] Create src/models/backfill_job.py with BackfillJob entity: backfill_job_id (PK), target_folder_path, target_file_list (JSON), total_file_count, processed_count, failed_count, status (Enum), progress_percentage, summary_report (JSON), timestamps
- [X] T023 Create Alembic migration for all new/extended models: alembic revision --autogenerate -m "Add RAG entities", test with alembic upgrade head

### LLM Provider Abstraction

- [X] T024 Create src/services/llm/base.py with LLMProvider abstract class: generate(), embed(), estimate_cost(), provider_name, model_name properties
- [X] T025 [P] Implement src/services/llm/openai_provider.py: OpenAIProvider class with GPT-4o generation, text-embedding-3-large embeddings, cost estimation
- [X] T026 [P] Implement src/services/llm/anthropic_provider.py: AnthropicProvider class with Claude models, cost estimation, retry logic
- [X] T027 [P] Implement src/services/llm/factory.py: LLMProviderFactory with provider instantiation logic, support for openai and anthropic provider names, configuration validation

### Vector Store & Embedding Infrastructure

- [X] T029 Create src/services/vector_store.py: ChromaDB wrapper with PersistentClient, collection management, metadata filtering, batch operations
- [X] T030 Create src/services/embedding/base.py: EmbeddingProvider interface and multi-provider embedding service

### Chunking Strategy Infrastructure

- [ ] T031 Create src/services/chunking/base.py: ChunkingStrategy abstract class with chunk() method
- [ ] T032 [P] Implement src/services/chunking/meeting_chunker.py: MeetingChunker that preserves speaker and timestamp metadata from Deepgram utterances
- [ ] T033 [P] Implement src/services/chunking/document_chunker.py: DocumentChunker using LangChain RecursiveCharacterTextSplitter with configurable chunk_size and overlap

### Artifact Generation Infrastructure

- [ ] T034 Create src/services/artifact_generation/base.py: ArtifactGenerator interface with generate() method and plugin registry pattern
- [ ] T035 [P] Implement src/services/artifact_generation/summary_generator.py: SummaryGenerator plugin with prompt template and JSON schema validation
- [ ] T036 [P] Implement src/services/artifact_generation/entities_generator.py: EntitiesGenerator plugin for extracting people, teams, organizations
- [ ] T037 [P] Implement src/services/artifact_generation/decisions_generator.py: DecisionsGenerator plugin with decisor/decision/justification extraction

### Core Services

- [X] T038 Extend src/utils/exceptions.py to add RAG-specific exceptions: RAGError, EmbeddingError, ChunkingError, ArtifactGenerationError, LLMProviderError
- [X] T039 Create src/services/rag_pipeline.py: RAG orchestration service coordinating normalize → chunk → embed → generate_artifacts steps
- [X] T040 Create src/services/file_ingestion.py: Multi-format file ingestion service with PyMuPDF (PDF), python-docx (DOCX), JSONLoader (chat exports)

### FastAPI Setup

- [X] T041 Create src/api/main.py: FastAPI app initialization with CORS, middleware, exception handlers, API v1 router mounting
- [X] T042 Create src/api/dependencies.py: Dependency injection for database session, LLM provider factory, vector store client, authentication
- [X] T043 Create src/api/middleware.py: Request logging middleware with correlation IDs, authentication middleware (reuse existing google_auth.py)
- [X] T044 [P] Create Pydantic schemas in src/api/schemas/file_schemas.py: FileUploadRequest, FileUploadResponse, FileListResponse, FileDetail
- [X] T045 [P] Create Pydantic schemas in src/api/schemas/job_schemas.py: JobListResponse, JobDetail, JobRun, JobStep, JobStepLogs
- [X] T046 [P] Create Pydantic schemas in src/api/schemas/artifact_schemas.py: ArtifactListResponse, ArtifactDetail, Artifact, ArtifactVersion
- [X] T047 [P] Create Pydantic schemas in src/api/schemas/chat_schemas.py: ChatQueryRequest, ChatResponse, Citation

### Foundational Tests (CRITICAL - Constitution Requirement)

> **⚠️ CONSTITUTION COMPLIANCE**: These tests MUST be written and FAIL before proceeding to user stories (Principle II: Regression Prevention - NON-NEGOTIABLE)

- [X] T047a [P] Unit tests for all new model entities in tests/unit/models/test_file_entities.py: test File, FileVersion, Chunk, Embedding entities with constraints and relationships validation
- [X] T047b [P] Unit tests for LLM provider factory in tests/unit/services/test_llm_factory.py: test configuration validation, invalid provider names, missing API keys, unsupported models
- [X] T047c [P] Unit tests for all LLM provider implementations in tests/unit/services/test_llm_providers.py: test OpenAI and Anthropic providers with mocked API calls, test error handling for invalid configuration
- [X] T047d [P] Integration test for ChromaDB vector store in tests/integration/test_vector_store.py: test collection creation, batch embedding storage, metadata filtering, retrieval
- [ ] T047e [P] Integration test for authentication middleware in tests/contract/test_auth_contract.py: verify all API endpoints except /health return 401 without valid token, verify OAuth2 flow
- [X] T047f [P] Unit tests for chunking strategies in tests/unit/services/test_chunking.py: test MeetingChunker preserves speaker metadata, DocumentChunker respects size/overlap configs

**✅ CHECKPOINT - TDD ENFORCEMENT**: All foundational tests written and failing. Verify test failures before proceeding to user story implementation.

**Checkpoint**: Foundation ready - user story implementation can now begin in parallel

---

## Phase 3: User Story 0 - Meeting Pipeline Integration Foundation (Priority: P0 - Prerequisite) 🔧

**Goal**: Validate existing Google Meet→Deepgram→RAG bridge, preserving speaker metadata end-to-end

**Independent Test**: Google Meet API detects ended meeting → recording downloads → Deepgram transcribes with speakers → transcript auto-ingests into RAG → chunks preserve speaker metadata → embeddings generated → transcript queryable via chat

### Tests for User Story 0

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [X] T048 [P] [US0] Integration test for Meeting→RAG bridge in tests/integration/test_meeting_rag_bridge.py: verify transcription triggers RAG ingestion
- [X] T049 [P] [US0] Integration test for speaker metadata preservation in tests/integration/test_speaker_metadata.py: verify chunks contain speaker labels and timestamps
- [X] T050 [P] [US0] E2E test for meeting RAG flow in tests/integration/test_meeting_e2e.py: mock Google Meet→Deepgram→RAG→Chat with sample audio

**✅ CHECKPOINT - TDD ENFORCEMENT**: All US0 tests written and failing. Implementation may now begin.

### Implementation for User Story 0

- [X] T051 [US0] Create src/services/meeting_rag_bridge.py: MeetingRAGBridge service with on_transcription_complete() callback
- [X] T052 [US0] Implement bridge logic in MeetingRAGBridge: check if File exists for Meeting, create File with source_type='meeting', create FileVersion with transcript content hash
- [X] T053 [US0] Implement speaker metadata extraction in MeetingRAGBridge: parse Transcript.deepgram_response JSON, extract utterances array with speaker labels and timestamps
- [X] T054 [US0] Extend src/services/scheduler.py to add RAG bridge trigger after transcription completion: call MeetingRAGBridge.on_transcription_complete(transcript_id)
- [X] T055 [US0] Update MeetingChunker to process Deepgram utterances: create chunks with metadata={'speaker': 'Speaker 0', 'timestamp': '00:14:32', ...}
- [X] T056 [US0] Implement automatic RAG pipeline triggering in RAGPipeline: detect new FileVersion for meeting source, queue ingestion job
- [X] T057 [US0] Add Meeting.rag_ingestion_status tracking: update status from pending→processing→completed as RAG pipeline progresses
- [X] T058 [US0] Add error handling for transcription failures: if Deepgram fails, do not create RAG records, log error with meeting context
- [X] T059 [US0] Add change detection for re-transcribed meetings: compare Transcript content hash, create new FileVersion only if changed, preserve old version

**Checkpoint**: Meeting transcriptions automatically flow into RAG pipeline with speaker metadata preserved

---

## Phase 4: User Story 1 - Manual File Ingestion with Multi-Source Processing (Priority: P1) 🎯 MVP

**Goal**: Users can upload files (PDF, DOCX, markdown, JSON) to monitored folders, system automatically processes through RAG pipeline

**Independent Test**: Upload file→file watcher detects→text extraction→chunking→embedding→artifacts generated→file queryable in chat

### Tests for User Story 1

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [X] T060 [P] [US1] Contract test for POST /api/v1/files/upload in tests/contract/test_file_upload_contract.py: validate against OpenAPI schema
- [X] T061 [P] [US1] Integration test for PDF ingestion in tests/integration/test_pdf_ingestion.py: upload PDF, verify text extraction with PyMuPDF
- [X] T061a [P] [US1] Integration test for OCR fallback in tests/integration/test_ocr_fallback.py: test scanned PDF triggers Tesseract, verify text extraction accuracy against known document
- [X] T062 [P] [US1] Integration test for DOCX ingestion in tests/integration/test_docx_ingestion.py: upload DOCX, verify paragraph structure preservation
- [X] T063 [P] [US1] Integration test for JSON chat export in tests/integration/test_json_ingestion.py: upload Slack JSON, verify message extraction
- [X] T063a [P] [US1] Integration test for multiple JSON chat formats in tests/integration/test_chat_formats.py: test Slack, Teams, WhatsApp schema parsing
- [X] T064 [P] [US1] Integration test for duplicate detection in tests/integration/test_duplicate_detection.py: upload identical file twice, verify SHA-256 deduplication
- [X] T065 [P] [US1] Integration test for concurrent uploads in tests/integration/test_concurrent_uploads.py: upload 20 files simultaneously, verify parallelism limits respected

**✅ CHECKPOINT - TDD ENFORCEMENT**: All US1 tests written and failing. Implementation may now begin.

### Implementation for User Story 1

- [X] T066 [P] [US1] Implement PDF text extraction in FileIngestionService: use PyMuPDF for native text PDFs, add OCR fallback with Tesseract for scanned PDFs
- [X] T067 [P] [US1] Implement DOCX parsing in FileIngestionService: use python-docx to extract text preserving headings, lists, and paragraph structure
- [X] T068 [P] [US1] Implement JSON chat backup parsing in FileIngestionService: use LangChain JSONLoader with JMESPath for Slack/Teams/WhatsApp exports
- [X] T069 [P] [US1] Implement markdown and plain text loading in FileIngestionService: use LangChain UnstructuredLoader
- [X] T070 [US1] Implement MIME type detection in FileIngestionService: use python-magic for file type validation, reject unsupported formats
- [X] T071 [US1] Implement SHA-256 hash calculation in FileIngestionService: hashlib.sha256() on file content, compare with existing FileVersion hashes
- [X] T072 [US1] Implement file validation in FileIngestionService: size limits (100MB for audio, 50MB for documents), format validation, corrupt file detection
- [X] T073 [US1] Create src/utils/file_watcher.py: watchdog-based file system monitor for ingestion folders, trigger ingestion on file creation
- [X] T074 [US1] Implement project extraction from file path in FileIngestionService: parse /ingest/{project_id}/ pattern or use default project
- [X] T075 [US1] Create src/api/routes/files.py: implement POST /api/v1/files/upload endpoint with multipart form data handling
- [X] T076 [US1] Implement duplicate file handling in files.py: return 409 Conflict with existing file_id if identical hash exists
- [X] T077 [US1] Implement GET /api/v1/files endpoint in files.py: list files with filters (project_id, source_type, mime_type, deleted)
- [X] T078 [US1] Implement GET /api/v1/files/{file_id} endpoint in files.py: return file details with version history and artifact links
- [X] T079 [US1] Implement DELETE /api/v1/files/{file_id} endpoint in files.py: soft delete (set deleted=true) with optional hard delete
- [X] T080 [US1] Implement GET /api/v1/files/{file_id}/versions endpoint in files.py: return all FileVersions with hashes and timestamps
- [X] T081 [US1] Implement POST /api/v1/files/{file_id}/reprocess endpoint in files.py: force file reprocessing through RAG pipeline
- [X] T082 [US1] Add file ingestion error handling: quarantine corrupt files to failed/ folder, log specific errors (password-protected PDF, invalid JSON)
- [X] T083 [US1] Add concurrency control in RAGPipeline: MAX_CONCURRENT_JOBS limit (default 3), queue management with FIFO priority

**Checkpoint**: Users can upload multiple file types, system processes automatically, files are queryable via API

---

## Phase 5: User Story 2 - Dual-Provider LLM Configuration (Priority: P1) 🧪

**Goal**: Users can select between OpenAI and Anthropic via environment configuration and compare provider outputs by switching LLM_PROVIDER_PREFERENCE

**Independent Test**: Set LLM_PROVIDER_PREFERENCE=openai→process test file→verify OpenAI used for all artifacts→switch to LLM_PROVIDER_PREFERENCE=anthropic→reprocess→verify Anthropic used→compare artifact quality

### Tests for User Story 2

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [ ] T084 [P] [US2] Unit test for LLMProviderFactory in tests/unit/test_llm_factory.py: test provider instantiation with openai and anthropic provider names, verify error handling for invalid provider names
- [ ] T085 [P] [US2] Integration test for OpenAI provider in tests/integration/test_openai_provider.py: test GPT-4o generation and embedding with real API, verify retry logic
- [ ] T086 [P] [US2] Integration test for Anthropic provider in tests/integration/test_anthropic_provider.py: test Claude generation with real API, verify retry logic
- [ ] T087 [P] [US2] Unit test for provider selection logic in tests/unit/test_provider_selection.py: test LLM_PROVIDER_PREFERENCE env var parsing, rules.yaml per-artifact override, default fallback to openai
- [ ] T088 [P] [US2] Integration test for provider error handling in tests/integration/test_provider_errors.py: test missing API key, invalid model name, provider unavailability raises clear error messages
- [ ] T089 [P] [US2] Integration test for provider switching in tests/integration/test_provider_switching.py: process file with LLM_PROVIDER_PREFERENCE=openai, switch to anthropic, reprocess, verify provider metadata in artifacts

**✅ CHECKPOINT - TDD ENFORCEMENT**: All US2 tests written and failing. Implementation may now begin.

### Implementation for User Story 2

- [ ] T090 [P] [US2] Implement OpenAI cost estimation in OpenAIProvider: calculate cost based on prompt_tokens, completion_tokens, and current pricing ($5/1M input, $15/1M output)
- [ ] T091 [P] [US2] Implement Anthropic cost estimation in AnthropicProvider: calculate cost based on Claude pricing ($3/1M input, $15/1M output)
- [ ] T092 [US2] Implement provider selection logic in RAGPipeline: read LLM_PROVIDER_PREFERENCE from env (default: openai), allow per-artifact override via rules.yaml
- [ ] T093 [US2] Add provider configuration validation on startup: verify LLM_PROVIDER_PREFERENCE is valid (openai|anthropic), selected provider's API key exists, raise clear error if misconfigured
- [ ] T094 [US2] Add provider metadata logging in JobRun.metrics: llm_provider, llm_model, tokens_used, cost_estimate for all LLM calls
- [ ] T095 [US2] Implement provider-specific retry logic: OpenAI (3 retries, exponential backoff over 5min), Anthropic (2 retries, linear backoff over 3min)
- [ ] T096 [US2] Add provider health checks in health endpoint: ping configured provider's API, report availability in /health response
- [ ] T097 [US2] Update config/rules.yaml with dual-provider examples: show LLM_PROVIDER_PREFERENCE usage, per-artifact override (OpenAI for summary, Anthropic for decisions)
- [ ] T098 [US2] Update .env.example with LLM_PROVIDER_PREFERENCE: document openai|anthropic options, default value, provider-specific configuration
- [ ] T099 [US2] Add error handling for provider unavailability: if selected provider fails, log error with clear guidance (check API key, check provider status), do NOT automatically switch providers

**Checkpoint**: System supports OpenAI and Anthropic as user-selectable alternatives via LLM_PROVIDER_PREFERENCE, with extensible architecture for future local model support

---

## Phase 6: User Story 3 - Declarative Artifact Generation with Plugins (Priority: P1) 📊

**Goal**: Users configure rules.yaml to declare which artifacts to generate (summary, decisions, entities) for which file types using which LLM providers

**Independent Test**: Define rule matching meetings→specify artifacts=[summary, decisions]→process meeting transcript→verify artifacts generated using correct providers→artifacts validate against schemas→artifacts linked to source file

### Tests for User Story 3

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [ ] T101 [P] [US3] Unit test for rules.yaml parsing in tests/unit/test_rules_parser.py: test YAML syntax validation, match criteria parsing
- [ ] T102 [P] [US3] Unit test for artifact generator plugin discovery in tests/unit/test_plugin_discovery.py: test auto-registration from src/services/artifact_generation/
- [ ] T103 [P] [US3] Contract test for POST /api/v1/artifacts in tests/contract/test_artifacts_contract.py: validate GET /api/v1/artifacts response against OpenAPI schema
- [ ] T104 [P] [US3] Integration test for summary generation in tests/integration/test_summary_generation.py: verify summary artifact created with correct structure
- [ ] T105 [P] [US3] Integration test for decisions extraction in tests/integration/test_decisions_generation.py: verify decisions artifact extracts decisor/decision/justification
- [ ] T106 [P] [US3] Integration test for entities extraction in tests/integration/test_entities_generation.py: verify entities artifact identifies people, teams, organizations
- [ ] T107 [P] [US3] Integration test for multi-file artifacts in tests/integration/test_multi_file_artifacts.py: verify weekly summary aggregates 5 meeting sources

**✅ CHECKPOINT - TDD ENFORCEMENT**: All US3 tests written and failing. Implementation may now begin.

### Implementation for User Story 3

- [ ] T108 [US3] Implement rules.yaml loader in RAGPipeline: parse YAML, validate syntax, cache in memory, support hot reload
- [ ] T109 [US3] Implement rule matching logic in RAGPipeline: match files against path_glob, mime_types, project_tags with first-match-wins strategy
- [ ] T110 [US3] Implement artifact generator plugin discovery in src/services/artifact_generation/base.py: scan *_generator.py files, register classes inheriting ArtifactGenerator
- [ ] T111 [US3] Implement artifact key generation in Artifact model: format {kind}:{project}:{identifier} (e.g., "summary:project-alpha:meeting-123")
- [ ] T112 [US3] Implement artifact versioning in ArtifactVersion: create new version when source changes or prompt template changes, set is_current flag
- [ ] T113 [US3] Implement artifact JSON schema validation: load schema from contracts/artifacts/{kind}.schema.json, validate LLM output structure
- [ ] T114 [US3] Implement ArtifactLink tracking in artifact generation: create links to all source FileVersions with role_type='source', track contribution weights for multi-file artifacts
- [ ] T115 [US3] Create src/api/routes/artifacts.py: implement GET /api/v1/artifacts with filters (artifact_key, kind, project_id, date range)
- [ ] T116 [US3] Implement GET /api/v1/artifacts/{artifact_id} endpoint in artifacts.py: return artifact with version history and source file links
- [ ] T117 [US3] Implement GET /api/v1/artifacts/{artifact_id}/versions/{version_id}/content endpoint in artifacts.py: return artifact content in JSON/markdown/text format
- [ ] T118 [US3] Implement GET /api/v1/artifacts/by-key/{artifact_key} endpoint in artifacts.py: retrieve artifact by composite key
- [ ] T119 [US3] Add artifact generation retry logic: if generation fails, mark artifact as failed, log error with prompt/response details, allow manual retry
- [ ] T120 [US3] Implement incremental artifact updates: when FileVersion changes, query ArtifactLinks to find dependent artifacts, regenerate only affected ones
- [ ] T121 [US3] Add prompt template management: store templates in src/services/prompts/{kind}_v{version}.txt, track template version in ArtifactVersion metadata
- [ ] T122 [US3] Create sample prompt templates: src/services/prompts/meeting_summary.txt, meeting_decisions.txt, meeting_entities.txt with variable substitution

**Checkpoint**: Declarative artifact generation working with plugin system, artifacts versioned and linked to sources

---

## Phase 7: User Story 4 - Pipeline Execution Tracking & Observability (Priority: P2) 📈

**Goal**: Users can view real-time job status in dashboard, drill into step-by-step logs, see performance metrics, retry failed jobs

**Independent Test**: Trigger multiple jobs (successful, failed, partial)→open dashboard→filter by status/date/project→click job for details→view step logs→click artifact links→retry failed job

### Tests for User Story 4

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [ ] T123 [P] [US4] Contract test for GET /api/v1/jobs in tests/contract/test_jobs_contract.py: validate job list response against OpenAPI schema
- [ ] T124 [P] [US4] Integration test for job tracking in tests/integration/test_job_tracking.py: verify JobRun and JobStep entities created for each pipeline execution
- [ ] T125 [P] [US4] Integration test for job metrics in tests/integration/test_job_metrics.py: verify chunks_created, embeddings_generated, llm_cost tracked accurately
- [ ] T126 [P] [US4] E2E test for job dashboard in tests/integration/test_job_dashboard.py: verify filtering, pagination, real-time updates

**✅ CHECKPOINT - TDD ENFORCEMENT**: All US4 tests written and failing. Implementation may now begin.

### Implementation for User Story 4

- [ ] T127 [US4] Implement JobRun creation in RAGPipeline: create JobRun with status='queued' on pipeline start, update status to running→success/failed/partial
- [ ] T128 [US4] Implement JobStep tracking in RAGPipeline: create JobStep for each pipeline step (normalize, chunk, embed, generate_{artifact_kind}), log step start/completion
- [ ] T129 [US4] Implement structured logging in JobStep.log_output: append JSON entries with timestamp, level, message, context for each operation
- [ ] T130 [US4] Implement job metrics collection in JobRun.metrics: track chunks_created, embeddings_generated, artifacts_produced, duration_seconds, llm_tokens_used, llm_cost_estimate
- [ ] T131 [US4] Create src/api/routes/jobs.py: implement GET /api/v1/jobs with filters (status, project_id, pipeline_name, start_date, end_date, pagination)
- [ ] T132 [US4] Implement GET /api/v1/jobs/{job_id} endpoint in jobs.py: return job details with all steps, logs, artifacts, metrics
- [ ] T133 [US4] Implement POST /api/v1/jobs/{job_id}/retry endpoint in jobs.py: create new JobRun for retry, optionally switch provider, support selective step retry
- [ ] T134 [US4] Implement GET /api/v1/jobs/{job_id}/steps/{step_id}/logs endpoint in jobs.py: return detailed step logs with filtering
- [ ] T135 [US4] Create src/ui/app.py: Streamlit main entry point with multi-page navigation
- [ ] T136 [US4] Create src/ui/pages/2_Jobs_Dashboard.py: Streamlit job list page with filters (status, date range, project), real-time updates with st.rerun()
- [ ] T137 [US4] Create src/ui/components/job_status_badge.py: Streamlit component for colored status badges (queued, running, success, failed, partial)
- [ ] T138 [US4] Implement job detail view in Jobs Dashboard: expandable job rows with step timeline, logs per step, output artifacts with preview links
- [ ] T139 [US4] Implement retry functionality in dashboard: "Retry" button for failed jobs, modal for provider selection
- [ ] T140 [US4] Add job metrics visualization in dashboard: bar charts for success rate, line chart for processing time trend, cost breakdown by provider
- [ ] T141 [US4] Implement real-time job status polling in dashboard: auto-refresh every 5 seconds for running jobs, st.progress() for completion percentage

**Checkpoint**: Full observability dashboard with job tracking, detailed logs, metrics, and retry capability

---

## Phase 8: User Story 5 - Intelligent RAG Chat with Citations (Priority: P3) 💬

**Goal**: Users ask questions in natural language, system retrieves relevant chunks (meetings + documents), LLM generates answer with speaker-aware citations

**Independent Test**: Ingest corpus with known content→ask questions with expected answers→verify correct chunks retrieved (recall >70%)→verify citations accurate (speaker/timestamp for meetings, file/page for documents)→verify low-confidence queries return "no information found"

### Tests for User Story 5

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [ ] T142 [P] [US5] Contract test for POST /api/v1/chat/query in tests/contract/test_chat_contract.py: validate ChatQueryRequest and ChatResponse against OpenAPI schema
- [ ] T143 [P] [US5] Integration test for RAG retrieval in tests/integration/test_rag_retrieval.py: verify top-K similar chunks retrieved with correct metadata
- [ ] T144 [P] [US5] Integration test for citation generation in tests/integration/test_citation_generation.py: verify citations include source_type, file_path, speaker (meetings), page (documents)
- [ ] T145 [P] [US5] Integration test for low-confidence queries in tests/integration/test_low_confidence.py: verify similarity < threshold returns "I don't have information about that"
- [ ] T146 [P] [US5] E2E test for chat flow in tests/integration/test_chat_e2e.py: ingest test corpus, submit query, verify answer accuracy and citation correctness

**✅ CHECKPOINT - TDD ENFORCEMENT**: All US5 tests written and failing. Implementation may now begin.

### Implementation for User Story 5

- [ ] T147 [US5] Create src/services/chat_service.py: RAG query service with embedding generation, vector retrieval, context assembly, LLM answer generation
- [ ] T148 [US5] Implement query embedding in ChatService: use same embedding model as indexed content, validate model consistency
- [ ] T149 [US5] Implement vector retrieval in ChatService: call ChromaDB.query() with top_k, metadata filters (project_id, date_range), cosine similarity
- [ ] T150 [US5] Implement context assembly in ChatService: retrieve chunks with metadata (speaker, timestamp, file_path, page), format for LLM input
- [ ] T151 [US5] Implement citation extraction in ChatService: parse LLM response for source references, map to chunk metadata, generate clickable citations
- [ ] T152 [US5] Implement low-confidence handling in ChatService: if max_similarity < threshold (default 0.6), return "I don't have information about that" without hallucination
- [ ] T153 [US5] Implement speaker-aware citations for meetings: format as "According to {speaker_name} at {timestamp}" with clickable link to transcript
- [ ] T154 [US5] Implement document citations: format as "{file_path} page {page}, section {section}" with clickable link to file
- [ ] T155 [US5] Create src/api/routes/chat.py: implement POST /api/v1/chat/query endpoint with ChatQueryRequest validation
- [ ] T156 [US5] Implement experimental mode in chat.py: when enabled, generate answers from all configured providers, return comparison view
- [ ] T157 [US5] Create src/ui/pages/3_Chat.py: Streamlit chat interface with st.chat_input(), st.chat_message(), conversation history in session_state
- [ ] T158 [US5] Implement citation rendering in chat UI: display citations as expandable cards with source preview, speaker highlighting for meetings
- [ ] T159 [US5] Implement project filter in chat UI: dropdown to scope retrieval to specific project
- [ ] T160 [US5] Implement advanced query options in chat UI: sliders for top_k (1-50), min_similarity (0.0-1.0), provider selection
- [ ] T161 [US5] Add query history tracking: store queries in session_state, display recent queries with click to re-run
- [ ] T162 [US5] Implement context preview in citations: show chunk text excerpt, highlight query keywords
- [ ] T163 [US5] Add embeddings immediately available after ingestion: ensure ChromaDB persists to disk after each batch, verify new chunks queryable within 1 minute

**Checkpoint**: RAG chat working with accurate citations, speaker metadata preserved, low-confidence queries handled gracefully

---

## Phase 9: User Story 6 - Backfill for Historical Data (Priority: P3) 🔄

**Goal**: Users trigger backfill job for folder or file list, system processes in batches with progress tracking, pause/resume/cancel controls

**Independent Test**: Place 50 test files in folder→trigger backfill via API→monitor dashboard progress→pause mid-execution→verify queued jobs remain→resume→verify processing continues→check summary report on completion

### Tests for User Story 6

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [ ] T164 [P] [US6] Contract test for POST /api/v1/backfill in tests/contract/test_backfill_contract.py: validate BackfillRequest and BackfillResponse against OpenAPI schema
- [ ] T165 [P] [US6] Integration test for backfill discovery in tests/integration/test_backfill_discovery.py: verify recursive folder scan discovers all matching files
- [ ] T166 [P] [US6] Integration test for backfill progress tracking in tests/integration/test_backfill_progress.py: verify processed_count, progress_percentage updated accurately
- [ ] T167 [P] [US6] Integration test for backfill controls in tests/integration/test_backfill_controls.py: test pause, resume, cancel operations

**✅ CHECKPOINT - TDD ENFORCEMENT**: All US6 tests written and failing. Implementation may now begin.

### Implementation for User Story 6

- [ ] T168 [US6] Implement backfill file discovery in BackfillService: recursive directory scan with glob pattern filtering, hash calculation, IngestionEvent creation
- [ ] T169 [US6] Implement backfill progress tracking: update BackfillJob.processed_count, failed_count, progress_percentage after each file completes
- [ ] T170 [US6] Implement backfill concurrency control: respect MAX_CONCURRENT_JOBS limit, queue management with backfill_job_id tagging
- [ ] T171 [US6] Implement backfill rate limiting: monitor API quota usage (OpenAI TPM), pause when quota exceeded, wait for cooldown, resume automatically
- [ ] T172 [US6] Create src/api/routes/backfill.py: implement POST /api/v1/backfill endpoint with folder or file_list input
- [ ] T173 [US6] Implement GET /api/v1/backfill endpoint in backfill.py: list backfill jobs with status filtering
- [ ] T174 [US6] Implement GET /api/v1/backfill/{backfill_job_id} endpoint in backfill.py: return detailed progress with estimated_completion_time
- [ ] T175 [US6] Implement POST /api/v1/backfill/{backfill_job_id}/pause endpoint in backfill.py: stop queueing new jobs, let running jobs finish
- [ ] T176 [US6] Implement POST /api/v1/backfill/{backfill_job_id}/resume endpoint in backfill.py: continue from pause point
- [ ] T177 [US6] Implement POST /api/v1/backfill/{backfill_job_id}/cancel endpoint in backfill.py: stop immediately, mark remaining as skipped
- [ ] T178 [US6] Implement backfill summary report generation: on completion, populate BackfillJob.summary_report with success/failure breakdown, artifacts generated, total cost
- [ ] T179 [US6] Implement GET /api/v1/backfill/{backfill_job_id}/summary endpoint in backfill.py: return summary report in JSON or CSV format
- [ ] T180 [US6] Add backfill monitoring in dashboard: display backfill jobs with progress bars, processing rate (files/min), estimated time remaining
- [ ] T181 [US6] Add failed file report in dashboard: downloadable CSV with file paths, error reasons for debugging

**Checkpoint**: Backfill operations working with discovery, progress tracking, pause/resume/cancel, summary reports

---

## Phase 10: User Story 7 - Change Detection & Incremental Updates (Priority: P2) 🔍

**Goal**: System detects file changes via SHA-256 hash, creates new FileVersion, regenerates only affected artifacts, preserves version history

**Independent Test**: Ingest file and generate artifacts→modify file content→save to same location→verify hash diff detected→new FileVersion created→only dependent artifacts regenerated→old versions preserved→version history accurate

### Tests for User Story 7

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [ ] T182 [P] [US7] Integration test for change detection in tests/integration/test_change_detection.py: upload file twice with different content, verify new FileVersion created only for changed content
- [ ] T183 [P] [US7] Integration test for incremental artifact updates in tests/integration/test_incremental_artifacts.py: modify source file, verify only affected artifacts regenerated
- [ ] T184 [P] [US7] Integration test for version history in tests/integration/test_version_history.py: verify all FileVersions linked to parent File with correct timestamps

**✅ CHECKPOINT - TDD ENFORCEMENT**: All US7 tests written and failing. Implementation may now begin.

### Implementation for User Story 7

- [ ] T185 [US7] Implement hash comparison in FileIngestionService: calculate SHA-256 of new content, query latest FileVersion.content_hash, compare for changes
- [ ] T186 [US7] Implement FileVersion creation on change: if hash differs, create new FileVersion with is_current=true, set old version is_current=false
- [ ] T187 [US7] Implement affected artifact detection: query ArtifactLinks for artifacts with links to updated FileVersion, flag for regeneration
- [ ] T188 [US7] Implement incremental embedding updates: delete old chunks for updated FileVersion from ChromaDB (soft delete in DB: Chunk.deleted=true), generate new chunks and embeddings
- [ ] T189 [US7] Implement artifact regeneration: create new ArtifactVersions for affected artifacts, preserve old versions with timestamps
- [ ] T190 [US7] Implement version comparison API: GET /api/v1/files/{file_id}/versions/{v1}/compare/{v2} returns text diff between versions
- [ ] T191 [US7] Add version history UI in dashboard: display all FileVersions for file with timestamps, hashes, diff buttons, artifact links per version
- [ ] T192 [US7] Add soft delete handling: when File.deleted=true, exclude embeddings from ChromaDB queries unless explicitly requested via include_deleted parameter
- [ ] T193 [US7] Implement hard delete operation: when triggered, purge FileVersions, Chunks, Embeddings (from ChromaDB), ArtifactLinks without leaving orphaned records

**Checkpoint**: Change detection working, incremental updates efficient, version history preserved

---

## Phase 11: Polish & Cross-Cutting Concerns

**Purpose**: Final improvements, documentation, and production readiness

- [ ] T194 [P] Create comprehensive README.md with project overview, architecture diagram, quick start guide, environment setup
- [ ] T195 [P] Create GETTING_STARTED.md with step-by-step instructions: install dependencies, configure environment, run migrations, start services
- [ ] T196 [P] Add API documentation: generate OpenAPI docs from FastAPI with descriptions for all endpoints, serve at /docs
- [ ] T197 [P] Create src/api/routes/health.py: implement GET /health endpoint with database, ChromaDB, LLM provider health checks
- [ ] T198 [P] Create src/api/routes/projects.py: implement CRUD endpoints for Project management (GET, POST, PUT, DELETE)
- [ ] T199 [P] Create src/api/routes/rules.py: implement GET /api/v1/rules, POST /api/v1/rules/reload, POST /api/v1/rules/validate
- [ ] T200 [P] Implement rules reload without restart: POST /api/v1/rules/reload triggers re-parsing of rules.yaml, validates syntax, updates in-memory cache
- [ ] T201 [P] Add Streamlit file upload page: src/ui/pages/1_File_Upload.py with drag-and-drop uploader, project selection, upload progress
- [ ] T202 [P] Add Streamlit artifacts browser: src/ui/pages/4_Artifacts.py with artifact search, version history, content preview, download
- [ ] T203 [P] Create src/ui/components/citation_card.py: reusable Streamlit component for rendering citations with source preview
- [ ] T204 [P] Add conversation history API: GET /api/v1/chat/conversations for tracking query history (future enhancement for multi-turn chat)
- [ ] T205 Code cleanup and refactoring: remove dead code, consolidate duplicate logic, improve error messages
- [ ] T206 Performance optimization: add database indexes per data-model.md, optimize ChromaDB batch sizes, tune chunk sizes
- [ ] T207 Security hardening: validate all API inputs with Pydantic, sanitize file paths, implement rate limiting on upload endpoints
- [ ] T208 Add unit tests for models: tests/unit/models/ for all entity validation rules, CheckConstraints, relationships
- [ ] T209 Add unit tests for utilities: tests/unit/utils/ for logging, retry logic, exceptions, validators
- [ ] T210 Run quickstart.md validation: follow guide from scratch on clean system, verify all steps work, update as needed
- [ ] T211 Generate test coverage report: pytest --cov=src --cov-report=html, ensure >80% coverage for core services
- [ ] T212 Create deployment guide: document Docker Compose deployment, environment variables, data persistence, backup procedures
- [ ] T213a [P] Create cost tracking dashboard in src/ui/pages/5_Cost_Tracking.py: display LLM costs per provider, embedding costs, storage growth, compare against success criteria SC-044 to SC-050
- [ ] T213 Add monitoring and alerting documentation: guide for tracking job success rates, API latency, LLM costs
- [ ] T214 Create troubleshooting guide: common errors (ChromaDB connection failed, LLM API quota exceeded, corrupt files), solutions

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3-10)**: All depend on Foundational phase completion
  - US0 can start after Foundational (validates existing pipeline integration)
  - US1, US2, US3 can proceed in parallel after US0 (all P1 - co-MVP)
  - US4, US7 can proceed in parallel (P2)
  - US5, US6 can proceed in parallel (P3)
- **Polish (Phase 11)**: Depends on all desired user stories being complete

### User Story Dependencies

- **US0 (P0)**: Prerequisite - validates existing Meeting→Deepgram→RAG bridge
- **US1 (P1)**: File ingestion - no dependencies on other stories
- **US2 (P1)**: Multi-provider LLMs - no dependencies on other stories
- **US3 (P1)**: Artifact generation - depends on US1 (file ingestion) and US2 (LLM providers)
- **US4 (P2)**: Observability - can start anytime, enhances all other stories
- **US5 (P3)**: RAG chat - depends on US1 (ingestion), US2 (LLMs), embeddings from foundational
- **US6 (P3)**: Backfill - depends on US1 (ingestion), uses same pipeline
- **US7 (P2)**: Change detection - depends on US1 (ingestion), US3 (artifacts)

### Within Each User Story

- Tests MUST be written and FAIL before implementation (TDD)
- Models before services
- Services before API endpoints
- API before UI
- Core implementation before integration
- Story complete before moving to next priority

### Parallel Opportunities

- All Setup tasks marked [P] can run in parallel (T002-T010)
- All Foundational tasks marked [P] can run in parallel within categories:
  - Models (T014-T022)
  - LLM providers (T025-T027)
  - Chunking strategies (T032-T033)
  - Artifact generators (T035-T037)
  - Pydantic schemas (T044-T047)
- Once Foundational completes, US0→US1→US2→US3 can start (P1 MVP track)
- US4, US7 can work in parallel (P2 enhancements)
- US5, US6 can work in parallel (P3 advanced features)
- All tests within a story marked [P] can run in parallel
- Polish tasks (T194-T214) can mostly run in parallel

---

## Implementation Strategy

### MVP First (US0 + US1 + US2 + US3)

1. Complete Phase 1: Setup (T001-T010)
2. Complete Phase 2: Foundational (T011-T047) - CRITICAL
3. Complete Phase 3: US0 (T048-T059) - Validate existing integration
4. Complete Phase 4: US1 (T060-T083) - File ingestion working
5. Complete Phase 5: US2 (T084-T100) - Multi-provider LLMs working
6. Complete Phase 6: US3 (T101-T122) - Artifact generation working
7. **STOP and VALIDATE**: Test P1 stories independently, verify MVP functionality
8. Deploy/demo if ready

### Incremental Delivery

1. Setup + Foundational → Foundation ready
2. Add US0 → Test independently → Validate existing pipeline integration
3. Add US1 → Test independently → File ingestion working
4. Add US2 → Test independently → Multi-provider support working
5. Add US3 → Test independently → Declarative artifacts working (MVP COMPLETE!)
6. Add US4 → Test independently → Observability added
7. Add US7 → Test independently → Change detection added
8. Add US5 → Test independently → RAG chat added
9. Add US6 → Test independently → Backfill capability added
10. Polish → Production ready

### Parallel Team Strategy

With multiple developers after Foundational phase completes:

- **Developer A**: US0 (P0) → US1 (P1) → US5 (P3)
- **Developer B**: US2 (P1) → US4 (P2) → US6 (P3)
- **Developer C**: US3 (P1) → US7 (P2) → Polish

---

## Notes

- **[P]** tasks = different files, no dependencies, can run in parallel
- **[Story]** label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Tests written FIRST (TDD), ensure they FAIL before implementing
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- File paths are absolute from repository root (e.g., src/models/file.py)
- Constitution compliance: comprehensive testing, production quality, observability
- Total tasks: 214 (Setup: 10, Foundational: 37, US0: 12, US1: 24, US2: 17, US3: 21, US4: 19, US5: 22, US6: 18, US7: 13, Polish: 21)

---

## Summary

This task breakdown enables:
- **Independent user stories**: Each story (US0-US7) can be implemented and tested independently
- **MVP focus**: P0 + P1 stories (US0, US1, US2, US3) deliver core value
- **Incremental delivery**: Each completed story adds value without breaking previous stories
- **Parallel development**: Multiple developers can work on different stories simultaneously after foundational phase
- **Clear checkpoints**: Validation points after each phase ensure quality
- **Constitution compliance**: Tests included, production readiness emphasized, observability throughout
