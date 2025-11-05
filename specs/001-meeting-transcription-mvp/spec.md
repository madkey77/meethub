# Feature Specification: RAG-Enhanced Meeting Intelligence System

**Feature Branch**: `001-meeting-transcription-mvp`
**Created**: 2025-11-04
**Updated**: 2025-11-04
**Status**: Draft - Extension of Existing System
**Input**: Extend existing Google Meet + Deepgram transcription system (KEEP all existing services) to add RAG capabilities with multi-provider LLM support and modular architecture for experimentation

## Overview

This specification extends the existing Google Meet + Deepgram transcription infrastructure to add Retrieval-Augmented Generation (RAG) capabilities. The system will continue to automatically pull meeting recordings from Google Meet, transcribe them with Deepgram (preserving speaker diarization and timestamps), and now additionally process these transcriptions—along with manually uploaded documents—through a RAG pipeline for intelligent querying, artifact generation, and cross-source knowledge retrieval.

**Key Extension Points**:
1. **KEEP**: All existing Google Meet polling, recording downloads, Deepgram transcription with speaker diarization
2. **ADD**: Bridge layer to map Meeting transcriptions → RAG ingestion pipeline
3. **ADD**: File ingestion for uploaded documents (PDF, DOCX, markdown, JSON)
4. **ADD**: Dual-provider LLM architecture (OpenAI and Anthropic) with user-selectable configuration and extensible design for future local model support
5. **ADD**: Modular plugin system for artifact generators, chunking strategies, embedding providers
6. **ADD**: Chat interface for unified queries across meetings + documents with citations

**Evolution Path**: This builds incrementally on the proven meeting transcription MVP, adding RAG as a complementary enhancement layer rather than a replacement.

## User Scenarios & Testing *(mandatory)*

### User Story 0 - Meeting Pipeline Integration Foundation (Priority: P0 - Prerequisite)

The existing Google Meet integration automatically detects when team meetings end, downloads recordings from Google Drive, and transcribes them using Deepgram with speaker attribution and timestamps. This foundation layer continues to work exactly as it does today, but now also triggers RAG ingestion: transcriptions are automatically chunked (preserving speaker and timestamp metadata), embedded using configured LLM providers, and made available for intelligent querying alongside manually uploaded documents.

**Why this priority**: This is the proven foundation that already works. P0 means it's a prerequisite—the system must preserve and extend this capability, not replace it.

**Independent Test**: Can be tested by verifying existing end-to-end flow still works: Google Meet API detects ended meeting → recording downloads → Deepgram transcribes with speakers → NEW: transcript auto-ingests into RAG pipeline → chunks are created with speaker metadata → embeddings are generated → transcript is queryable via chat.

**Acceptance Scenarios**:

1. **Given** a meeting ends in Google Meet, **When** scheduler runs, **Then** meeting is detected, recording is downloaded, Deepgram transcription completes with speaker diarization, and RAG ingestion is automatically triggered
2. **Given** a transcript is generated, **When** RAG bridge processes it, **Then** FileVersion record is created, chunks preserve speaker and timestamp metadata, embeddings are stored in vector database
3. **Given** meeting chunks exist with speaker metadata, **When** user queries "What did Alice say about deployment?", **Then** system retrieves relevant chunks filtered by speaker, returns answer with citations including speaker name and timestamp
4. **Given** transcription fails (API error, timeout), **When** error occurs, **Then** system logs detailed error with meeting context, marks job as failed, notifies user, and does not create incomplete RAG records
5. **Given** same meeting is re-transcribed (user retry), **When** new transcript is generated, **Then** system detects content change via hash, creates new FileVersion, preserves old version for audit, re-processes through RAG pipeline

---

### User Story 1 - Manual File Ingestion with Multi-Source Processing (Priority: P1)

A team lead wants to query not just meeting transcriptions but also uploaded project documents (architecture PDFs, decision logs in markdown, chat exports in JSON). They drop files into monitored folders or upload via API. The system automatically detects file types, extracts text content, processes files through the same RAG pipeline as meeting transcriptions, and makes all content queryable together. Users can ask "What did we decide about Kubernetes?" and get answers citing both meeting transcriptions (with speaker/timestamp) and uploaded documents (with file path and location).

**Why this priority**: Core value proposition—unified knowledge retrieval across heterogeneous sources. This is co-P1 with artifact generation because file ingestion is the input, artifacts are the intelligent output.

**Independent Test**: Can be fully tested by uploading files of different types (PDF, DOCX, markdown, JSON) to monitored folders, verifying text extraction succeeds, chunks are created with appropriate metadata, embeddings are generated, and files are queryable via chat interface with accurate citations.

**Acceptance Scenarios**:

1. **Given** a PDF document is uploaded to monitored folder, **When** file watcher detects it, **Then** file is queued for ingestion, text is extracted (with OCR fallback for scanned PDFs), chunks are created, embeddings are generated, and document appears as queryable within 2 minutes
2. **Given** multiple files arrive simultaneously (20 files), **When** ingestion processes them, **Then** jobs run in parallel respecting concurrency limits (default 3), all files complete independently, no file blocks others, and dashboard shows real-time progress
3. **Given** a DOCX file is uploaded, **When** processing occurs, **Then** text extraction preserves paragraph structure, metadata includes original formatting markers (headings, lists), chunks maintain logical boundaries
4. **Given** a JSON chat backup (Slack export) is uploaded, **When** parser processes it, **Then** messages are extracted with sender and timestamp, conversation threads are preserved in chunk metadata, and format is compatible with meeting transcript structure
5. **Given** same file is re-uploaded (identical SHA-256 hash), **When** system checks for changes, **Then** duplicate detection skips reprocessing, no new FileVersion is created, user is notified of duplicate, and original embeddings remain available

---

### User Story 2 - LLM Provider Selection and Comparison (Priority: P1)

A researcher wants to select between OpenAI GPT-4o and Anthropic Claude for generating meeting summaries and decision indexes, and compare their outputs. They can switch providers via environment configuration (LLM_PROVIDER_PREFERENCE=openai|anthropic) or configure rules.yaml to use different providers for different artifact types. The system processes artifacts using the selected provider(s), stores results with provider metadata (model name, tokens used, latency, cost), and allows side-by-side comparison when both are configured. The researcher can evaluate which provider gives better quality, lower cost, or faster responses for their specific use case, then select their preferred provider for production use.

**Why this priority**: Critical for the "experimental and we need to prototype fast" requirement. Provider abstraction prevents vendor lock-in and enables experimentation. This is P1 because the architecture must support easy provider switching from day one, and OpenAI/Anthropic offer different quality/cost trade-offs.

**Independent Test**: Can be tested by (1) setting LLM_PROVIDER_PREFERENCE=openai in .env, ingesting file, verifying OpenAI used; (2) changing to anthropic, reprocessing, verifying Anthropic used; (3) configuring rules.yaml with both providers for same artifact type, verifying parallel generation and comparison view in dashboard.

**Acceptance Scenarios**:

1. **Given** LLM_PROVIDER_PREFERENCE=openai in .env and OpenAI API key configured, **When** a meeting transcript is processed, **Then** system uses OpenAI GPT-4o for all artifact generation, logs show OpenAI provider metadata (model, tokens, cost), artifacts are generated successfully
2. **Given** user changes LLM_PROVIDER_PREFERENCE=anthropic and restarts system, **When** new transcript is processed, **Then** system uses Anthropic Claude for all artifacts, logs show Anthropic metadata, user can compare outputs from both providers
3. **Given** rules.yaml specifies OpenAI for summaries and Anthropic for decisions, **When** meeting is processed, **Then** summary uses GPT-4o, decisions use Claude, metadata logs show distinct provider usage per artifact type
4. **Given** rules.yaml configures both OpenAI and Anthropic for summary generation (experimental mode), **When** transcript is processed, **Then** both providers generate summaries in parallel, artifacts are stored with provider tags, dashboard shows side-by-side comparison with quality/cost/latency metrics
5. **Given** selected provider's API key is missing or invalid, **When** system starts or artifact generation is attempted, **Then** system throws clear error message ("OPENAI_API_KEY not configured. Set LLM_PROVIDER_PREFERENCE and corresponding API key."), suggests corrective action, does not fail silently

---

