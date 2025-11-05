# Data Model Specification

**Feature**: RAG-Enhanced Meeting Intelligence System
**Created**: 2025-11-04
**Status**: Planning Phase 1

## Overview

This document defines all entities in the RAG-Enhanced Meeting Intelligence System, specifying their fields, relationships, constraints, indexes, and state transitions. The system extends existing meeting transcription infrastructure with RAG capabilities, preserving speaker metadata throughout the data model.

**Entity Classification**:
- **EXISTING (KEEP AS-IS)**: Entities that exist and require no changes
- **EXISTING (EXTEND)**: Entities that exist and need new RAG-related fields
- **NEW**: Entities that need to be created for RAG functionality

---

## 1. Meeting (EXISTING - EXTEND)

**Description**: Represents a Google Meet session with recording and transcription metadata. Extended to link meetings to RAG pipeline for automatic transcription ingestion.

**Fields**:

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| meeting_id | String(255) | PK, NOT NULL | Unique identifier from Google Meet API |
| title | String(500) | NOT NULL | Meeting title/subject |
| start_time | DateTime | NOT NULL | Meeting start timestamp (UTC) |
| end_time | DateTime | NOT NULL | Meeting end timestamp (UTC) |
| duration_minutes | Integer | NOT NULL, > 0, <= 180 | Meeting duration in minutes |
| recording_url | String(1000) | NULL | Google Drive recording URL |
| recording_drive_id | String(255) | NULL | Google Drive file ID for recording |
| status | Enum(MeetingStatus) | NOT NULL, DEFAULT='detected' | Processing status (detected, downloading, transcribing, uploading, completed, failed, skipped) |
| project_name | String(100) | NOT NULL, DEFAULT='GERAL' | Project classification |
| **file_id** | **Integer** | **NULL, FK(files.file_id)** | **NEW: Link to RAG File entity when transcript enters RAG pipeline** |
| **rag_ingestion_status** | **Enum(RAGIngestionStatus)** | **NULL** | **NEW: RAG pipeline status (pending, processing, completed, failed)** |
| created_at | DateTime | NOT NULL, DEFAULT=now() | Record creation timestamp |
| updated_at | DateTime | NOT NULL, DEFAULT=now(), onupdate=now() | Record update timestamp |

**Relationships**:
- One-to-Many with `Participant` (back_populates="meeting")
- One-to-One with `Transcript` (back_populates="meeting")
- One-to-Many with `ProcessingJob` (back_populates="meeting")
- **NEW: Many-to-One with `File`** (back_populates="source_meetings")

**Indexes**:
- `idx_meeting_status` on (status)
- `idx_meeting_end_time` on (end_time)
- `idx_meeting_project` on (project_name)
- **NEW: `idx_meeting_file_id`** on (file_id)
- **NEW: `idx_meeting_rag_status`** on (rag_ingestion_status)

**Validation Rules**:
- `duration_minutes > 0` (CheckConstraint: duration_positive)
- `duration_minutes <= 180` (CheckConstraint: duration_max_3_hours)
- `end_time > start_time` (application-level validation)

**State Transitions**:
```
detected → downloading → transcribing → uploading → completed
                                      ↓
                                   failed (retryable via ProcessingJob)
```

**Notes**:
- Existing fields and relationships preserved
- New RAG fields enable bridge to File entity after transcription
- MeetingRAGBridge service monitors `status=completed` and `rag_ingestion_status=null` to trigger ingestion

---

## 2. Participant (EXISTING - KEEP AS-IS)

**Description**: Represents a meeting attendee with identification and attendance metadata.

**Fields**:

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| participant_id | Integer | PK, AUTOINCREMENT | Unique participant record identifier |
| meeting_id | String(255) | FK(meetings.meeting_id), NOT NULL, ON DELETE CASCADE | Reference to meeting |
| name | String(255) | NOT NULL, DEFAULT='Unknown Participant' | Participant display name |
| email | String(320) | NULL | Participant email address |
| speaker_id | String(50) | NULL | Deepgram speaker label (Speaker 0, Speaker 1, etc.) for mapping |
| attendance_duration_minutes | Integer | NULL | Duration participant was in meeting |

**Relationships**:
- Many-to-One with `Meeting` (back_populates="participants")

**Indexes**:
- `idx_participant_meeting` on (meeting_id)
- `idx_participant_email` on (email)

**Notes**:
- No changes required for RAG integration
- `speaker_id` field can be populated to map Deepgram speaker labels to actual participant names
- Optional future enhancement: automatic speaker mapping via calendar invite attendees

---

## 3. Transcript (EXISTING - EXTEND)

**Description**: Represents transcribed meeting content from Deepgram with speaker diarization. Extended to track RAG processing metadata.

**Fields**:

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| transcript_id | Integer | PK, AUTOINCREMENT | Unique transcript identifier |
| meeting_id | String(255) | FK(meetings.meeting_id), UNIQUE, NOT NULL, ON DELETE CASCADE | Reference to meeting (one transcript per meeting) |
| full_text | Text | NOT NULL | Complete transcription text |
| markdown_text | Text | NOT NULL | Formatted transcription with speaker labels and timestamps |
| word_count | Integer | NOT NULL, DEFAULT=0, >= 0 | Total word count |
| speaker_count | Integer | NOT NULL, DEFAULT=0, >= 0 | Number of distinct speakers detected |
| drive_file_id | String(255) | NULL | Google Drive file ID where transcript is stored |
| drive_folder_id | String(255) | NOT NULL | Google Drive folder ID for project storage |
| **deepgram_response** | **JSON** | **NULL** | **NEW: Raw Deepgram API response preserving utterances with speaker/timestamp metadata** |
| **chunk_count** | **Integer** | **NULL, >= 0** | **NEW: Number of chunks created from this transcript** |
| **embedding_generated_at** | **DateTime** | **NULL** | **NEW: Timestamp when embeddings were generated** |
| created_at | DateTime | NOT NULL, DEFAULT=now() | Transcript creation timestamp |

