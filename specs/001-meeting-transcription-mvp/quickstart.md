# QuickStart Guide: RAG-Enhanced Meeting Intelligence System

**Feature**: RAG-Enhanced Meeting Intelligence System
**Version**: 1.0.0
**Last Updated**: 2025-11-04

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Installation](#installation)
3. [Configuration](#configuration)
4. [Quick Start Scenarios](#quick-start-scenarios)
5. [API Usage Examples](#api-usage-examples)
6. [UI Usage](#ui-usage)
7. [CLI Usage](#cli-usage)
8. [Testing](#testing)
9. [Troubleshooting](#troubleshooting)

---

## Prerequisites

### System Requirements

- **Operating System**: Linux, macOS, or Windows (WSL2 recommended for Windows)
- **Python**: 3.11 or higher
- **RAM**: Minimum 8GB, recommended 16GB for optimal performance
- **Disk Space**: 100GB+ available (grows with document volume)
- **Network**: Internet connection for cloud LLM providers and Google APIs

### Required Services

**EXISTING (Already Configured)**:
- Google Workspace account with Meet access
- Google Cloud project with Meet API and Drive API enabled
- Deepgram API account and API key
- Google OAuth2 credentials or Service Account JSON

**NEW (For RAG Capabilities)**:
- **LLM Provider** (at least one required):
  - OpenAI API key (for GPT-4o and text-embedding-3-large) - Default provider
  - Anthropic API key (for Claude models) - Alternative provider

**Note**: Local model support (Ollama) is not included in MVP scope but architecture supports future extension via LLMProvider interface.

---

## Installation

### Step 1: Clone Repository

```bash
git clone https://github.com/yourorg/meethub.git
cd meethub
git checkout 001-meeting-transcription-mvp
```

### Step 2: Create Virtual Environment

```bash
# Create virtual environment
python3.11 -m venv venv

# Activate virtual environment
# Linux/macOS:
source venv/bin/activate
# Windows:
venv\Scripts\activate
```

### Step 3: Install Dependencies

```bash
# Install all dependencies from requirements.txt
pip install -r requirements.txt

# Verify key packages
pip list | grep -E "fastapi|chromadb|langchain|openai|anthropic|streamlit"
```

**Expected output**:
```
anthropic         0.25.0
chromadb          0.4.22
fastapi           0.104.1
langchain         0.1.10
openai            1.12.0
streamlit         1.32.0
```

### Step 4: Install System Dependencies

**For PDF OCR Support** (optional but recommended):

```bash
# Ubuntu/Debian
sudo apt-get update
sudo apt-get install tesseract-ocr tesseract-ocr-por

# macOS
brew install tesseract tesseract-lang

# Windows (via Chocolatey)
choco install tesseract
```

### Step 5: Initialize Database

```bash
# Run Alembic migrations to create database schema
alembic upgrade head

# Verify database
sqlite3 meethub.db ".tables"
```

**Expected output**:
```
alembic_version         file_versions          job_runs
artifact_links          files                  job_steps
artifact_versions       meetings               participants
artifacts               processing_jobs        projects
backfill_jobs           transcripts
chunks                  embeddings
```

### Step 6: Initialize ChromaDB

ChromaDB initializes automatically on first use, but you can verify:

```bash
# Create ChromaDB data directory
mkdir -p ./data/chroma_db

# Verify ChromaDB is accessible
python -c "import chromadb; client = chromadb.PersistentClient(path='./data/chroma_db'); print('ChromaDB initialized:', client.heartbeat())"
```

### Step 7: Setup Environment Configuration

```bash
# Copy example environment file
cp .env.example .env

# Edit .env with your credentials (see Configuration section)
nano .env  # or your preferred editor
```

---

## Configuration

### Environment Variables Overview

Edit `.env` file with the following configuration:

```bash
# ============================================================================
# EXISTING CONFIGURATION (Keep as-is)
# ============================================================================

# Google API Authentication Mode
# Options: 'service_account' (admin/org-wide) or 'oauth' (personal)
GOOGLE_AUTH_MODE=service_account

# Service Account Mode (for production with admin access)
GOOGLE_SERVICE_ACCOUNT_PATH=./service-account.json
GOOGLE_WORKSPACE_ADMIN_EMAIL=admin@yourdomain.com

# OAuth Mode (for personal account testing - no admin needed)
# GOOGLE_OAUTH_CREDENTIALS_PATH=./credentials.json
# GOOGLE_OAUTH_TOKEN_PATH=./token.json

# Google Drive Configuration
DRIVE_ROOT_FOLDER_ID=your_root_folder_id_here

# Deepgram API Configuration (EXISTING)
DEEPGRAM_API_KEY=your_deepgram_api_key_here
DEEPGRAM_MODEL=nova-2
ENABLE_DIARIZATION=true  # IMPORTANT: Required for speaker metadata
ENABLE_PUNCTUATION=true

# ============================================================================
# NEW CONFIGURATION (For RAG Capabilities)
# ============================================================================

# LLM Provider Selection (at least one provider required)
LLM_PROVIDER_PREFERENCE=openai  # Options: openai | anthropic (default: openai)

# OpenAI Configuration
OPENAI_API_KEY=sk-...your_openai_api_key...
OPENAI_CHAT_MODEL=gpt-4o
OPENAI_EMBEDDING_MODEL=text-embedding-3-large
OPENAI_MAX_RETRIES=3
OPENAI_TIMEOUT=30

# Anthropic Configuration
ANTHROPIC_API_KEY=sk-ant-...your_anthropic_api_key...
ANTHROPIC_CHAT_MODEL=claude-3-5-sonnet-20241022
ANTHROPIC_MAX_RETRIES=2
ANTHROPIC_TIMEOUT=30

# ChromaDB Configuration
CHROMADB_PATH=./data/chroma_db
CHROMADB_COLLECTION_NAME=meethub_embeddings

# File Upload Configuration
MAX_FILE_SIZE_MB=100
ALLOWED_FILE_TYPES=md,pdf,docx,json,txt

# RAG Configuration
RAG_CHUNK_SIZE=1200
RAG_CHUNK_OVERLAP=200
RAG_TOP_K_RETRIEVAL=10
RAG_MIN_SIMILARITY=0.6

# Processing Configuration
MAX_CONCURRENT_JOBS=3  # EXISTING - Applies to both transcription and RAG
RAG_INGESTION_ENABLED=true
RAG_BACKFILL_BATCH_SIZE=10

# Database Configuration (EXISTING)
DATABASE_URL=sqlite:///./meethub.db
DATABASE_ECHO=false

# Logging Configuration (EXISTING)
LOG_LEVEL=INFO
LOG_FORMAT=json

# Application Configuration (EXISTING)
APP_NAME=meethub
ENVIRONMENT=development
```

### Configuration Notes

**1. Google OAuth2 Credentials** (EXISTING):
- Place `service-account.json` or `credentials.json` in project root
- For personal mode setup, see `PERSONAL_MODE_SETUP.md`

**2. Deepgram API Key** (EXISTING):
- Required for meeting transcription
- Sign up at https://deepgram.com
- Ensure `ENABLE_DIARIZATION=true` for speaker metadata

**3. OpenAI API Key** (NEW - Primary):
- Required for RAG chat and embeddings
- Sign up at https://platform.openai.com
- Start with GPT-4o for quality, GPT-4o-mini for cost optimization

**4. Anthropic API Key** (NEW):
- For Claude models as alternative provider (user-selectable via LLM_PROVIDER_PREFERENCE)
- Sign up at https://console.anthropic.com

**5. File Upload Limits**:
- `MAX_FILE_SIZE_MB=100` - Adjust based on disk space
- Supported types: `.md`, `.pdf`, `.docx`, `.json`, `.txt`

---

## Quick Start Scenarios

### Scenario 1: Validate Existing Meeting Pipeline (User Story 0)

**Goal**: Verify the existing Google Meet + Deepgram pipeline still works with RAG integration.

```bash
# Step 1: Start the meeting processor
python -m src.scheduler

# Step 2: Trigger a test meeting detection (in another terminal)
python -c "
from src.services.google_meet import GoogleMeetService
service = GoogleMeetService()
meetings = service.poll_ended_meetings()
print(f'Detected {len(meetings)} ended meetings')
"

# Step 3: Monitor processing
sqlite3 meethub.db "SELECT meeting_id, status, rag_ingestion_status FROM meetings ORDER BY end_time DESC LIMIT 5;"

# Step 4: Verify RAG ingestion
sqlite3 meethub.db "SELECT f.file_id, f.relative_path, fv.content_hash FROM files f JOIN file_versions fv ON f.current_version_id = fv.version_id WHERE f.source_type = 'meeting';"
```

**Expected Flow**:
1. Meeting detected → `status='detected'`
2. Recording downloaded → `status='downloading'`
3. Deepgram transcription → `status='transcribing'`, creates `Transcript` with speaker labels
4. RAG bridge triggered → `rag_ingestion_status='processing'`, creates `File` and `FileVersion`
5. Chunks created with speaker metadata → Query `chunks` table
6. Embeddings generated → `rag_ingestion_status='completed'`

---

### Scenario 2: Upload PDF and Generate Summary (User Story 1 + 3)

**Goal**: Test file ingestion, chunking, embedding, and artifact generation end-to-end.

```bash
# Step 1: Create test PDF or use existing document
# Place file in: /tmp/test-docs/architecture.pdf

# Step 2: Upload via API
curl -X POST http://localhost:8000/api/v1/files/upload \
  -H "Content-Type: multipart/form-data" \
  -F "file=@/tmp/test-docs/architecture.pdf" \
  -F "project_id=1" \
  | jq

# Step 3: Monitor job progress
JOB_ID=$(curl -s http://localhost:8000/api/v1/jobs?limit=1 | jq -r '.jobs[0].job_id')
curl http://localhost:8000/api/v1/jobs/$JOB_ID | jq

# Step 4: Check generated artifacts
curl http://localhost:8000/api/v1/artifacts?kind=summary | jq

# Step 5: View artifact content
ARTIFACT_ID=$(curl -s "http://localhost:8000/api/v1/artifacts?kind=summary&limit=1" | jq -r '.artifacts[0].artifact_id')
curl "http://localhost:8000/api/v1/artifacts/$ARTIFACT_ID/versions/1/content?format=markdown"
```

**Expected Results**:
- File uploaded successfully (202 response)
- Job progresses through steps: `normalize` → `chunk` → `embed` → `generate_summary`
- Artifacts created: summary, decisions (if configured), entities (if configured)
- Chunks queryable in ChromaDB

---

### Scenario 3: Query Across Meetings with RAG Chat (User Story 5)

**Goal**: Test RAG retrieval with cross-source queries including meeting speaker metadata.

```bash
# Step 1: Ensure at least 2 meetings are transcribed and ingested
sqlite3 meethub.db "SELECT COUNT(*) FROM meetings WHERE rag_ingestion_status = 'completed';"

# Step 2: Submit chat query via API
curl -X POST http://localhost:8000/api/v1/chat/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Who decided to use Kubernetes for deployment, and what does the architecture document say about scalability?",
    "project_id": 1,
    "top_k": 10,
    "min_similarity": 0.6,
    "llm_provider": "openai",
    "llm_model": "gpt-4o"
  }' | jq

# Step 3: Query with speaker filter
curl -X POST http://localhost:8000/api/v1/chat/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What did Alice say about deployment?",
    "top_k": 5
  }' | jq '.citations[] | select(.speaker != null)'
```

**Expected Response Structure**:
```json
{
  "answer": "According to Alice in the standup on 2025-11-01 at 14:32, the team decided to use Kubernetes for deployment...",
  "citations": [
    {
      "source_type": "meeting",
      "file_path": "meeting://meeting-123",
      "speaker": "Speaker 0",
      "speaker_name": "Alice Smith",
      "timestamp": "00:14:32",
      "similarity_score": 0.89,
      "chunk_text": "I think we should use Kubernetes..."
    },
    {
      "source_type": "document",
      "file_path": "/ingest/project-alpha/architecture.pdf",
      "page": 12,
      "similarity_score": 0.87,
      "chunk_text": "Kubernetes provides horizontal scaling..."
    }
  ],
  "retrieval_metadata": {
    "chunks_retrieved": 10,
    "avg_similarity": 0.78,
    "max_similarity": 0.89,
    "llm_provider": "openai",
    "llm_model": "gpt-4o",
    "tokens_used": 3200,
    "cost_estimate": 0.08
  }
}
```

---

### Scenario 4: Backfill Historical Meetings (User Story 6)

**Goal**: Bulk-process existing transcriptions through RAG pipeline.

```bash
# Step 1: Check how many meetings need RAG ingestion
sqlite3 meethub.db "SELECT COUNT(*) FROM meetings WHERE status = 'completed' AND rag_ingestion_status IS NULL;"

# Step 2: Create folder with historical meeting transcripts
mkdir -p /tmp/historical-meetings
cp existing-transcripts/*.md /tmp/historical-meetings/

# Step 3: Trigger backfill via API
curl -X POST http://localhost:8000/api/v1/backfill \
  -H "Content-Type: application/json" \
  -d '{
    "target_path": "/tmp/historical-meetings/",
    "project_id": 1,
    "recursive": true,
    "file_pattern": "*.md"
  }' | jq

# Step 4: Monitor backfill progress
BACKFILL_ID=$(curl -s http://localhost:8000/api/v1/backfill?status=running | jq -r '.backfill_jobs[0].backfill_job_id')
watch -n 5 "curl -s http://localhost:8000/api/v1/backfill/$BACKFILL_ID | jq '.progress_percentage, .processed_count, .failed_count'"

# Step 5: Pause if needed (e.g., API quota limit)
curl -X POST http://localhost:8000/api/v1/backfill/$BACKFILL_ID/pause

# Step 6: Resume after cooldown
curl -X POST http://localhost:8000/api/v1/backfill/$BACKFILL_ID/resume

# Step 7: Get final summary report
curl http://localhost:8000/api/v1/backfill/$BACKFILL_ID/summary | jq
```

**Expected Behavior**:
- Files discovered and queued
- Processing respects `MAX_CONCURRENT_JOBS=3` limit
- Progress updates every 30 seconds
- Failed files logged with specific error reasons
- Summary report includes cost estimates and artifact counts

---

### Scenario 5: Switch Between LLM Providers (User Story 2)

**Goal**: Compare OpenAI and Anthropic by switching LLM_PROVIDER_PREFERENCE and reprocessing files.

**Method 1: Global Provider Switching (via .env)**

```bash
# Step 1: Process with OpenAI (default)
echo "LLM_PROVIDER_PREFERENCE=openai" >> .env
python -m src.cli process-file --path test-meeting.md

# Wait for completion, then check artifacts
FILE_ID=$(curl -s http://localhost:8000/api/v1/files?limit=1 | jq -r '.files[0].file_id')
curl http://localhost:8000/api/v1/artifacts?file_id=$FILE_ID | jq '.artifacts[] | {kind, llm_provider, created_at}'

# Step 2: Switch to Anthropic and reprocess
sed -i 's/LLM_PROVIDER_PREFERENCE=openai/LLM_PROVIDER_PREFERENCE=anthropic/' .env
# Restart application to reload env vars
python -m src.cli process-file --path test-meeting.md

# Step 3: Compare artifacts
curl http://localhost:8000/api/v1/artifacts?file_id=$FILE_ID | jq '.artifacts | group_by(.kind) | map({kind: .[0].kind, providers: map(.llm_provider)})'
```

**Method 2: Per-Artifact Provider Override (via rules.yaml)**

Edit `config/rules.yaml` to use different providers for different artifact types:

```yaml
artifact_generation_rules:
  - name: "provider-comparison"
    match_criteria:
      path_glob: "test://**"
      mime_types: ["text/markdown"]

    processing_steps:
      - step: "generate_artifacts"
        artifacts:
          # Use OpenAI for summaries
          - kind: "summary"
            generator: "SummaryGenerator"
            llm_provider: "openai"
            llm_model: "gpt-4o"
            prompt_template: "meeting_summary.txt"

          # Use Anthropic for decisions
          - kind: "decisions_index"
            generator: "DecisionsGenerator"
            llm_provider: "anthropic"
            llm_model: "claude-3-5-sonnet-20241022"
            prompt_template: "meeting_decisions.txt"
```

**Expected Results**:
```json
{
  "artifacts": [
    {
      "kind": "summary",
      "llm_provider": "openai",
      "llm_model": "gpt-4o",
      "prompt_tokens": 1500,
      "completion_tokens": 800,
      "cost_usd": 0.0195,
      "latency_seconds": 2.1
    },
    {
      "kind": "decisions_index",
      "llm_provider": "anthropic",
      "llm_model": "claude-3-5-sonnet-20241022",
      "prompt_tokens": 1600,
      "completion_tokens": 700,
      "cost_usd": 0.0153,
      "latency_seconds": 2.8
    }
  ]
}
```

---

## API Usage Examples

### Upload File

```bash
curl -X POST http://localhost:8000/api/v1/files/upload \
  -H "Content-Type: multipart/form-data" \
  -F "file=@/path/to/document.pdf" \
  -F "project_id=1" \
  -F "force_reprocess=false"
```

### Check Job Status

```bash
# List recent jobs
curl http://localhost:8000/api/v1/jobs?limit=10&status=running

# Get specific job details
curl http://localhost:8000/api/v1/jobs/123

# Get step logs
curl http://localhost:8000/api/v1/jobs/123/steps/5/logs
```

### Get Artifacts

```bash
# List all summaries
curl "http://localhost:8000/api/v1/artifacts?kind=summary&project_id=1"

# Get artifact by key
curl "http://localhost:8000/api/v1/artifacts/by-key/summary:project-alpha:meeting-123"

# Get artifact content as JSON
curl "http://localhost:8000/api/v1/artifacts/42/versions/1/content?format=json"

# Get artifact content as Markdown
curl "http://localhost:8000/api/v1/artifacts/42/versions/1/content?format=markdown"
```

### Submit Chat Query

```bash
curl -X POST http://localhost:8000/api/v1/chat/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What are the main architectural decisions?",
    "project_id": 1,
    "top_k": 10,
    "min_similarity": 0.6,
    "llm_provider": "openai"
  }'
```

### Create Backfill Job

```bash
# Folder-based backfill
curl -X POST http://localhost:8000/api/v1/backfill \
  -H "Content-Type: application/json" \
  -d '{
    "target_path": "/ingest/historical/",
    "project_id": 1,
    "recursive": true,
    "file_pattern": "*.md"
  }'

# File list-based backfill
curl -X POST http://localhost:8000/api/v1/backfill \
  -H "Content-Type: application/json" \
  -d '{
    "file_list": [
      "/ingest/meeting-001.md",
      "/ingest/meeting-002.md"
    ],
    "project_id": 1
  }'
```

### Control Backfill Job

```bash
# Pause backfill
curl -X POST http://localhost:8000/api/v1/backfill/42/pause

# Resume backfill
curl -X POST http://localhost:8000/api/v1/backfill/42/resume

# Cancel backfill
curl -X POST http://localhost:8000/api/v1/backfill/42/cancel

# Get summary report
curl http://localhost:8000/api/v1/backfill/42/summary
```

---

## UI Usage

### Start Streamlit Dashboard

```bash
# Start Streamlit server
streamlit run src/ui/app.py

# Access UI at http://localhost:8501
```

### File Upload Page

1. Navigate to **File Upload** tab
2. Select files (drag-and-drop or browse)
3. Choose project from dropdown
4. Click **Upload** button
5. Monitor upload progress
6. View job ID for tracking

### Jobs Dashboard

1. Navigate to **Jobs Dashboard** tab
2. Apply filters:
   - Status: `queued`, `running`, `success`, `failed`, `partial`
   - Date range: Last 7 days, 30 days, custom
   - Project: Select from dropdown
3. Click job row to expand details:
   - Input files with download links
   - Step-by-step timeline with status icons
   - Logs per step (click to expand)
   - Output artifacts (click to preview)
4. Use **Retry** button for failed jobs

### Chat Interface

1. Navigate to **RAG Chat** tab
2. Select project scope (or "All Projects")
3. Enter query in text box:
   - Example: "Who decided to use Kubernetes?"
4. Adjust settings (optional):
   - Top-K chunks: 5-20
   - Similarity threshold: 0.5-0.9
   - LLM provider: OpenAI or Anthropic (based on LLM_PROVIDER_PREFERENCE)
5. Click **Submit** or press Enter
6. View response with citations:
   - Click citation to jump to source
   - Meetings: Show speaker + timestamp
   - Documents: Show page/section
7. Chat history maintained in session

### Artifacts Browser

1. Navigate to **Artifacts** tab
2. Filter by:
   - Artifact kind: summary, decisions, entities, timeline
   - Project
   - Date range
3. Click artifact to view:
   - Current version content (syntax highlighted)
   - Source files linked
   - Version history with timestamps
   - Metadata (LLM provider, model, cost)
4. Download artifact as JSON or Markdown

---

## CLI Usage

### Process Meeting

```bash
# Process specific meeting by ID
python -m src.cli process-meeting <meeting-id>

# Example
python -m src.cli process-meeting meeting-20251104-143000

# Options
python -m src.cli process-meeting <meeting-id> \
  --force-retranscribe \
  --force-reingest
```

### Ingest File

```bash
# Ingest single file
python -m src.cli ingest-file /path/to/document.pdf --project-id 1

# Ingest multiple files
python -m src.cli ingest-file /path/to/docs/*.pdf --project-id 1 --batch

# Ingest with custom rules
python -m src.cli ingest-file /path/to/doc.md --rule-name custom-rule
```

### Generate Artifacts

```bash
# Generate artifacts for specific file version
python -m src.cli generate-artifacts --file-version-id 123

# Generate specific artifact kinds
python -m src.cli generate-artifacts --file-version-id 123 --kinds summary,decisions

# Regenerate with different provider
python -m src.cli generate-artifacts --file-version-id 123 \
  --provider anthropic \
  --model claude-3-5-sonnet-20241022
```

### Backfill Operations

```bash
# Trigger backfill from CLI
python -m src.cli backfill --target-path /ingest/historical/ --project-id 1

# Monitor backfill
python -m src.cli backfill-status --backfill-job-id 42

# Cancel backfill
python -m src.cli backfill-cancel --backfill-job-id 42
```

### Utility Commands

```bash
# Health check
python -m src.cli health-check

# Database stats
python -m src.cli stats

# Clean up old artifacts (respecting retention policy)
python -m src.cli cleanup --dry-run
python -m src.cli cleanup --confirm

# Rebuild ChromaDB index (if corrupted)
python -m src.cli rebuild-index --confirm
```

---

## Testing

### Run All Tests

```bash
# Run full test suite
pytest

# With coverage report
pytest --cov=src --cov-report=html

# View coverage in browser
open htmlcov/index.html
```

### Unit Tests

```bash
# Test specific modules
pytest tests/unit/test_file_ingestion.py
pytest tests/unit/test_chunking.py
pytest tests/unit/test_embeddings.py
pytest tests/unit/test_artifact_generation.py

# Test with verbose output
pytest tests/unit/ -v

# Test with specific markers
pytest -m "rag" -v  # Only RAG-related tests
```

### Integration Tests

```bash
# Test end-to-end flows
pytest tests/integration/

# Test specific user story
pytest tests/integration/test_us1_file_ingestion.py
pytest tests/integration/test_us5_rag_chat.py

# Test with real API calls (requires credentials)
pytest tests/integration/ --real-api
```

### Contract Tests

```bash
# Test API contract compliance with OpenAPI spec
pytest tests/contract/test_api_spec.py

# Test against running server
pytest tests/contract/ --base-url http://localhost:8000
```

### Performance Tests

```bash
# Load testing for chat queries
pytest tests/performance/test_chat_latency.py

# Backfill performance
pytest tests/performance/test_backfill_throughput.py
```

---

## Troubleshooting

### Issue 1: ChromaDB Initialization Errors

**Symptom**: `chromadb.errors.ChromaException: Could not connect to ChromaDB`

**Solutions**:

```bash
# Check if ChromaDB directory exists and has write permissions
ls -la ./data/chroma_db
chmod -R 755 ./data/chroma_db

# Remove corrupted ChromaDB data and reinitialize
rm -rf ./data/chroma_db
mkdir -p ./data/chroma_db
python -m src.cli rebuild-index --confirm

# Verify ChromaDB health
python -c "import chromadb; client = chromadb.PersistentClient(path='./data/chroma_db'); print(client.heartbeat())"
```

---

### Issue 2: LLM API Authentication Failures

**Symptom**: `openai.AuthenticationError: Invalid API key`

**Solutions**:

```bash
# Verify API key is set correctly
echo $OPENAI_API_KEY

# Test OpenAI API directly
curl https://api.openai.com/v1/models \
  -H "Authorization: Bearer $OPENAI_API_KEY"

# Check .env file is loaded
python -c "from src.config import settings; print(settings.OPENAI_API_KEY[:10] + '...')"

# For Anthropic
curl https://api.anthropic.com/v1/messages \
  -H "x-api-key: $ANTHROPIC_API_KEY" \
  -H "anthropic-version: 2023-06-01" \
  -H "content-type: application/json" \
  -d '{"model":"claude-3-5-sonnet-20241022","max_tokens":1024,"messages":[{"role":"user","content":"Hello"}]}'
```

---

### Issue 3: File Upload Size Limits

**Symptom**: `FileTooLarge: File size exceeds 100MB limit`

**Solutions**:

```bash
# Increase limit in .env
echo "MAX_FILE_SIZE_MB=500" >> .env

# Restart FastAPI server
pkill -f "uvicorn src.api.main:app"
uvicorn src.api.main:app --reload

# For very large files, split before upload
split -b 50M large-file.pdf large-file-part-

# Or use streaming upload for large files
curl -X POST http://localhost:8000/api/v1/files/upload \
  -H "Content-Type: multipart/form-data" \
  -F "file=@large-file.pdf" \
  --limit-rate 10M
```

---

### Issue 4: Meeting Transcription Not Triggering RAG Ingestion

**Symptom**: Meetings have `status='completed'` but `rag_ingestion_status` is NULL

**Solutions**:

```bash
# Check if RAG bridge is enabled
grep RAG_INGESTION_ENABLED .env

# Enable RAG bridge
echo "RAG_INGESTION_ENABLED=true" >> .env

# Manually trigger RAG ingestion for completed meetings
sqlite3 meethub.db "SELECT meeting_id FROM meetings WHERE status = 'completed' AND rag_ingestion_status IS NULL;" | while read meeting_id; do
  python -m src.cli trigger-rag-ingestion --meeting-id $meeting_id
done

# Check bridge logs
grep "MeetingRAGBridge" logs/app.log

# Restart scheduler to apply changes
pkill -f "python -m src.scheduler"
python -m src.scheduler &
```

---

### Issue 6: Low Retrieval Quality / No Results

**Symptom**: Chat queries return "I don't have information about that" for known content

**Solutions**:

```bash
# Check if embeddings were generated
sqlite3 meethub.db "SELECT COUNT(*) FROM embeddings;"
sqlite3 meethub.db "SELECT COUNT(*) FROM chunks WHERE deleted = false;"

# Verify ChromaDB collection has vectors
python -c "
import chromadb
client = chromadb.PersistentClient(path='./data/chroma_db')
collection = client.get_collection('meethub_embeddings')
print(f'Total embeddings in ChromaDB: {collection.count()}')
"

# Lower similarity threshold for testing
curl -X POST http://localhost:8000/api/v1/chat/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "your test query",
    "min_similarity": 0.3
  }' | jq '.retrieval_metadata'

# Check embedding model consistency
sqlite3 meethub.db "SELECT DISTINCT embedding_model FROM embeddings;"

# Regenerate embeddings if model mismatch
python -m src.cli rebuild-embeddings --embedding-model text-embedding-3-large --confirm
```

---

### Issue 7: Disk Space Full

**Symptom**: `OSError: [Errno 28] No space left on device`

**Solutions**:

```bash
# Check disk usage
df -h
du -sh ./data/chroma_db
du -sh ./meethub.db

# Clean up old file versions (soft deleted)
sqlite3 meethub.db "SELECT COUNT(*) FROM files WHERE deleted = true;"
python -m src.cli cleanup --hard-delete --confirm

# Archive old ChromaDB collections
python -m src.cli archive-embeddings --older-than 90d --backup-path /backup/

# Enable artifact retention policy
sqlite3 meethub.db "UPDATE projects SET artifact_retention_days = 90 WHERE artifact_retention_days IS NULL;"
python -m src.cli cleanup --apply-retention --confirm
```

---

### Issue 8: Slow Query Performance

**Symptom**: Chat queries take >10 seconds to respond

**Solutions**:

```bash
# Check database indexes
sqlite3 meethub.db ".schema" | grep -i index

# Analyze query performance
EXPLAIN QUERY PLAN SELECT * FROM chunks WHERE file_version_id = 123;

# Rebuild database indexes
sqlite3 meethub.db "REINDEX;"

# Optimize ChromaDB collection
python -c "
import chromadb
client = chromadb.PersistentClient(path='./data/chroma_db')
collection = client.get_collection('meethub_embeddings')
# ChromaDB auto-optimizes, but you can force rebuild:
# client.delete_collection('meethub_embeddings')
# Then rebuild with: python -m src.cli rebuild-index
"

# Reduce top-K retrieval for faster responses
curl -X POST http://localhost:8000/api/v1/chat/query \
  -d '{"query": "test", "top_k": 5}'  # Instead of default 10

# Use smaller LLM model for speed
curl -X POST http://localhost:8000/api/v1/chat/query \
  -d '{"query": "test", "llm_model": "gpt-4o-mini"}'
```

---

## Additional Resources

- **API Documentation**: http://localhost:8000/docs (Swagger UI when server running)
- **Specification**: See `/specs/001-meeting-transcription-mvp/spec.md` for full requirements
- **Data Model**: See `/specs/001-meeting-transcription-mvp/data-model.md` for entity relationships
- **Architecture Decisions**: See `/specs/001-meeting-transcription-mvp/research.md` for technology choices
- **Project Constitution**: See `/.specify/memory/constitution.md` for development principles

---

## Next Steps

After completing the quickstart scenarios:

1. **Configure Processing Rules**: Edit `rules.yaml` to customize artifact types and LLM providers
2. **Set Up Projects**: Create project-specific ingestion folders and classification rules
3. **Integrate with Workflows**: Set up file watchers for automatic ingestion from document repositories
4. **Monitor Costs**: Track LLM usage via job metrics and optimize provider selection
5. **Scale Up**: Migrate from SQLite to PostgreSQL and ChromaDB to Qdrant for production scale

For production deployment, see `DEPLOYMENT.md` (future document).

---

**End of QuickStart Guide**