### User Story 3 - Declarative Artifact Generation with Plugins (Priority: P1)

A team configures rules in YAML stating: "For meeting transcriptions, generate: summary, decisions index, action items, and sentiment analysis. Use GPT-4o for summaries, Claude for decisions, and local Mistral for sentiment." When meetings are transcribed, the system automatically generates all specified artifacts using the configured providers, validates outputs against JSON schemas, links artifacts to source transcriptions, and makes them browsable in the dashboard. Users can view meeting summaries without re-listening to recordings, search for specific decisions across all meetings, and track action items assigned during discussions.

**Why this priority**: Artifacts are the intelligent output—the "why RAG" value proposition. Declarative rules enable experimentation without code changes. Plugin system enables adding new artifact types (e.g., "risks", "technical debt mentions") without touching core pipeline. Co-P1 with file ingestion because ingestion provides input, artifacts provide output.

**Independent Test**: Can be tested by defining rules matching specific file patterns with multiple artifact types, ingesting matching files, verifying all declared artifacts are generated using correct providers, artifacts validate against schemas, and are linked to source files with full version history.

**Acceptance Scenarios**:

1. **Given** a rule matches `meetings/**/*.md` with artifacts `[summary, decisions, action_items]`, **When** a matching transcript is ingested, **Then** all three artifacts are generated in parallel, each uses configured LLM provider, outputs validate against schemas, and artifacts are linked to FileVersion with role='derived_from'
2. **Given** artifact generation fails (LLM timeout, invalid JSON output), **When** failure occurs, **Then** specific artifact is marked failed, other artifacts continue processing, error is logged with prompt/response details, and user can retry failed artifact without reprocessing whole file
3. **Given** source file is updated (new version), **When** change is detected via SHA-256 hash, **Then** only artifacts depending on that file are flagged for regeneration, incremental update creates new ArtifactVersions, old versions are preserved with timestamps
4. **Given** user creates custom artifact generator plugin (e.g., "technical_risks.py"), **When** plugin is placed in src/services/artifacts/ and registered, **Then** new artifact type appears in rules.yaml autocomplete, can be configured like built-in types, and is invoked during pipeline execution
5. **Given** artifact depends on multiple source files (e.g., weekly summary aggregating 5 meetings), **When** any source file changes, **Then** dependent artifact is flagged for regeneration with updated data, all source file links are maintained in ArtifactLinks table

---

### User Story 4 - Pipeline Execution Tracking & Observability (Priority: P2)

An operations engineer opens the execution dashboard and sees real-time status of all ingestion jobs: meetings being transcribed, files being processed, artifacts being generated. Each job shows detailed step-by-step progress (file detected → text extracted → chunked → embedded → artifacts generated), logs for each step, input files, output artifacts, and performance metrics (duration, tokens used, cost per job). When a job fails, the engineer can see exactly which step failed, view error details, compare with successful jobs, and trigger retry with one click.

**Why this priority**: Observability is essential for debugging production issues and understanding system behavior, but the core ingestion/artifact generation must work first. P2 because it's critical for production use but not blocking MVP functionality.

**Independent Test**: Can be tested by triggering various job types (successful, failed, partial), opening dashboard UI, applying filters (status, date range, project), drilling into job details, verifying logs/metrics are accurate, clicking artifact links, and using retry functionality.

**Acceptance Scenarios**:

1. **Given** multiple jobs are running, **When** user opens dashboard, **Then** jobs are listed with real-time status updates (queued → running → success/failed), progress bars show completion percentage, estimated time remaining is displayed, and list auto-refreshes every 5 seconds
2. **Given** user clicks on a job, **When** detail view loads, **Then** it displays: input files with download links, step-by-step timeline with status icons, logs for each step (collapsed by default, expandable), output artifacts with preview links, and performance metrics (duration, LLM tokens/cost)
3. **Given** job failed at embedding step, **When** engineer views details, **Then** failure step is highlighted in red, error message explains root cause (e.g., "OpenAI API quota exceeded"), related logs show full context, and "Retry" button appears with option to switch provider
4. **Given** user wants to debug slow jobs, **When** they filter by duration >5min, **Then** dashboard shows slowest jobs, performance breakdown by step (e.g., "embedding: 3.2min, artifact generation: 1.8min"), and comparison with average durations for similar file types
5. **Given** artifact is clicked in job view, **When** user navigates, **Then** artifact content is displayed with syntax highlighting (JSON), source file links are clickable, version history is shown, and artifact is downloadable in markdown or JSON format

---

### User Story 5 - Intelligent RAG Chat with Citations (Priority: P3)

A product manager opens the chat interface and asks: "What did we decide about the deployment strategy, and what does the architecture document say about scalability?" The system searches across all ingested content (meeting transcriptions with speaker metadata + uploaded documents), retrieves top-K relevant chunks using vector similarity, assembles context with source information, sends to configured LLM (e.g., GPT-4o) for answer generation, and returns a response with inline citations. Citations are clickable links showing: for meetings, the speaker and timestamp; for documents, the file path and page/section. If no relevant content is found (low similarity scores), the system responds "I don't have information about that" instead of hallucinating.

**Why this priority**: Chat is the ultimate user-facing value—conversational access to organizational knowledge. However, it depends on ingestion (P1), artifacts (P1), and embeddings working first. P3 because the system is useful without chat (users can browse artifacts), but chat makes it truly powerful.

**Independent Test**: Can be tested by ingesting test corpus with known content, asking questions with expected answers, verifying correct chunks are retrieved (recall >70%), LLM responses are accurate and grounded in sources, citations point to correct files/locations, and low-confidence queries return "no information found".

**Acceptance Scenarios**:

1. **Given** user asks "Who decided to use Kubernetes for deployment?", **When** query is processed, **Then** system generates embedding for query, retrieves top-10 chunks by similarity (meeting: 0.89, doc: 0.87), assembles context with source metadata, sends to LLM, and returns "According to Alice in the standup on 2025-11-01 at 14:32, the team decided to use Kubernetes for deployment. The decision is also documented in architecture.pdf page 12."
2. **Given** query spans multiple sources (meeting + document), **When** context is assembled, **Then** chunks are ranked by similarity regardless of source type, citations clearly differentiate source format (meeting: speaker/timestamp, document: file/page), and answer synthesizes information from all sources
3. **Given** no relevant content exists (similarity scores all <0.6), **When** system evaluates retrieval, **Then** it responds "I don't have information about that in the indexed content. Try rephrasing your question or check if relevant meetings/documents have been uploaded.", prevents hallucination, and logs low-confidence query for analysis
4. **Given** user clicks a citation to a meeting, **When** navigation occurs, **Then** meeting detail page opens, transcript is displayed with cited section highlighted, video player (if available) seeks to cited timestamp, and speaker is visually indicated
5. **Given** user enables "experimental" mode with multiple LLM providers, **When** query is submitted, **Then** system generates answers from all configured providers, displays comparison view with responses side-by-side, shows latency and token cost per provider, and user can select preferred response

---

### User Story 6 - Backfill for Historical Data (Priority: P3)

A team has 200 historical meeting recordings already transcribed and stored. They configure RAG ingestion rules and trigger a backfill job to reprocess all existing transcriptions. The system discovers all files in specified folders, queues ingestion events respecting rate limits and concurrency settings, processes files in batches, generates configured artifacts for each, and updates the dashboard with progress. The backfill job can be paused (current jobs complete, queued remain), resumed later, or cancelled entirely. On completion, a summary report shows: success count, failure count, artifacts generated, total duration, and links to failed jobs for investigation.

**Why this priority**: Backfill is essential for migrating existing data into the new RAG system, but it's a one-time or periodic operation, not core to daily workflow. P3 because real-time ingestion (P1) must work first, and backfill uses the same pipeline but in batch mode.

**Independent Test**: Can be tested by placing large batch of test files (50-100) in a folder, triggering backfill via API, monitoring dashboard as files process concurrently, pausing and resuming mid-execution, verifying all files eventually process (success or logged failure), and checking artifacts are generated correctly.

**Acceptance Scenarios**:

1. **Given** user triggers backfill for `/historical_meetings/` containing 200 transcriptions, **When** backfill starts, **Then** all files are discovered, ingestion events are created with metadata (backfill_job_id, sequence_number), jobs are queued respecting global concurrency limit (3 concurrent), and dashboard shows "Backfill: 0/200 processed"
2. **Given** backfill is running, **When** monitoring progress, **Then** dashboard displays: total file count, processed count, failed count, current processing rate (files/min), estimated time remaining (based on average duration), and real-time log stream of completed files
3. **Given** OpenAI API quota is hit during backfill, **When** rate limit error occurs, **Then** backfill pauses automatically, waits for configured cooldown period (5 minutes), logs rate limit event, and resumes processing remaining files after cooldown
4. **Given** user pauses backfill, **When** pause command is issued via API, **Then** currently running jobs complete normally, queued jobs remain in queue with status "paused", no new jobs start, and dashboard shows "Backfill Paused: 87/200 processed, 113 remaining"
5. **Given** backfill completes, **When** final summary is generated, **Then** report shows: success count (195), failure count (5), artifacts generated (195 summaries, 195 decisions, etc.), total duration (2h 14min), average processing time per file (40s), total LLM cost ($23.50), and downloadable CSV of failed files with error reasons

---

### User Story 7 - Change Detection & Incremental Updates (Priority: P2)

A user updates a meeting transcription file to add notes or corrections. The system detects the content change via SHA-256 hash comparison, creates a new FileVersion record linked to the parent File, and re-runs only the affected pipeline steps (chunking, embedding, artifact generation). Artifacts that depend solely on this file are regenerated as new ArtifactVersions; artifacts based on other files remain unchanged. The version history view shows all file versions with timestamps, hashes, and links to artifacts generated from each version, enabling audit trails and rollback if needed.

**Why this priority**: Incremental processing is crucial for efficiency—reprocessing everything on every change wastes compute and time. P2 because initial ingestion (P1) must work first, and change detection is an optimization that becomes critical as data volume grows.

**Independent Test**: Can be tested by ingesting a file and generating artifacts, modifying file content, saving to same location, verifying system detects change via hash diff, creates new FileVersion, reprocesses only that file, updates dependent artifacts while preserving old versions, and version history is accurate.

**Acceptance Scenarios**:

1. **Given** file has been ingested with SHA-256 hash `abc123`, **When** file content changes and hash becomes `def456`, **Then** system detects difference, creates new FileVersion with new hash, old version remains linked to parent File with is_current=false, and ingestion event is triggered for new version
2. **Given** file version update occurs, **When** artifact regeneration is evaluated, **Then** only artifacts with ArtifactLink pointing to updated FileVersion are flagged for regeneration (e.g., summary, decisions for that specific file), artifacts from other files are unaffected
3. **Given** artifact depends on multiple files (e.g., weekly summary aggregating 5 meetings), **When** one source file changes, **Then** artifact is marked for regeneration, new ArtifactVersion is created, all source file links are updated in ArtifactLinks table to reflect mix of old and new versions
4. **Given** user views file version history, **When** accessing File detail page, **Then** all versions are listed chronologically with: timestamps, SHA-256 hashes (abbreviated), file size, links to artifacts generated from each version, and "diff" button to compare versions
5. **Given** file is deleted from monitored folder, **When** deletion is detected, **Then** File.deleted=true is set (soft delete), all FileVersions remain in database for audit, embeddings remain in vector store but are excluded from future queries unless user explicitly includes deleted files, and deletion event is logged with reason

---

### Edge Cases

- **What happens when Deepgram transcription fails (API timeout, quota exceeded)?** System retries with exponential backoff (3 attempts), logs detailed error with meeting context (meeting_id, recording URL, error code), marks transcription job as failed, does not create incomplete RAG records, and notifies user via dashboard with actionable error message (e.g., "Deepgram API quota exceeded. Retry after 1 hour or upgrade plan.").

- **How does system handle very large meeting recordings (>2 hours, >500MB)?** System streams processing to avoid memory issues: recording is downloaded in chunks, Deepgram handles long-form audio (up to 4 hours per API call), transcript is processed in segments, chunks are created incrementally, and embeddings are generated in batches (100 chunks at a time). If file exceeds Deepgram limits, it is split at silence boundaries and processed as separate jobs with sequence metadata.

- **What if multiple meetings end simultaneously (10 meetings in 1 minute)?** Scheduler detects all ended meetings in single polling cycle, creates IngestionEvent for each, jobs are queued and processed concurrently respecting MAX_CONCURRENT_JOBS limit (default 3), priority is given to older meetings (FIFO), and dashboard shows queue depth with estimated wait time.

- **What happens when LLM provider is unavailable (OpenAI downtime, Anthropic API errors)?** System retries with backoff (configurable per provider per FR-021: OpenAI 3 retries exponential backoff over 5min, Anthropic 2 retries linear backoff over 3min), if all retries fail, marks artifact as "pending_retry" and schedules for next availability check (every 15 minutes), other artifacts and pipeline steps continue unaffected, and user can manually retry or switch to alternative provider via .env configuration (LLM_PROVIDER_PREFERENCE) or dashboard.

- **How does system handle corrupt or malformed files (unreadable PDF, invalid JSON)?** File validation occurs early in pipeline: MIME type check, file size check, format-specific validation (PDF readable, JSON parseable, DOCX structure valid). If validation fails, job is marked failed immediately with specific error (e.g., "PDF is password-protected and cannot be extracted"), file is quarantined (moved to failed/ folder with timestamp), user is notified with recovery instructions, and no downstream steps are attempted.

- **What if embedding generation takes longer than expected (>5 minutes for single file)?** System implements per-step timeouts: embedding generation has 10-minute timeout for files <10MB, 30-minute for larger files. If timeout is hit, step is marked failed with timeout error, partial embeddings (if any) are discarded to maintain consistency, job is marked failed, and user can retry with increased timeout or investigate file content (e.g., extremely long document may need splitting).

- **What happens when vector database becomes full or corrupted?** System monitors ChromaDB storage size and health: logs warnings at 80% and 90% capacity, prevents new embeddings at 95% (returns user-friendly error: "Vector storage full, please archive old content or increase capacity"), provides admin command to rebuild index from database records, and supports backup/restore of ChromaDB directory for disaster recovery.

- **How are concurrent file updates to same file handled?** File ingestion uses file path as natural lock key: if IngestionEvent for same file is already queued/running, subsequent detection is deduplicated, only hash comparison determines if new version is needed, concurrent writes to same physical file are prevented at OS level (file watcher waits for write lock release before triggering ingestion).

- **What if YAML rules file has syntax errors or circular dependencies?** System validates rules.yaml on startup and on reload: YAML syntax is checked, artifact dependency graph is built and checked for cycles (A depends on B, B depends on A), if errors are found, system refuses to start/reload with detailed error messages (line number, error type, suggestion), previous valid rules remain in effect until successful reload.

- **How does system handle mixed-language content (Portuguese + English)?** LLM providers (GPT-4o, Claude) inherently support multilingual content, embeddings handle mixed languages naturally (semantic similarity works across languages), artifacts preserve original language of source content, user can configure language-specific prompts in rules.yaml if needed (e.g., "generate summary in Portuguese even if source is English"), and chat queries work in any language.

- **What happens when file watcher misses events (system downtime, network interruption)?** On startup and every configured interval (default hourly), system performs reconciliation scan: compares files on disk with database records, calculates hashes for files missing FileVersion, queues ingestion for new/changed files discovered, logs reconciliation events with counts (files added, changed, deleted), and ensures no files are permanently missed.

- **How are speaker names from Deepgram mapped to actual user identities?** Deepgram provides speaker labels (Speaker 0, Speaker 1, etc.) but not names. System stores labels in chunk metadata as-is. Optional post-processing can map labels to names if user provides mapping config (e.g., "Speaker 0" → "Alice Smith" based on calendar invite attendees or email matching). If no mapping is provided, queries use labels (e.g., "What did Speaker 0 say?"), and users can manually add speaker names to Meeting entity which then enriches chunk metadata in subsequent queries.

## Requirements *(mandatory)*

### Functional Requirements

#### Meeting Pipeline Foundation (Existing Infrastructure)