**Relationships**:
- One-to-One with `Meeting` (back_populates="transcript")

**Indexes**:
- `idx_transcript_meeting` on (meeting_id) - automatically created via UNIQUE constraint
- **NEW: `idx_transcript_embedding_status`** on (embedding_generated_at) - to find pending embeddings

**Validation Rules**:
- `word_count >= 0` (CheckConstraint: word_count_non_negative)
- `speaker_count >= 0` (CheckConstraint: speaker_count_non_negative)

**Notes**:
- Existing fields preserved
- New `deepgram_response` JSON field stores complete Deepgram utterances array for speaker metadata preservation
- MeetingRAGBridge reads this field to create chunks with speaker and timestamp metadata
- `chunk_count` enables tracking of transcript → chunk conversion status

---

## 4. ProcessingJob (EXISTING - KEEP AS-IS)

**Description**: Tracks transcription processing attempts, retries, and failures for meeting recordings.

**Fields**:

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| job_id | Integer | PK, AUTOINCREMENT | Unique job identifier |
| meeting_id | String(255) | FK(meetings.meeting_id), NOT NULL, ON DELETE CASCADE | Reference to meeting |
| status | Enum(JobStatus) | NOT NULL, DEFAULT='pending' | Job status (pending, processing, completed, failed) |
| retry_count | Integer | NOT NULL, DEFAULT=0, >= 0, <= 3 | Number of retry attempts |
| error_message | Text | NULL | Human-readable error description |
| error_type | String(100) | NULL | Error classification (DeepgramAPIError, NetworkError, etc.) |
| started_at | DateTime | NULL | Job start timestamp |
| completed_at | DateTime | NULL | Job completion timestamp |
| next_retry_at | DateTime | NULL | Scheduled next retry timestamp |
| created_at | DateTime | NOT NULL, DEFAULT=now() | Record creation timestamp |
| updated_at | DateTime | NOT NULL, DEFAULT=now(), onupdate=now() | Record update timestamp |

**Relationships**:
- Many-to-One with `Meeting` (back_populates="processing_jobs")

**Indexes**:
- `idx_job_status` on (status)
- `idx_job_next_retry` on (next_retry_at)
- `idx_job_meeting` on (meeting_id)

**Validation Rules**:
- `retry_count >= 0` (CheckConstraint: retry_count_non_negative)
- `retry_count <= 3` (CheckConstraint: retry_count_max_3)

**State Transitions**:
```
pending → processing → completed
                    ↓
                 failed (retry_count < 3 → pending with next_retry_at)
                    ↓
                 failed (retry_count = 3 → terminal state)
```

**Notes**:
- Handles transcription pipeline only (not RAG pipeline)
- Coexists with new `JobRun` entity (ProcessingJob for transcription, JobRun for RAG)
- No changes required for RAG integration

---

## 5. Project (EXISTING - EXTEND FOR RAG)

**Description**: Organizational grouping for meetings and documents. Extended to support RAG-specific configuration and file management.

**Fields**:

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| project_id | Integer | PK, AUTOINCREMENT | Unique project identifier |
| name | String(100) | UNIQUE, NOT NULL | Project name (used for classification) |
| drive_folder_id | String(255) | UNIQUE, NOT NULL | Google Drive folder ID for meeting recordings |
| classification_rules | JSON | NOT NULL, DEFAULT=[] | JSON array of title/participant matching rules |
| is_default | Boolean | NOT NULL, DEFAULT=false | Flag indicating default project (exactly one must be true) |
| **display_name** | **String(255)** | **NULL** | **NEW: Human-readable project name for UI display** |
| **description** | **Text** | **NULL** | **NEW: Project description** |
| **ingestion_folder_path** | **String(500)** | **NULL** | **NEW: Local filesystem path for document ingestion** |
| **artifact_retention_days** | **Integer** | **NULL, > 0** | **NEW: Retention policy for artifacts (null = indefinite)** |
| **metadata** | **JSON** | **NULL** | **NEW: Custom metadata (team, client, domain tags)** |
| created_at | DateTime | NOT NULL, DEFAULT=now() | Project creation timestamp |

**Relationships**:
- **NEW: One-to-Many with `File`** (back_populates="project")
- **NEW: One-to-Many with `Artifact`** (back_populates="project")

**Indexes**:
- `idx_project_name` on (name) - automatically created via UNIQUE constraint
- `idx_project_is_default` on (is_default)
- **NEW: `idx_project_ingestion_folder`** on (ingestion_folder_path)

**Notes**:
- Existing meeting classification functionality preserved
- New RAG fields enable project-scoped file ingestion and artifact management
- `ingestion_folder_path` enables file watcher to monitor project-specific folders

---

## 6. File (NEW)

**Description**: Represents logical document for RAG ingestion. Can be linked from Meeting (for transcripts entering RAG) or standalone (uploaded documents).