- **FR-001**: System MUST continue to poll Google Meet API on configurable schedule (default: every 5 minutes) to detect ended meetings using existing google_meet.py service
- **FR-002**: System MUST continue to download meeting recordings from Google Drive using existing google_drive.py service with authenticated API calls and retry logic
- **FR-003**: System MUST continue to transcribe meeting recordings using existing transcription.py service with Deepgram API, speaker diarization enabled, and timestamp extraction
- **FR-004**: System MUST preserve existing Meeting, Participant, Transcript, ProcessingJob entities and their relationships in database schema
- **FR-005**: System MUST create bridge layer (MeetingRAGBridge) to map completed Transcripts → FileVersion records for RAG pipeline ingestion without modifying existing transcription workflow. IMPORTANT: FileVersion.content_hash is SHA-256 of Transcript.full_text, NOT audio file hash, to detect re-transcription with different Deepgram parameters or manual corrections

#### File Ingestion & Detection

- **FR-006**: System MUST monitor specified ingestion folders for new files using file watcher (watchdog library) with configurable polling interval (default: 30 seconds)
- **FR-007**: System MUST support ingestion of multiple file types: markdown (`.md`), PDF (`.pdf`), DOCX (`.docx`), JSON (`.json`), plain text (`.txt`), and meeting transcripts (via bridge from Transcript entity)
- **FR-008**: System MUST calculate SHA-256 hash for each ingested file to detect content changes and prevent duplicate processing
- **FR-009**: System MUST create File and FileVersion entities: File tracks logical document, FileVersion tracks immutable snapshots with hash, size, discovered timestamp, and content locator
- **FR-010**: System MUST extract project identifier from file path using configurable pattern (e.g., `/ingest/project-alpha/` → project: `project-alpha`) or from Meeting.project_id for transcript bridge
- **FR-011**: System MUST detect file modifications by comparing current SHA-256 hash with latest FileVersion.content_hash and trigger reprocessing only for changed content
- **FR-012**: System MUST extract text content from PDFs using PyMuPDF with OCR fallback (Tesseract) for image-based PDFs
- **FR-013**: System MUST parse DOCX files to extract text while preserving paragraph structure and basic formatting metadata (headings, lists)
- **FR-014**: System MUST validate JSON files for chat backup format (Slack, Teams, WhatsApp exports) and parse messages with sender and timestamp

#### Dual-Provider LLM Architecture

- **FR-015**: System MUST implement pluggable LLM provider abstraction using Strategy pattern: LLMProvider abstract base class with generate() and embed() methods, designed for easy extension to additional providers
- **FR-016**: System MUST support OpenAI provider implementation: GPT-4o for text generation, text-embedding-3-large for embeddings, with API key configuration
- **FR-017**: System MUST support Anthropic provider implementation: Claude models (claude-3-5-sonnet, claude-3-opus) for text generation with API key configuration
- **FR-018**: System MUST implement LLMProviderFactory to instantiate providers based on configuration: provider name (openai|anthropic), model name, optional parameters (temperature, max_tokens)
- **FR-019**: System MUST allow provider selection via environment variable: LLM_PROVIDER_PREFERENCE (values: openai|anthropic, default: openai). Selected provider is used for all artifact generation unless overridden in rules.yaml
- **FR-020**: System MUST validate that selected provider's API key is configured on system startup: if LLM_PROVIDER_PREFERENCE=openai but OPENAI_API_KEY is missing, throw clear error with configuration instructions
- **FR-021**: System MUST log LLM provider metadata for every call: provider name, model name, prompt tokens, completion tokens, cost estimate (based on provider pricing), latency, timestamp
- **FR-022**: System MUST support provider-specific retry logic: OpenAI (3 retries, exponential backoff over 5min), Anthropic (2 retries, linear backoff over 3min)
- **FR-023**: System MUST allow per-artifact-type provider configuration in rules.yaml: specify provider and model for each artifact kind (e.g., summary: OpenAI GPT-4o, decisions: Anthropic Claude), overriding LLM_PROVIDER_PREFERENCE for specific artifacts

#### Text Processing & Embeddings

- **FR-024**: System MUST normalize text with precise rules: remove consecutive whitespace >1 space, standardize to \n line breaks, preserve punctuation in Unicode categories Po/Ps/Pe/Pi/Pf, remove control characters except \n and \t
- **FR-025**: System MUST chunk text into configurable segments using LangChain RecursiveCharacterTextSplitter: default 1200 characters with 200-character overlap (configurable per rule). Recommended tuning: meetings (800/150 for utterance boundaries), technical docs (1500/250 for context), chat exports (600/100 for message threads)
- **FR-026**: System MUST preserve context across chunks by including overlap and metadata: source file path, chunk index, character offsets (start/end), timestamps (if from meeting transcript), speaker (if from meeting)
- **FR-027**: System MUST generate embeddings for each text chunk using configured provider: OpenAI text-embedding-3-large (3072 dimensions) for MVP, with architecture supporting additional embedding providers in future
- **FR-028**: System MUST store embeddings in ChromaDB vector database with metadata: chunk_id (reference to chunks table), file_path, project_id, speaker (if meeting), timestamp (if meeting), chunk_text (for display)
- **FR-029**: System MUST support embedding model consistency: store embedding model name and dimensions in collection metadata (e.g., text-embedding-3-large: 3072 dimensions), prevent mixing embeddings from different models in same collection, validate both model name and dimensions match on retrieval

#### Declarative Artifact Generation

- **FR-030**: System MUST load processing rules from YAML configuration files (rules.yaml) with syntax validation on startup and on manual reload
- **FR-031**: System MUST match files against rules using glob patterns (`path_glob`), MIME types (`mimetypes`), and project identifiers with first-match-wins strategy
- **FR-032**: System MUST execute processing steps in defined order per rule: normalize → chunk → embed → generate_artifacts, with dependency tracking between steps
- **FR-033**: System MUST support configurable artifact types in rules: summary, decisions_index, entities_index, timeline, action_items, custom (plugin-defined)
- **FR-034**: System MUST generate artifacts using configured LLM provider and prompt template: load template from src/services/prompts/, substitute variables (context, file metadata), call provider, validate output
- **FR-035**: System MUST validate generated artifacts against JSON schemas: load schema from contracts/artifacts/{kind}.schema.json, validate structure and required fields, log validation failures
- **FR-036**: System MUST version artifacts: Artifact entity tracks logical artifact, ArtifactVersion entity tracks immutable snapshots, new version created when source file changes or prompt template changes
- **FR-037**: System MUST link artifacts to source files via ArtifactLink entity: track which FileVersions contributed to which ArtifactVersions, support role types (source, derived, reference)
- **FR-038**: System MUST support multi-file artifacts: artifacts depending on multiple source files (e.g., weekly summary), track all dependencies in ArtifactLinks, regenerate when any dependency changes
- **FR-039**: System MUST expose artifacts via unique keys: format `{kind}:{project}:{identifier}` (e.g., `summary:project-alpha:2025-W45`), support key-based retrieval via API

#### Plugin System for Extensibility

- **FR-040**: System MUST implement plugin registry pattern for artifact generators: scan src/services/artifacts/ for classes implementing ArtifactGenerator interface, auto-register at startup
- **FR-041**: System MUST support custom artifact generators: users can create Python files in plugins directory with generate() method, declare artifact kind in class metadata, no core code changes needed
- **FR-042**: System MUST implement plugin registry for chunking strategies: scan src/services/chunkers/ for classes implementing ChunkingStrategy interface, allow selection via rules.yaml
- **FR-043**: System MUST support dependency injection for services: LLMProvider, EmbeddingService, ArtifactGenerator are injected via factory pattern, enabling easy swapping for testing and experimentation

#### Pipeline Execution & Job Tracking