**Fields**:

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| file_id | Integer | PK, AUTOINCREMENT | Unique file identifier |
| relative_path | String(1000) | NOT NULL | Path relative to ingestion root or "meeting://{meeting_id}" for transcripts |
| mime_type | String(100) | NOT NULL | MIME type (text/markdown, application/pdf, etc.) |
| source_type | Enum(FileSourceType) | NOT NULL | Source classification (meeting, uploaded_document, chat_export) |
| project_id | Integer | FK(projects.project_id), NOT NULL, ON DELETE CASCADE | Project grouping |
| current_version_id | Integer | FK(file_versions.version_id), NULL | Reference to latest FileVersion |
| deleted | Boolean | NOT NULL, DEFAULT=false | Soft delete flag |
| created_at | DateTime | NOT NULL, DEFAULT=now() | File discovery timestamp |
| updated_at | DateTime | NOT NULL, DEFAULT=now(), onupdate=now() | Last modification timestamp |

**Relationships**:
- One-to-Many with `FileVersion` (back_populates="file")
- Many-to-One with `Project` (back_populates="files")
- **One-to-Many with `Meeting`** (back_populates="file") - for transcript source tracking

**Indexes**:
- `idx_file_project` on (project_id)
- `idx_file_relative_path` on (relative_path)
- `idx_file_source_type` on (source_type)
- `idx_file_deleted` on (deleted)
- `idx_file_current_version` on (current_version_id)

**Validation Rules**:
- `relative_path` must be unique within (project_id, deleted=false)
- `mime_type` must be in supported list (validated at application level)

**Notes**:
- Soft delete pattern: `deleted=true` retains data but excludes from queries by default
- `current_version_id` points to active FileVersion for efficient latest-version queries
- `source_type='meeting'` indicates file was created from transcript bridge

---

## 7. FileVersion (NEW)

**Description**: Immutable snapshot of file content with hash-based change detection.

**Fields**:

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| version_id | Integer | PK, AUTOINCREMENT | Unique version identifier |
| file_id | Integer | FK(files.file_id), NOT NULL, ON DELETE CASCADE | Parent file reference |
| content_hash | String(64) | NOT NULL | SHA-256 hash of content (hex string) |
| file_size_bytes | Integer | NOT NULL, > 0 | File size in bytes |
| content_locator | String(1000) | NOT NULL | Storage location (file path, S3 key, or database reference) |
| is_current | Boolean | NOT NULL, DEFAULT=true | Flag indicating active version |
| discovered_at | DateTime | NOT NULL, DEFAULT=now() | Version creation timestamp |

**Relationships**:
- Many-to-One with `File` (back_populates="versions")
- One-to-Many with `Chunk` (back_populates="file_version")
- One-to-Many with `ArtifactLink` (back_populates="file_version")
- One-to-Many with `JobRun` (via input_file_version_id)

**Indexes**:
- `idx_file_version_file` on (file_id)
- `idx_file_version_hash` on (content_hash)
- `idx_file_version_is_current` on (is_current, file_id) - composite for current version lookup

**Validation Rules**:
- `file_size_bytes > 0` (CheckConstraint: file_size_positive)
- Only one version per file can have `is_current=true` (enforced at application level)
- `content_hash` must be unique within file_id (same file, different hash = new version)

**Notes**:
- Hash-based change detection: compare `content_hash` with new file to detect changes
- All versions retained for audit trail and rollback capability
- When new version created: old version `is_current=false`, new version `is_current=true`

---

## 8. Chunk (NEW)

**Description**: Text segment extracted from FileVersion for embedding and retrieval. Preserves speaker and timestamp metadata for meeting transcripts.

**Fields**:

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| chunk_id | Integer | PK, AUTOINCREMENT | Unique chunk identifier |
| file_version_id | Integer | FK(file_versions.version_id), NOT NULL, ON DELETE CASCADE | Source file version |
| chunk_index | Integer | NOT NULL, >= 0 | Position in document (0-indexed) |
| text_content | Text | NOT NULL | Chunk text content |
| char_offset_start | Integer | NOT NULL, >= 0 | Character offset in source document (start) |
| char_offset_end | Integer | NOT NULL, > 0 | Character offset in source document (end) |
| metadata | JSON | NULL | Chunk-specific metadata (speaker, timestamp, heading, page, etc.) |
| deleted | Boolean | NOT NULL, DEFAULT=false | Soft delete flag (for version updates) |
| created_at | DateTime | NOT NULL, DEFAULT=now() | Chunk creation timestamp |

**Relationships**:
- Many-to-One with `FileVersion` (back_populates="chunks")
- One-to-One with `Embedding` (back_populates="chunk")

**Indexes**:
- `idx_chunk_file_version` on (file_version_id)
- `idx_chunk_index` on (chunk_index, file_version_id) - composite for sequential access
- `idx_chunk_deleted` on (deleted)

**Validation Rules**:
- `char_offset_end > char_offset_start` (CheckConstraint: valid_offsets)
- `chunk_index` must be unique within file_version_id

**Metadata Schema** (JSON field structure):

```json
{
  "speaker": "Speaker 0",           // Meeting transcripts only
  "timestamp": "00:14:32",          // Meeting transcripts only
  "speaker_name": "Alice Smith",    // Optional if speaker mapping available
  "page": 5,                        // Documents with pagination (PDF)
  "heading": "Architecture Design", // Documents with structure (DOCX, MD)
  "section": "2.3",                 // Document section number
  "message_sender": "john@example", // Chat exports
  "message_timestamp": "2025-11-01T14:32:00Z" // Chat exports
}
```

**Notes**:
- Soft delete pattern enables versioning: old chunks marked `deleted=true` when file updated
- Speaker metadata from Deepgram preserved in `metadata.speaker` and `metadata.timestamp`
- Overlap between chunks (typically 200 chars) handled via offset ranges, not duplicated text