- **FR-044**: System MUST create JobRun entity for each ingestion event: track status (queued, running, success, failed, partial), timestamps (started_at, completed_at), input reference (FileVersion or Meeting), metrics (chunks created, embeddings generated, artifacts produced)
- **FR-045**: System MUST record JobStep entities for each pipeline step: step name (normalize, chunk, embed, generate_artifacts), status, timestamps, log output (JSON), error details if failed
- **FR-046**: System MUST support concurrent job execution with configurable parallelism: global MAX_CONCURRENT_JOBS limit (default 3), per-rule concurrency limits, queue management with priority support
- **FR-047**: System MUST implement retry logic with exponential backoff for transient failures: network errors, API rate limits, timeout errors, max 3 retries with 2x backoff multiplier
- **FR-048**: System MUST continue processing remaining steps if non-critical steps fail: CRITICAL steps (normalize, chunk, embed) cause job failure, NON-CRITICAL steps (artifact generation) allow partial success. Mark job as "partial" if artifact generation fails but embeddings succeeded, log partial success details
- **FR-049**: System MUST record job metrics in JobRun.metrics JSON field: input_file_count, chunks_created, embeddings_generated, artifacts_produced, duration_seconds, llm_tokens_used, llm_cost_estimate
- **FR-050**: System MUST provide job status API endpoints: GET /api/v1/jobs (list with filters), GET /api/v1/jobs/{job_id} (detail with steps/logs/artifacts), POST /api/v1/jobs/{job_id}/retry

#### Observability & Monitoring

- **FR-051**: System MUST log all operations using structured JSON format (via existing src/utils/logging.py): timestamp, level, service, job_id, file_id, meeting_id (if applicable), message, context
- **FR-052**: System MUST expose execution dashboard UI (Streamlit) listing jobs with filters: date range, status, project, file type, meeting vs uploaded file
- **FR-053**: System MUST provide job detail view showing: input files (clickable links), step timeline with status icons, logs per step (expandable), output artifacts (preview links), performance metrics
- **FR-054**: System MUST link artifacts in job view to their content and usage: artifact detail page, source file links, version history, chat queries that referenced this artifact
- **FR-055**: System MUST track and display job metrics in dashboard: total jobs, success rate, average duration, failure breakdown by type (validation error, LLM timeout, embedding failure)
- **FR-056**: System MUST implement health checks for critical dependencies: database connection, ChromaDB reachability, LLM provider API status (ping endpoints), disk space availability

#### RAG & Retrieval

- **FR-057**: System MUST provide chat interface (Streamlit) for natural language queries: text input, conversation history, support for follow-up questions (maintain context)
- **FR-058**: System MUST convert user queries to embeddings using same model as indexed content: validate embedding model consistency, generate query embedding, log embedding latency
- **FR-059**: System MUST retrieve top-K similar chunks from ChromaDB using cosine similarity: default K=10, configurable per query, support metadata filters (project, date range, source type)
- **FR-060**: System MUST assemble context from retrieved chunks with source metadata: chunk text, source file path, line/page number, speaker (if meeting), timestamp (if meeting), similarity score
- **FR-061**: System MUST send context + query to configured LLM provider for answer generation: use chat completion format, system message defines role ("assistant grounded in provided context"), user message contains query and context
- **FR-062**: System MUST extract citations from LLM response: parse for source references (file path, speaker, timestamp), map to chunk metadata, format as clickable links in UI
- **FR-063**: System MUST handle low-confidence retrievals: if max similarity score < threshold (default 0.6), return "I don't have information about that in the indexed content" instead of generating answer. Threshold rationale: 0.6 based on empirical testing with Portuguese/English corpus. Tune per project: technical content may need 0.5, conversational content 0.65. Monitor false negative rate
- **FR-064**: System MUST make newly ingested embeddings immediately available: ChromaDB persists to disk after each batch, no manual reindexing required, new embeddings queryable within 1 minute of ingestion

#### Backfill & Reprocessing

- **FR-065**: System MUST support backfill operations to process existing files in bulk: manual trigger via API (POST /api/v1/backfill) or CLI command, specify target folder or file list
- **FR-066**: System MUST discover all matching files during backfill: recursive directory scan, filter by extension/MIME type, calculate hashes, create IngestionEvents with backfill_job_id
- **FR-067**: System MUST respect rate limits during backfill: monitor API quota usage (OpenAI TPM, Deepgram monthly limit), pause when quota exceeded, wait for cooldown, resume automatically
- **FR-068**: System MUST provide backfill progress tracking: BackfillJob entity with total_file_count, processed_count, failed_count, status (queued/running/paused/completed), progress_percentage, estimated_completion_time
- **FR-069**: System MUST support backfill control: POST /api/v1/backfill/{job_id}/pause (stop queueing new jobs, let running jobs finish), /resume (continue from pause point), /cancel (stop immediately, mark remaining as skipped)
- **FR-070**: System MUST generate backfill summary report on completion: success count, failure count, artifacts generated (breakdown by type), total duration, average time per file, total LLM cost, downloadable CSV of failed files with error reasons

#### Data Management & Versioning

- **FR-071**: System MUST implement soft delete for files: File.deleted=true, FileVersions retained in database, embeddings remain in ChromaDB but excluded from queries unless explicitly requested, deletion event logged
- **FR-072**: System MUST maintain file version history: all FileVersions linked to parent File with timestamps and hashes, version comparison (diff) available via API, rollback to previous version supported
- **FR-073**: System MUST detect and flag duplicate files: compare SHA-256 hashes across File entities, deduplicate on ingestion (skip reprocessing), provide duplicate report via API for cleanup
- **FR-074**: System MUST implement incremental artifact updates: query ArtifactLinks to find affected artifacts when FileVersion changes, regenerate only necessary ArtifactVersions, preserve old versions for audit
- **FR-075**: System MUST support retention policies for cleanup: configurable TTL for old FileVersions (default: retain indefinitely), manual hard delete operation (purge all related data), LGPD compliance (data deletion on request)
- **FR-076**: System MUST provide data export capabilities: database dump (SQLite backup), ChromaDB directory export, artifact archive (ZIP with all artifact files), full system backup for disaster recovery

### Key Entities

- **Meeting** (EXISTING - KEEP): Represents a Google Meet session; includes meeting ID from Google, title, start/end time, organizer, participants, recording URL, transcription status, **NEW: RAG fields (ingestion_status, file_id linking to RAG File entity)**

- **Participant** (EXISTING - KEEP): Represents a meeting attendee; includes participant ID, meeting reference, email, display name, join/leave timestamps

- **Transcript** (EXISTING - KEEP): Represents transcribed meeting content from Deepgram; includes transcript ID, meeting reference, full text with speaker labels and timestamps, confidence score, Deepgram response metadata, **NEW: RAG tracking fields (chunk_count, embedding_generated_at)**

- **ProcessingJob** (EXISTING - KEEP): Represents transcription processing workflow; includes job ID, meeting reference, status (pending/processing/completed/failed), started/completed timestamps, error details; **NOTE: Coexists with new JobRun entity (ProcessingJob for transcription, JobRun for RAG pipeline)**

- **File** (NEW): Represents logical document for RAG ingestion; includes file ID, relative path (to ingestion root), MIME type, project identifier, reference to current FileVersion, deleted flag (soft delete), created/updated timestamps; **NOTE: Can be linked from Meeting via meeting.file_id for transcripts entering RAG pipeline**

- **FileVersion** (NEW): Immutable snapshot of file content; includes version ID, parent File reference, SHA-256 hash (for change detection), file size in bytes, discovered timestamp, content locator (original path or archive location)

- **Chunk** (NEW): Text segment extracted for embedding; includes chunk ID, FileVersion reference, chunk index (position in document), text content, character offsets (start/end in source), metadata JSON (speaker, timestamp if from meeting; heading, page if from document), created timestamp

- **Embedding** (NEW): Vector representation of chunk; includes embedding ID, Chunk reference, embedding model identifier (e.g., "text-embedding-3-large"), vector_db_id (ChromaDB document ID), collection name, created timestamp; **NOTE: Actual embedding vectors stored in ChromaDB, this entity is metadata/reference**

- **JobRun** (NEW): RAG pipeline execution instance; includes job ID, pipeline name (rule that triggered it), status (queued/running/success/failed/partial), started/completed timestamps, input reference (FileVersion ID or backfill_job_id), metrics JSON (chunks created, embeddings generated, artifacts produced, LLM cost), retry count

- **JobStep** (NEW): Individual stage within JobRun; includes step ID, JobRun reference, step name (normalize/chunk/embed/generate_artifacts/{artifact_kind}), status, started/completed timestamps, log output (structured JSON), error details if failed

- **Artifact** (NEW): Logical artifact aggregating versions; includes artifact ID, artifact key (unique composite: `{kind}:{project}:{identifier}`), artifact kind (summary/decisions/entities/timeline/action_items/custom), project identifier, created/updated timestamps