---

## 9. Embedding (NEW)

**Description**: Vector representation of chunk stored in ChromaDB. This entity is metadata/reference; actual vectors stored in ChromaDB.

**Fields**:

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| embedding_id | Integer | PK, AUTOINCREMENT | Unique embedding identifier |
| chunk_id | Integer | FK(chunks.chunk_id), UNIQUE, NOT NULL, ON DELETE CASCADE | Reference to chunk (one embedding per chunk) |
| embedding_model | String(100) | NOT NULL | Model identifier (text-embedding-3-large, nomic-embed-text, etc.) |
| vector_db_id | String(255) | NOT NULL | ChromaDB document ID |
| collection_name | String(100) | NOT NULL | ChromaDB collection name |
| created_at | DateTime | NOT NULL, DEFAULT=now() | Embedding creation timestamp |

**Relationships**:
- One-to-One with `Chunk` (back_populates="embedding")

**Indexes**:
- `idx_embedding_chunk` on (chunk_id) - automatically created via UNIQUE constraint
- `idx_embedding_model` on (embedding_model)
- `idx_embedding_collection` on (collection_name)
- `idx_embedding_vector_db_id` on (vector_db_id) - for ChromaDB synchronization

**Validation Rules**:
- `embedding_model` must match ChromaDB collection metadata (validated at application level)
- `vector_db_id` must exist in ChromaDB (validated at retrieval time)

**Notes**:
- Actual embedding vectors (3072 dimensions for OpenAI, varies by model) stored in ChromaDB
- This table provides bidirectional mapping: chunk_id ↔ ChromaDB document ID
- Collection naming convention: `{project_id}_{embedding_model}` (e.g., "project-alpha_text-embedding-3-large")
- Model consistency enforced: cannot mix embeddings from different models in same collection

---

## 10. JobRun (NEW)

**Description**: RAG pipeline execution instance tracking ingestion, chunking, embedding, and artifact generation.

**Fields**:

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| job_id | Integer | PK, AUTOINCREMENT | Unique job identifier |
| pipeline_name | String(100) | NOT NULL | Rule name that triggered this job |
| status | Enum(JobRunStatus) | NOT NULL, DEFAULT='queued' | Job status (queued, running, success, failed, partial) |
| input_file_version_id | Integer | FK(file_versions.version_id), NULL, ON DELETE SET NULL | Source file version (null for backfill aggregates) |
| backfill_job_id | Integer | FK(backfill_jobs.backfill_job_id), NULL, ON DELETE CASCADE | Parent backfill job if part of batch |
| retry_count | Integer | NOT NULL, DEFAULT=0, >= 0 | Number of retry attempts |
| metrics | JSON | NULL | Job metrics (chunks_created, embeddings_generated, artifacts_produced, llm_tokens, cost) |
| started_at | DateTime | NULL | Job start timestamp |
| completed_at | DateTime | NULL | Job completion timestamp |
| created_at | DateTime | NOT NULL, DEFAULT=now() | Job creation timestamp |

**Relationships**:
- Many-to-One with `FileVersion` (back_populates="job_runs")
- Many-to-One with `BackfillJob` (back_populates="job_runs")
- One-to-Many with `JobStep` (back_populates="job_run")
- One-to-Many with `ArtifactVersion` (back_populates="job_run")

**Indexes**:
- `idx_job_run_status` on (status)
- `idx_job_run_file_version` on (input_file_version_id)
- `idx_job_run_backfill` on (backfill_job_id)
- `idx_job_run_pipeline` on (pipeline_name)
- `idx_job_run_started` on (started_at)

**Validation Rules**:
- `retry_count >= 0` (CheckConstraint: retry_count_non_negative)
- Either `input_file_version_id` or `backfill_job_id` must be set (application-level validation)

**State Transitions**:
```
queued → running → success
                ↓
              partial (some artifacts failed, embeddings succeeded)
                ↓
              failed (critical step failed, e.g., file validation, chunking)
```

**Metrics Schema** (JSON field):

```json
{
  "input_file_count": 1,
  "chunks_created": 150,
  "embeddings_generated": 150,
  "artifacts_produced": 3,
  "duration_seconds": 45.2,
  "llm_tokens_used": 4500,
  "llm_cost_estimate": 0.15,
  "llm_provider": "openai",
  "llm_model": "gpt-4o",
  "embedding_provider": "openai",
  "embedding_model": "text-embedding-3-large"
}
```

**Notes**:
- Separate from `ProcessingJob` (transcription) to maintain clear separation of concerns
- `status='partial'` indicates non-critical failures (e.g., artifact generation failed but embeddings succeeded)
- Retry logic applied at JobRun level; failed steps can be retried individually via JobStep

---

## 11. JobStep (NEW)

**Description**: Individual stage within JobRun pipeline with detailed logging and error tracking.

**Fields**:

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| step_id | Integer | PK, AUTOINCREMENT | Unique step identifier |
| job_run_id | Integer | FK(job_runs.job_id), NOT NULL, ON DELETE CASCADE | Parent job run |
| step_name | String(100) | NOT NULL | Step identifier (normalize, chunk, embed, generate_{artifact_kind}) |
| status | Enum(JobStepStatus) | NOT NULL, DEFAULT='pending' | Step status (pending, running, success, failed) |
| log_output | JSON | NULL | Structured log entries for this step |
| error_message | Text | NULL | Human-readable error description |
| error_type | String(100) | NULL | Error classification (ValidationError, LLMTimeoutError, etc.) |
| started_at | DateTime | NULL | Step start timestamp |
| completed_at | DateTime | NULL | Step completion timestamp |