- **ArtifactVersion** (NEW): Specific version of artifact content; includes version ID, Artifact reference, JobRun reference (which execution created this), content locator (file path, database BLOB, or external URL), metadata JSON (schema version, LLM provider, model name, prompt template used, generation timestamp, tokens used, cost), created timestamp

- **ArtifactLink** (NEW): Many-to-many relationship tracking artifact sources; includes link ID, ArtifactVersion reference, FileVersion reference, role type (source/derived/reference), weight or contribution score (optional for multi-file artifacts), link metadata (which sections of file were used)

- **ProcessingRule** (NEW): Declarative configuration for pipeline behavior; loaded from rules.yaml, not stored as entities but cached in memory; includes rule name, match criteria (path glob, MIME types, project tags), processing steps with parameters, artifact specifications (kind, provider, model, prompt template), reprocess policy (changed_input/always/manual_only), enabled flag

- **Project** (NEW): Organizational grouping for files and artifacts; includes project identifier (derived from folder name or explicit config), display name, description, artifact retention policies, ingestion folder paths, custom metadata (team, client, domain tags)

- **BackfillJob** (NEW): Bulk reprocessing operation; includes backfill job ID, target folder path or file list, total file count, processed count, failed count, status (queued/running/paused/completed/cancelled), progress percentage, started/paused/resumed/completed timestamps, summary report JSON (success/failure breakdown, artifacts created)

- **LLMProvider** (NEW - Code abstraction, not entity): Interface for pluggable LLM implementations; implementations: OpenAIProvider, AnthropicProvider (MVP scope), extensible for future providers; methods: generate(prompt, context) → string, embed(text) → vector, estimate_cost(tokens) → float

## Success Criteria *(mandatory)*

### Measurable Outcomes

#### Meeting Pipeline Integration

- **SC-001**: Existing Google Meet integration continues to work without regression: meetings are detected within 5 minutes of ending, recordings download successfully 95% of the time, transcriptions complete with speaker diarization for 90% of meetings
- **SC-002**: Meeting transcriptions automatically flow into RAG pipeline: within 2 minutes of transcription completion, FileVersion is created, chunks preserve speaker and timestamp metadata, embeddings are generated and queryable
- **SC-003**: Speaker metadata is preserved end-to-end: chunks include speaker labels from Deepgram, chat queries can filter by speaker (e.g., "What did Alice say?"), citations show speaker name and timestamp in results

#### File Ingestion & Processing

- **SC-004**: System detects and queues newly uploaded files within 30 seconds of file creation (file watcher) or next polling interval (1 minute for polling fallback)
- **SC-005**: 95% of files under 10MB complete full processing (ingestion → chunking → embedding → artifacts) within 2 minutes
- **SC-006**: System correctly identifies and skips duplicate files (identical SHA-256 hash) 100% of the time, avoiding redundant processing and storage
- **SC-007**: File type detection accuracy is 100% for supported formats (MD, PDF, DOCX, JSON, TXT) based on MIME type validation and magic number detection
- **SC-008**: PDF text extraction succeeds for 90% of PDFs without OCR; OCR fallback (Tesseract) handles remaining 10% with >80% text accuracy
- **SC-009**: System handles up to 20 concurrent file ingestions without degradation, processing within configured parallelism limits (3 concurrent jobs)

#### Dual-Provider LLM & Experimentation

- **SC-010**: Users can switch LLM providers without code changes: updating LLM_PROVIDER_PREFERENCE environment variable from "openai" to "anthropic" (or rules.yaml provider field) causes next artifact generation to use new provider
- **SC-011**: System successfully generates artifacts using both OpenAI GPT-4o and Anthropic Claude with identical input, storing provider metadata (model, tokens, cost, latency) for comparison
- **SC-012**: LLM provider selection works correctly: user can switch between OpenAI and Anthropic via LLM_PROVIDER_PREFERENCE environment variable, selected provider is used for all artifacts (unless overridden in rules.yaml), configuration errors are clearly reported at startup
- **SC-013**: All LLM calls are logged with complete metadata: provider, model, prompt tokens, completion tokens, latency, cost estimate, enabling cost tracking and performance analysis
- **SC-014**: Experimental mode allows A/B testing: when multiple providers are configured for same artifact type, all variants are generated, comparison view displays results side-by-side in dashboard

#### Artifact Generation Quality

- **SC-015**: Artifact generation succeeds for 95% of files matching rules, with failures logged with specific error reasons (LLM timeout, invalid JSON, schema validation failure) and retryable
- **SC-016**: Decisions index artifacts extract structured decisions with required fields (decisor, decision, date, justification) for 85% of meetings/documents containing explicit decision language. Decision language patterns: keywords ('decidimos', 'vamos', 'agreed to', 'decided', 'will proceed with') within 50 tokens of action verb
- **SC-017**: Entity recognition identifies people, teams, and organizations with 80% precision/recall compared to manual annotation on sample corpus
- **SC-018**: Timeline artifacts correctly sequence events chronologically with accurate timestamps for 90% of time-referenced statements in meetings/documents
- **SC-019**: Summary artifacts capture key points covering 80% of human-identified critical topics (measured via user feedback or test set evaluation)
- **SC-020**: Artifact updates complete within 3 minutes when source files change, regenerating only affected artifacts (not all), verified by version timestamps

#### RAG Retrieval & Chat Accuracy

- **SC-021**: Chat queries retrieve relevant chunks with >70% recall on test question set (known questions with known correct source locations across meetings and documents)
- **SC-022**: Retrieval precision (top-5 chunks contain answer content) exceeds 60% on diverse question types (factual, decision-based, timeline-based, cross-source)
- **SC-023**: LLM responses include correct citations with >85% accuracy: file path, page/line number for documents, speaker and timestamp for meetings
- **SC-024**: System responds "I don't have information about that" when similarity scores are below threshold (0.6), avoiding hallucinations 100% of the time on out-of-domain queries
- **SC-025**: End-to-end query latency (question → retrieval → LLM → response) is under 5 seconds for 90% of queries using OpenAI GPT-4o with cached embeddings
- **SC-026**: Newly ingested content becomes searchable within 1 minute of ingestion completion: embeddings indexed in ChromaDB and available for retrieval immediately

#### Observability & Reliability

- **SC-027**: 100% of job executions are logged with structured data (job ID, status, timestamps, metrics) and queryable via API or dashboard
- **SC-028**: Users can locate execution details for any file ingestion within 30 seconds using dashboard filters (file name, date range, project, status)
- **SC-029**: Failed jobs display actionable error messages and retry options in dashboard for 100% of failures, with clear root cause explanation
- **SC-030**: System uptime is 99.5% during business hours (local deployment, excludes scheduled maintenance), measured by health check endpoint availability
- **SC-031**: Health checks detect critical failures (database down, ChromaDB unreachable, LLM provider unavailable) within 1 minute and log alerts with severity tags
- **SC-032**: Backfill jobs provide progress updates at least every 30 seconds, displaying accurate completion percentage (±5%) and estimated time remaining

#### Data Integrity & Versioning

- **SC-033**: File version history is preserved with 100% accuracy: all FileVersions linked to parent File with correct timestamps, hashes, and artifact links
- **SC-034**: Incremental updates correctly identify affected artifacts: when file changes, system regenerates only dependent ArtifactVersions (not all), verified by artifact version timestamps
- **SC-035**: Soft delete operations retain all data and relationships: File.deleted=true, data queryable via explicit API parameter, recoverable for 90 days (configurable retention)
- **SC-036**: Hard delete (when triggered) removes 100% of related data: FileVersions, Chunks, Embeddings (from ChromaDB), ArtifactLinks purged without leaving orphaned records
- **SC-037**: Duplicate file detection prevents redundant storage: files with identical SHA-256 hashes link to same FileVersion, saving disk space and processing time
- **SC-038**: Version comparison (diff) works correctly: API returns text differences between FileVersions, UI displays side-by-side comparison with highlighted changes

#### User Experience & Usability