**Relationships**:
- Many-to-One with `JobRun` (back_populates="job_steps")

**Indexes**:
- `idx_job_step_run` on (job_run_id)
- `idx_job_step_status` on (status)
- `idx_job_step_name` on (step_name)

**Validation Rules**:
- `step_name` must follow convention: "normalize", "chunk", "embed", or "generate_{artifact_kind}"
- At most one step with same step_name per job_run_id (application-level validation)

**Log Output Schema** (JSON field):

```json
{
  "entries": [
    {
      "timestamp": "2025-11-04T14:32:15Z",
      "level": "INFO",
      "message": "Starting text extraction from PDF",
      "context": {"file_path": "/ingest/project-alpha/doc.pdf", "file_size": 2457600}
    },
    {
      "timestamp": "2025-11-04T14:32:18Z",
      "level": "WARN",
      "message": "OCR fallback triggered for scanned pages",
      "context": {"pages_scanned": [3, 5, 7]}
    }
  ]
}
```

**Notes**:
- Enables detailed debugging: each step's logs isolated for troubleshooting
- Failed steps can be retried independently without rerunning entire job
- Step execution order enforced at application level based on pipeline definition

---

## 12. Artifact (NEW)

**Description**: Logical artifact aggregating versions (summary, decisions index, entities, etc.). Supports multi-version history.

**Fields**:

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| artifact_id | Integer | PK, AUTOINCREMENT | Unique artifact identifier |
| artifact_key | String(500) | UNIQUE, NOT NULL | Composite key: {kind}:{project}:{identifier} (e.g., "summary:project-alpha:meeting-123") |
| artifact_kind | String(100) | NOT NULL | Artifact type (summary, decisions_index, entities_index, timeline, action_items, custom) |
| project_id | Integer | FK(projects.project_id), NOT NULL, ON DELETE CASCADE | Project grouping |
| current_version_id | Integer | FK(artifact_versions.version_id), NULL | Reference to latest ArtifactVersion |
| created_at | DateTime | NOT NULL, DEFAULT=now() | Artifact creation timestamp |
| updated_at | DateTime | NOT NULL, DEFAULT=now(), onupdate=now() | Last version update timestamp |

**Relationships**:
- One-to-Many with `ArtifactVersion` (back_populates="artifact")
- Many-to-One with `Project` (back_populates="artifacts")

**Indexes**:
- `idx_artifact_key` on (artifact_key) - automatically created via UNIQUE constraint
- `idx_artifact_kind` on (artifact_kind)
- `idx_artifact_project` on (project_id)
- `idx_artifact_current_version` on (current_version_id)

**Validation Rules**:
- `artifact_key` format: `{kind}:{project_identifier}:{unique_identifier}` (application-level validation)
- `artifact_kind` must be registered in artifact generator registry (application-level validation)

**Notes**:
- Artifact key enables idempotent creation/update: same key = update existing artifact
- Versioning pattern similar to File/FileVersion: Artifact is logical, ArtifactVersion is immutable
- `current_version_id` points to active version for efficient queries

---

## 13. ArtifactVersion (NEW)

**Description**: Specific version of artifact content with generation metadata (LLM provider, model, cost, etc.).

**Fields**:

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| version_id | Integer | PK, AUTOINCREMENT | Unique version identifier |
| artifact_id | Integer | FK(artifacts.artifact_id), NOT NULL, ON DELETE CASCADE | Parent artifact |
| job_run_id | Integer | FK(job_runs.job_id), NULL, ON DELETE SET NULL | Job that created this version |
| content_locator | String(1000) | NOT NULL | Storage location (file path or database reference) |
| content_hash | String(64) | NOT NULL | SHA-256 hash of content (for deduplication) |
| metadata | JSON | NOT NULL | Generation metadata (schema_version, llm_provider, model, prompt_template, tokens, cost) |
| is_current | Boolean | NOT NULL, DEFAULT=true | Flag indicating active version |
| created_at | DateTime | NOT NULL, DEFAULT=now() | Version creation timestamp |

**Relationships**:
- Many-to-One with `Artifact` (back_populates="versions")
- Many-to-One with `JobRun` (back_populates="artifact_versions")
- One-to-Many with `ArtifactLink` (back_populates="artifact_version")

**Indexes**:
- `idx_artifact_version_artifact` on (artifact_id)
- `idx_artifact_version_job_run` on (job_run_id)
- `idx_artifact_version_is_current` on (is_current, artifact_id) - composite for current version lookup
- `idx_artifact_version_hash` on (content_hash) - for deduplication

**Validation Rules**:
- Only one version per artifact can have `is_current=true` (enforced at application level)

**Metadata Schema** (JSON field):

```json
{
  "schema_version": "1.0",
  "llm_provider": "openai",
  "llm_model": "gpt-4o",
  "prompt_template": "summary_v2.txt",
  "prompt_tokens": 2500,
  "completion_tokens": 800,
  "total_tokens": 3300,
  "cost_estimate": 0.075,
  "generation_timestamp": "2025-11-04T14:35:22Z",
  "temperature": 0.7,
  "max_tokens": 1000
}
```

**Notes**:
- Complete generation provenance enables A/B testing and cost analysis
- `content_hash` enables deduplication: if new generation produces identical content, skip storage
- Prompt template versioning enables artifact regeneration comparison

---

## 14. ArtifactLink (NEW)

**Description**: Many-to-many relationship tracking artifact sources and dependencies. Enables incremental updates and audit trails.

**Fields**:

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| link_id | Integer | PK, AUTOINCREMENT | Unique link identifier |
| artifact_version_id | Integer | FK(artifact_versions.version_id), NOT NULL, ON DELETE CASCADE | Target artifact version |
| file_version_id | Integer | FK(file_versions.version_id), NOT NULL, ON DELETE CASCADE | Source file version |
| role_type | Enum(LinkRoleType) | NOT NULL | Relationship type (source, derived, reference) |
| contribution_weight | Float | NULL, >= 0.0, <= 1.0 | Contribution score for multi-file artifacts (null = equal weight) |
| link_metadata | JSON | NULL | Additional link context (sections used, relevance score) |
| created_at | DateTime | NOT NULL, DEFAULT=now() | Link creation timestamp |

**Relationships**:
- Many-to-One with `ArtifactVersion` (back_populates="artifact_links")
- Many-to-One with `FileVersion` (back_populates="artifact_links")

**Indexes**:
- `idx_artifact_link_artifact` on (artifact_version_id)
- `idx_artifact_link_file` on (file_version_id)
- `idx_artifact_link_role` on (role_type)
- **Composite unique**: `idx_artifact_link_unique` on (artifact_version_id, file_version_id) - prevent duplicate links

**Validation Rules**:
- `contribution_weight` between 0.0 and 1.0 if not null (CheckConstraint: valid_weight)
- Sum of `contribution_weight` for same `artifact_version_id` should equal 1.0 (application-level validation)

**Role Types**:
- `source`: FileVersion is primary input for artifact (e.g., meeting transcript → summary)
- `derived`: Artifact was derived from this file but not primary (e.g., weekly summary referencing 5 meetings)
- `reference`: File is cited or referenced but not directly used for generation

**Link Metadata Schema** (JSON field):

```json
{
  "sections_used": ["Introduction", "Architecture"],
  "relevance_score": 0.87,
  "chunks_referenced": [12, 15, 18, 23],
  "extraction_method": "rag_retrieval"
}
```

**Notes**:
- Enables incremental updates: when FileVersion changes, query ArtifactLinks to find affected artifacts
- Multi-file artifacts (e.g., weekly summary) track all source files with contribution weights
- Audit trail: all artifact sources traceable via this table

---

## 15. BackfillJob (NEW)

**Description**: Bulk reprocessing operation for historical files with progress tracking and control.

**Fields**:

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| backfill_job_id | Integer | PK, AUTOINCREMENT | Unique backfill job identifier |
| target_folder_path | String(1000) | NULL | Target folder for recursive scan (null = file list) |
| target_file_list | JSON | NULL | Explicit list of file paths (null = folder scan) |
| total_file_count | Integer | NOT NULL, >= 0 | Total files to process |
| processed_count | Integer | NOT NULL, DEFAULT=0, >= 0 | Files successfully processed |
| failed_count | Integer | NOT NULL, DEFAULT=0, >= 0 | Files that failed processing |
| status | Enum(BackfillStatus) | NOT NULL, DEFAULT='queued' | Job status (queued, running, paused, completed, cancelled) |
| progress_percentage | Float | NOT NULL, DEFAULT=0.0, >= 0.0, <= 100.0 | Completion percentage |
| summary_report | JSON | NULL | Final report (success/failure breakdown, artifacts created, costs) |
| started_at | DateTime | NULL | Job start timestamp |
| paused_at | DateTime | NULL | Job pause timestamp (if applicable) |
| resumed_at | DateTime | NULL | Job resume timestamp (if applicable) |
| completed_at | DateTime | NULL | Job completion timestamp |
| created_at | DateTime | NOT NULL, DEFAULT=now() | Job creation timestamp |

**Relationships**:
- One-to-Many with `JobRun` (back_populates="backfill_job")

**Indexes**:
- `idx_backfill_status` on (status)
- `idx_backfill_started` on (started_at)

**Validation Rules**:
- Exactly one of `target_folder_path` or `target_file_list` must be set (application-level validation)
- `progress_percentage` between 0.0 and 100.0 (CheckConstraint: valid_progress)
- `processed_count + failed_count <= total_file_count` (application-level validation)

**State Transitions**:
```
queued → running → completed
              ↓
           paused → running (resumed)
              ↓
          cancelled (terminal state)
```

**Summary Report Schema** (JSON field):

```json
{
  "success_count": 195,
  "failure_count": 5,
  "artifacts_generated": {
    "summary": 195,
    "decisions_index": 195,
    "entities_index": 190
  },
  "total_duration_seconds": 8040,
  "average_duration_per_file_seconds": 40.2,
  "total_llm_cost": 23.50,
  "failed_files": [
    {
      "file_path": "/ingest/project-alpha/corrupted.pdf",
      "error_reason": "PDF is password-protected",
      "error_type": "ValidationError"
    }
  ]
}
```

**Notes**:
- Backfill control: pause stops queueing new jobs, resume continues from current position
- Progress tracking via `processed_count` and `progress_percentage` for real-time UI updates
- Summary report generated on completion for post-analysis

---

## 16. ProcessingRule (NEW - Configuration, Not Entity)

**Description**: Declarative configuration for RAG pipeline behavior loaded from rules.yaml. Not stored as database entity but cached in memory.

**Configuration Structure** (YAML):