- **SC-039**: Users can configure new processing rule (YAML edit → reload) and see it take effect within 1 minute without restarting system
- **SC-040**: Dashboard loads job list (<1000 jobs) in under 2 seconds and supports pagination for larger sets, maintaining responsiveness
- **SC-041**: Chat interface responds to user input with visual feedback (typing indicator, loading state) within 200ms of query submission
- **SC-042**: Citation links navigate to correct source location: for meetings, show transcript with highlighted section and timestamp; for documents, show file with highlighted paragraph (within ±5 lines)
- **SC-043**: Users successfully complete common tasks (check job status, trigger backfill, query knowledge, compare LLM providers) without documentation 80% of the time (measured via usability testing)

#### Resource & Cost Efficiency

- **SC-044**: Average embedding generation cost is under $0.05 per 1000 chunks using OpenAI text-embedding-3-large ($0.13/1M tokens * ~300 tokens/chunk)
- **SC-045**: Artifact generation (LLM calls) costs under $0.20 per document on average using OpenAI GPT-4o ($5/1M input tokens, $15/1M output tokens)
- **SC-046**: ChromaDB storage efficiency: average 500KB per 1000 chunks including embeddings (3072 dimensions * 4 bytes * 1000) and metadata
- **SC-047**: System operates on commodity hardware (16GB RAM, 4 CPU cores, 100GB disk) supporting up to 10,000 documents and 100k chunks without performance degradation
- **SC-048**: Disk space usage grows predictably at ~2MB per ingested document (including versions, embeddings, artifacts, logs), enabling capacity planning
- **SC-049**: Provider comparison metrics show: OpenAI (fastest response, highest cost) vs Anthropic (balanced quality/cost), enabling informed provider selection based on use case priorities

## Assumptions

**Infrastructure & Deployment**:
- Assuming deployment environment is local (on-premise or private VPS) with full control over resources
- Assuming minimum hardware available: 16GB RAM, 4-core CPU, 100GB disk (scales with document volume)
- Assuming stable file system with POSIX-compliant permissions for folder monitoring and write access
- Assuming network connectivity for cloud LLM services (OpenAI or Anthropic required) and Google APIs
- Assuming Docker or container runtime is available for simplified deployment (optional but recommended)

**Existing Infrastructure** (CRITICAL):
- Assuming Google Meet integration (src/services/google_meet.py) is working and will not be modified except for RAG bridge hookpoint
- Assuming Deepgram transcription service (src/services/transcription.py) is working and produces speaker-diarized transcripts with timestamps
- Assuming Meeting, Participant, Transcript, ProcessingJob models are stable and will be extended with RAG fields, not replaced
- Assuming existing utilities (src/utils/logging.py, retry.py, exceptions.py, google_auth.py) are reused, not recreated
- Assuming scheduler.py will be extended to trigger RAG ingestion after transcription completes

**File Sources & Formats**:
- Assuming ingested files are primarily text-based or convertible to text (MD, PDF, DOCX, JSON, TXT)
- Assuming PDF files are either native text PDFs or require OCR (Tesseract available locally or as service)
- Assuming DOCX files follow standard Office Open XML format (not heavily corrupted or password-protected)
- Assuming JSON chat backups follow recognizable schema (Slack, Teams, WhatsApp exports) or can be configured via rules
- Assuming file encoding is UTF-8 or detectable/convertible to UTF-8 (chardet library for detection)
- Assuming average file size is 1-10MB; large files (>100MB) are rare and handled with streaming or chunking

**Content & Language**:
- Assuming documents and meetings are primarily in Portuguese (Brazilian), with potential for English content
- Assuming LLM models support Portuguese for artifact generation: OpenAI GPT-4o and Anthropic Claude both have multilingual support
- Assuming meeting transcriptions from Deepgram follow consistent format with speaker labels (Speaker 0, Speaker 1) and timestamps ([HH:MM:SS] format)
- Assuming structured artifacts (decisions, entities, timelines) are extractable from most ingested content with reasonable accuracy (85%+ success rate)

**Usage Patterns**:
- Assuming initial corpus includes existing meetings (already transcribed, need backfill) plus new meetings (ongoing transcription) plus uploaded documents
- Assuming daily ingestion rate is 10-50 new files during active periods (meetings + uploads)
- Assuming backfill operations are infrequent (one-time migration of historical meetings, quarterly re-indexing if needed)
- Assuming concurrent users accessing chat interface: 1-10 during MVP, scaling to 50+ in production
- Assuming query frequency: 10-100 queries per day during MVP testing, growing with adoption

**Data Privacy & Security**:
- Assuming all data is sensitive and must remain local (no cloud storage except optional LLM APIs which receive only chunks, not full files)
- Assuming users have organizational permission to ingest and process all uploaded documents and meeting transcriptions
- Assuming LGPD (Brazilian data protection law) compliance is required for personal data in documents and meeting content
- Assuming retention policies will be configured per project (default: retain indefinitely with manual cleanup; auto-purge can be enabled)
- Assuming soft delete is default; hard delete is manual and rare (for compliance requests or storage cleanup)

**LLM Providers & Costs**:
- Assuming OpenAI API key is available for GPT-4o and text-embedding-3-large (default LLM provider)
- Assuming Anthropic API key is available for Claude models (alternative LLM provider option)
- Assuming at least one LLM provider (OpenAI or Anthropic) is configured via environment variables
- Assuming OpenAI API rate limits are sufficient for MVP workload (10k TPM for GPT-4o, 1M TPM for embeddings)
- Assuming Anthropic API rate limits are sufficient when selected as LLM provider (10k TPM for Claude)
- Assuming budget exists for cloud LLM usage: estimated $500 for MVP corpus (10k documents, 100k chunks) including embeddings + artifacts + queries for 1 year
- Assuming LLM outputs are non-deterministic and may require prompt template tuning for optimal quality

**Processing Rules & Configuration**:
- Assuming processing rules are defined by technical users comfortable editing YAML files
- Assuming rules can be tested and refined iteratively without breaking production data (versioning and rollback supported)
- Assuming project taxonomy (folder structure, naming conventions) is defined before ingestion begins
- Assuming artifact schemas (e.g., decision structure with decisor/decision/date/justification fields) are standardized and consistent across projects

**Observability & Monitoring**:
- Assuming users need visibility into processing status but don't require real-time alerting (Slack/email notifications) in MVP
- Assuming structured JSON logs are sufficient for debugging; no requirement for centralized log aggregation (Splunk, ELK) in MVP
- Assuming dashboard UI is web-based and accessible via localhost or internal network (no public internet exposure required)
- Assuming metrics collection focuses on job success/failure rates, processing times, LLM costs rather than system-level metrics (CPU, memory) in MVP

**Integration & Extensibility**:
- Assuming future integrations (e.g., SharePoint, Confluence, Notion) will follow similar ingestion patterns (folder monitoring, API polling, file download)
- Assuming artifact types may expand beyond initial set (summary, decisions, entities, timeline, action_items) as user needs evolve
- Assuming new file formats (e.g., PPT, XLS, HTML) can be added by implementing extractors without core refactoring (plugin system supports this)
- Assuming custom LLM providers (e.g., Cohere, Hugging Face Inference API) can be added by implementing LLMProvider interface

## Dependencies

**Existing Infrastructure** (KEEP - Critical Foundation):
- Google Meet API integration (google_meet.py) for meeting detection and recording downloads
- Google Drive API integration (google_drive.py) for recording file access
- Deepgram API integration (transcription.py) for audio transcription with speaker diarization
- Meeting processing orchestration (meeting_processor.py) for transcription workflow management
- Scheduler (scheduler.py) for periodic Google Meet polling and job triggering
- Database models (models/meeting.py, participant.py, transcript.py, processing_job.py)
- Utility modules (utils/logging.py, retry.py, exceptions.py, google_auth.py) for cross-cutting concerns

**Core Runtime Dependencies**:
- Python 3.11+ runtime environment
- FastAPI 0.104+ for REST API and async request handling
- SQLAlchemy 2.0+ for ORM and database abstraction
- SQLite (for lightweight deployments) or PostgreSQL (for production scale)
- Alembic for database schema migrations
- Pydantic 2.0+ for data validation and settings management

**RAG & Vector Database** (NEW):
- ChromaDB 0.4+ (embedded vector database for local-first RAG experimentation)
- LangChain 0.1+ (document loaders, text splitters, retrieval chains, embeddings)

**Dual-Provider LLM Support** (NEW):
- OpenAI Python SDK 1.0+ (GPT-4o for generation, text-embedding-3-large for embeddings)
- Anthropic Python SDK (Claude models for generation)
- httpx or requests (for HTTP client operations and potential future provider extensions)