```yaml
artifact_generation_rules:
  - name: "meeting-rag-ingestion"
    match_criteria:
      path_glob: "meeting://**"
      mime_types: ["text/markdown"]
      project_tags: ["default"]

    processing_steps:
      - step: "normalize"
        params:
          remove_excessive_whitespace: true
          preserve_speaker_format: true

      - step: "chunk"
        strategy: "MeetingChunker"
        params:
          chunk_size: 1200
          chunk_overlap: 200
          preserve_speaker_boundaries: true

      - step: "embed"
        provider: "openai"
        model: "text-embedding-3-large"

      - step: "generate_artifacts"
        artifacts:
          - kind: "summary"
            generator: "SummaryGenerator"
            llm_provider: "openai"
            llm_model: "gpt-4o"
            prompt_template: "meeting_summary.txt"

          - kind: "decisions_index"
            generator: "DecisionsGenerator"
            llm_provider: "anthropic"
            llm_model: "claude-3-5-sonnet-20241022"
            prompt_template: "meeting_decisions.txt"

    reprocess_policy: "changed_input"  # changed_input | always | manual_only
    enabled: true
```

**Notes**:
- Loaded at startup and on manual reload (POST /api/v1/rules/reload)
- First-match-wins strategy for rule selection
- Validation performed on load: YAML syntax, artifact dependencies, plugin existence
- Changes require reload but not system restart

---

## 17. LLMProvider (NEW - Code Abstraction, Not Entity)

**Description**: Interface for pluggable LLM implementations with Strategy + Factory pattern. Not stored as database entity.

**Interface Definition**:

```python
from abc import ABC, abstractmethod
from typing import List, Dict, Any

class LLMProvider(ABC):
    """Abstract base class for LLM provider implementations."""

    @abstractmethod
    def generate(self, prompt: str, context: str = "", **kwargs) -> str:
        """Generate text completion from prompt and context."""
        pass

    @abstractmethod
    def embed(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for list of text strings."""
        pass

    @abstractmethod
    def estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """Calculate cost estimate based on provider pricing."""
        pass

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Provider identifier (openai, anthropic)."""
        pass

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Model identifier (gpt-4o, claude-3-5-sonnet)."""
        pass
```

**Implementations** (MVP Scope):
- `OpenAIProvider`: OpenAI API integration (GPT-4o, text-embedding-3-large)
- `AnthropicProvider`: Anthropic API integration (Claude models)

**Future Extensions**:
- `OllamaProvider`: Can be added for local model support (mistral, phi3, llama2, nomic-embed-text) without refactoring

**Factory Pattern**:

```python
class LLMProviderFactory:
    """Factory for creating LLM provider instances."""

    @staticmethod
    def create(provider_name: str, model_name: str, **config) -> LLMProvider:
        """Instantiate provider based on name."""
        if provider_name == "openai":
            return OpenAIProvider(model_name, api_key=config.get("api_key"))
        elif provider_name == "anthropic":
            return AnthropicProvider(model_name, api_key=config.get("api_key"))
        else:
            raise ValueError(f"Unknown provider: {provider_name}. Supported: openai, anthropic")
```

**Notes**:
- Strategy pattern enables provider swapping via configuration
- All LLM calls logged with metadata: provider, model, tokens, cost, latency
- Retry logic implemented at provider level (reuses existing utils/retry.py)

---

## Entity Relationship Diagram (ERD)

```
┌─────────────┐       ┌──────────────┐       ┌─────────────┐
│   Meeting   │──────<│ Participant  │       │  Transcript │
│ (EXISTING   │       │ (EXISTING-   │       │ (EXISTING-  │
│  EXTEND)    │       │  KEEP)       │       │  EXTEND)    │
└──────┬──────┘       └──────────────┘       └──────┬──────┘
       │                                             │
       │ file_id (NEW)                               │ deepgram_response (NEW)
       │                                             │ chunk_count (NEW)
       ├─────────────────────────────────────────────┤
       │                                             │
       ↓                                             ↓
┌─────────────┐       ┌──────────────┐       ┌─────────────┐
│    File     │──────<│ FileVersion  │──────<│    Chunk    │
│   (NEW)     │       │   (NEW)      │       │   (NEW)     │
└──────┬──────┘       └──────┬───────┘       └──────┬──────┘
       │                     │                       │
       │ project_id          │ content_hash          │ metadata (speaker, timestamp)
       │                     │                       │
       ↓                     ↓                       ↓
┌─────────────┐       ┌──────────────┐       ┌─────────────┐
│   Project   │       │   JobRun     │       │  Embedding  │
│ (EXISTING-  │       │   (NEW)      │       │   (NEW)     │
│  EXTEND)    │       └──────┬───────┘       └─────────────┘
└──────┬──────┘              │
       │                     │ job_steps
       │ artifacts           │
       │                     ↓
       │              ┌──────────────┐
       │              │   JobStep    │
       │              │   (NEW)      │
       │              └──────────────┘
       │
       ↓
┌─────────────┐       ┌──────────────┐       ┌─────────────┐
│  Artifact   │──────<│ArtifactVer-  │──────<│ ArtifactLink│
│   (NEW)     │       │  sion (NEW)  │       │   (NEW)     │
└─────────────┘       └──────────────┘       └──────┬──────┘
                                                     │
                                                     │ file_version_id
                                                     ↓
                                              ┌──────────────┐
                                              │ FileVersion  │
                                              └──────────────┘

┌─────────────┐       ┌──────────────┐
│BackfillJob  │──────<│   JobRun     │
│   (NEW)     │       │   (NEW)      │
└─────────────┘       └──────────────┘

┌─────────────┐       ┌──────────────┐
│ProcessingJob│──────<│   Meeting    │
│ (EXISTING-  │       │ (EXISTING)   │
│  KEEP)      │       └──────────────┘
└─────────────┘
```