**Document Processing Libraries** (NEW):
- PyMuPDF (fitz) or pdfplumber (PDF text extraction)
- Tesseract OCR + pytesseract (OCR fallback for image-based PDFs)
- python-docx (DOCX parsing)
- python-magic or mimetypes (file type detection)
- chardet (encoding detection for non-UTF8 files)
- watchdog (file system monitoring for ingestion folders)

**UI & Dashboard** (NEW):
- Streamlit 1.28+ (chat interface and execution dashboard - rapid prototyping without frontend code)

**Testing & Quality** (NEW):
- pytest (unit, integration, contract tests)
- pytest-asyncio (async test support)
- httpx (API testing client)
- pytest-cov (coverage reporting)

**Deployment & Containerization** (Optional but Recommended):
- Docker + Docker Compose (for reproducible local/cloud deployment)

**Operational Dependencies**:
- Configured ingestion folder paths with read/write permissions
- YAML processing rules defined in rules.yaml before first ingestion
- Project taxonomy and folder structure established (e.g., /ingest/{project_id}/)
- LLM service credentials: OPENAI_API_KEY and/or ANTHROPIC_API_KEY (environment variables), LLM_PROVIDER_PREFERENCE configuration
- Google API credentials (existing: for Meet and Drive access via OAuth)
- Deepgram API key (existing: for transcription service)

## Out of Scope (for Initial Implementation)

The following features are explicitly NOT included in the initial implementation and will be considered for future iterations:

**Local Model Support**:
- Ollama integration: Local LLM hosting (mistral, phi3, llama2) is NOT included in MVP
- Architecture supports future addition via LLMProvider interface (Strategy pattern)
- To add later: implement OllamaProvider class, update factory, add OLLAMA_BASE_URL to .env
- Rationale: Focus MVP on proven cloud providers (OpenAI, Anthropic) while maintaining extensible architecture

**Advanced NLP & AI Features**:
- Named Entity Linking (NEL): Resolving entities to knowledge bases (Wikidata, internal HR system)
- Sentiment analysis: Tracking emotional tone or meeting sentiment over time
- Topic modeling: Automatic discovery of discussion themes beyond explicit keywords
- Real-time transcription: No live meeting transcription; only post-meeting file processing
- Custom vocabulary training: No fine-tuning of LLM/embedding models on domain-specific terminology
- Multi-language auto-detection: Assuming Portuguese/English; no automatic switching for other languages
- Speaker name resolution: Deepgram provides labels (Speaker 0, Speaker 1); mapping to actual names requires manual configuration

**User Interface & Collaboration**:
- Real-time collaboration: No multi-user editing of artifacts or annotations
- Manual artifact editing UI: No WYSIWYG editor for correcting generated summaries/decisions (users can regenerate with different prompt)
- Commenting/annotations on files: No in-app discussion threads or highlights on documents/transcripts
- Role-based access control (RBAC): No per-user or per-project permissions (all users see all data in MVP)
- Mobile app: Dashboard and chat are web-only; no native mobile client
- Email/Slack/Teams notifications: No automated alerts when jobs complete or fail (users check dashboard manually)
- Calendar integration: No automatic sync with Google/Outlook calendars for meeting context enrichment

**Advanced Data Management**:
- Multi-tenancy: Single organization/workspace only; no tenant isolation
- Data lineage visualization: No graphical view of file → artifact → query relationships (data is tracked in database, no UI)
- Audit log UI: Logs are queryable via API/DB but no dedicated audit dashboard
- Automated data retention enforcement: Retention policies exist but require manual trigger for cleanup
- Cross-project search: Search is per-project or global; no complex multi-project queries with ACLs
- Version diffing: File/artifact versions are tracked but no visual diff tool (API returns raw text differences)

**Integration & Extensibility**:
- Direct cloud storage integrations: No native connectors for Google Drive folders (other than meeting recordings), Dropbox, SharePoint (files must be copied to ingestion folders manually)
- Webhooks: No outbound webhook triggers for external systems on ingestion events (polling API required)
- GraphQL API: REST only; no GraphQL for flexible querying
- SSO/LDAP integration: No enterprise authentication; assumes local deployment or basic auth/VPN-protected environment

**Performance & Scale**:
- Distributed processing: No multi-node job execution; single-server parallelism only (MAX_CONCURRENT_JOBS=3)
- GPU acceleration: No GPU support for embeddings/LLM (CPU-based or cloud API only)
- Streaming ingestion: No real-time data pipelines (Kafka, Kinesis); batch file-based only
- Horizontal scaling: ChromaDB and SQLite are single-instance; no sharding or clustering (migrate to PostgreSQL + Qdrant if scale exceeds single-node limits)

**Advanced Artifact Types**:
- Graph visualization: Relationships tracked in ArtifactLinks but no visual graph UI (Neo4j integration deferred)
- Causal reasoning: No "why did X lead to Y" analysis; only factual extraction
- Predictive artifacts: No forecasting or trend analysis ("based on past decisions, what will happen next")
- Cross-document synthesis: Artifacts are per-document or simple aggregations; no complex multi-doc reasoning beyond RAG context window

**Quality & Testing**:
- Automated test suite for artifact quality: No regression tests for LLM output quality (manual validation only)
- A/B testing framework: Experimental mode exists but no statistical significance testing or automated winner selection
- Explainability tools: No LIME/SHAP for understanding why specific chunks were retrieved (similarity scores logged but not explained)

**Compliance & Security**:
- End-to-end encryption: Data at rest encryption via OS/filesystem tools; no app-level E2E encryption
- Redaction: No automatic PII/sensitive data masking in artifacts or responses (user must configure prompts to avoid sensitive topics)
- Compliance reporting: No GDPR/LGPD audit reports or automated data subject access request (DSAR) handling (manual export via API)
- Penetration testing: No formal security audit or pen-test as part of MVP scope

**Advanced LLM Features**:
- Fine-tuning: No custom model training on organizational data (use off-the-shelf models with prompt engineering)
- Agent workflows: No autonomous agents or multi-step reasoning chains (single-shot LLM calls only)
- Retrieval re-ranking: No advanced reranking algorithms (Cohere, ColBERT); simple cosine similarity ranking only
- Hybrid search: No keyword + vector search combination (pure vector search via ChromaDB)

---

## Technology Context (for Planning Phase)

**Existing Technology Stack** (DO NOT CHANGE):
- Language: Python 3.11+
- Transcription: Deepgram API via AsyncDeepgramClient
- Meeting API: Google Meet API v2, Google Drive API v3
- Scheduling: APScheduler (existing scheduler.py)
- Authentication: OAuth2 (existing google_auth.py)
- Logging: structlog (existing logging.py)
- Database: SQLite with SQLAlchemy (existing models)
- Retry Logic: Custom decorator (existing retry.py)
- Exception Handling: Custom hierarchy (existing exceptions.py)

**New Technology Additions** (for RAG capabilities):
- Vector Database: ChromaDB (embedded, local-first)
- RAG Framework: LangChain (document loading, chunking, retrieval)
- LLM Providers: OpenAI (default), Anthropic (alternative, user-selectable)
- Chat UI: Streamlit (rapid prototyping, no frontend code)
- API Framework: FastAPI (for new RAG endpoints)
- Testing: pytest, pytest-asyncio, httpx (for new tests)

**Modular Architecture Patterns**:
- Strategy Pattern: LLMProvider interface with OpenAI/Anthropic implementations (extensible for future providers)
- Factory Pattern: LLMProviderFactory to instantiate providers based on config
- Plugin Registry: Artifact generators, chunking strategies auto-discovered from plugins directory
- Dependency Injection: Services injected via factory, enabling easy swapping for testing/experimentation
- Bridge Pattern: MeetingRAGBridge to connect existing transcription pipeline to new RAG pipeline without tight coupling

**Configuration-Driven Behavior**:
- rules.yaml: Declarative processing rules (file matching, artifact types, LLM providers, prompt templates)
- .env: Environment variables (API keys, database URL, ChromaDB path, concurrency limits)
- Plugin discovery: Drop Python files in src/services/artifacts/ or src/services/chunkers/, auto-register via class metadata