---

## Key Design Patterns

### 1. Soft Delete Pattern
- Entities: `File`, `Chunk`
- Implementation: `deleted` boolean flag (default `false`)
- Behavior: Excluded from queries by default unless explicitly requested
- Retention: Configurable per project (default: indefinite)

### 2. Versioning Pattern
- Entity Pairs: `File`/`FileVersion`, `Artifact`/`ArtifactVersion`
- Immutability: Versions are immutable snapshots
- Current Version Tracking: Parent entity has `current_version_id` for efficient lookup
- Audit Trail: All versions retained with timestamps and hashes

### 3. Hash-Based Change Detection
- Entities: `FileVersion`, `ArtifactVersion`
- Hash: SHA-256 of content (hex string)
- Usage: Compare hash to detect changes, avoid duplicate processing
- Efficiency: Incremental updates regenerate only affected artifacts

### 4. Bridge Pattern (Meeting → RAG Integration)
- Bridge Service: `MeetingRAGBridge`
- Purpose: Connect existing transcription pipeline to RAG without tight coupling
- Flow: `Transcript` (completed) → Bridge → `File` + `FileVersion` → RAG pipeline
- Independence: Transcription and RAG pipelines evolve independently

### 5. Strategy Pattern (Dual-Provider LLMs)
- Interface: `LLMProvider` abstract base class
- Implementations (MVP): `OpenAIProvider`, `AnthropicProvider`
- Selection: User-configurable via LLM_PROVIDER_PREFERENCE env var or rules.yaml per-artifact override
- Extensibility: Future providers (e.g., OllamaProvider) can be added by implementing interface

### 6. Factory Pattern (Provider Instantiation)
- Factory: `LLMProviderFactory.create(provider_name, model_name, **config)`
- Purpose: Encapsulate provider creation logic
- Benefit: Centralized configuration and dependency injection

### 7. Plugin Discovery Pattern
- Plugin Types: Artifact generators, chunking strategies
- Discovery: Scan directories for classes implementing interface
- Registration: Automatic via convention (inherit from base, implement methods)
- Configuration: Select plugins via rules.yaml

---

## Index Strategy

### High-Frequency Query Patterns

1. **Find pending RAG ingestion**:
   - Query: `SELECT * FROM meetings WHERE status='completed' AND rag_ingestion_status IS NULL`
   - Index: `idx_meeting_rag_status` on (rag_ingestion_status)

2. **Retrieve current file version**:
   - Query: `SELECT fv.* FROM file_versions fv JOIN files f ON f.current_version_id = fv.version_id WHERE f.file_id = ?`
   - Index: `idx_file_current_version` on (current_version_id)

3. **Find chunks for file version**:
   - Query: `SELECT * FROM chunks WHERE file_version_id = ? AND deleted = false ORDER BY chunk_index`
   - Index: `idx_chunk_file_version` on (file_version_id), `idx_chunk_index` on (chunk_index, file_version_id)

4. **Get embeddings for retrieval**:
   - Query: `SELECT * FROM embeddings WHERE collection_name = ? AND embedding_model = ?`
   - Index: `idx_embedding_collection` on (collection_name), `idx_embedding_model` on (embedding_model)

5. **Find affected artifacts when file changes**:
   - Query: `SELECT DISTINCT a.* FROM artifacts a JOIN artifact_versions av ON a.artifact_id = av.artifact_id JOIN artifact_links al ON av.version_id = al.artifact_version_id WHERE al.file_version_id = ?`
   - Index: `idx_artifact_link_file` on (file_version_id)

6. **Dashboard job list with filters**:
   - Query: `SELECT * FROM job_runs WHERE status = ? AND started_at BETWEEN ? AND ? ORDER BY started_at DESC`
   - Index: `idx_job_run_status` on (status), `idx_job_run_started` on (started_at)

7. **Backfill progress tracking**:
   - Query: `SELECT * FROM backfill_jobs WHERE status IN ('queued', 'running') ORDER BY started_at`
   - Index: `idx_backfill_status` on (status)

---

## Summary

This data model specification defines all 17 entities required for the RAG-Enhanced Meeting Intelligence System:

**EXISTING (KEEP AS-IS)**: 2 entities
- Participant
- ProcessingJob

**EXISTING (EXTEND)**: 3 entities
- Meeting (add file_id, rag_ingestion_status)
- Transcript (add deepgram_response, chunk_count, embedding_generated_at)
- Project (add display_name, description, ingestion_folder_path, artifact_retention_days, metadata)

**NEW**: 12 entities
- File, FileVersion, Chunk, Embedding
- JobRun, JobStep
- Artifact, ArtifactVersion, ArtifactLink
- BackfillJob

**Code Abstractions** (not database entities): 2
- ProcessingRule (configuration loaded from YAML)
- LLMProvider (Strategy pattern interface with OpenAI/Anthropic implementations, extensible for future providers)

**Key Features**:
- Speaker metadata preserved end-to-end (Deepgram → Chunk → ChromaDB → Citations)
- Soft delete pattern for data retention and audit trails
- Versioning pattern for files and artifacts with hash-based change detection
- Bridge pattern for loose coupling between transcription and RAG pipelines
- Multi-provider LLM support via Strategy + Factory patterns
- Incremental updates via ArtifactLinks for efficient reprocessing
- Comprehensive observability via JobRun/JobStep tracking
