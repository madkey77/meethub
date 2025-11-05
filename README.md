# MeetHub - Automated Google Meet Transcription & Organization

Automatically detect ended Google Meet meetings, download recordings, transcribe with speaker identification using Deepgram AI, and save formatted transcripts to Google Drive organized by project.

**🚀 New to MeetHub?** Choose your setup:
- **Personal Mode (Testing)**: [Personal Mode Setup](PERSONAL_MODE_SETUP.md) - No admin access needed, works with your own Google account
- **Organization Mode (Production)**: [Getting Started Guide](GETTING_STARTED.md) - Full admin access, organization-wide deployment

## Table of Contents

- [Features](#features)
- [Quick Start](#quick-start)
  - [Prerequisites](#prerequisites)
  - [Step-by-Step Setup](#step-by-step-setup)
  - [Quick Reference](#quick-reference)
  - [What Happens After Setup?](#what-happens-after-setup)
- [Architecture](#architecture)
- [Configuration](#configuration)
- [Testing](#testing)
- [Deployment](#deployment)
- [Development](#development)
- [Monitoring](#monitoring)
- [Troubleshooting](#troubleshooting)
- [Documentation](#documentation)

## Features

- **Automatic Meeting Detection**: Polls Google Meet API every 15 minutes for ended meetings
- **Cloud Transcription**: Uses Deepgram API for fast, accurate transcription with speaker diarization
- **Project-Based Organization**: Automatically classifies meetings into project folders based on rules
- **Background Processing**: Runs continuously with concurrent processing (up to 3 meetings simultaneously)
- **Retry Logic**: Automatic retry with exponential backoff for failed operations
- **Structured Logging**: JSON logs for production monitoring and debugging

## Quick Start

Follow these steps to get MeetHub up and running in your environment.

### Prerequisites

Before starting, ensure you have:

- **Python 3.11+** installed
- **Google Workspace account** with Google Meet enabled
- **Google Cloud Platform account** (for API access)
- **Deepgram account** (for AI transcription)
- **Docker and Docker Compose** (recommended for production)
- **Git** for cloning the repository

### Step-by-Step Setup

#### 1. Clone the Repository

```bash
git clone https://github.com/your-org/meethub.git
cd meethub
```

#### 2. Install Python Dependencies

```bash
# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

#### 3. Configure Google Cloud Platform

##### 3.1 Create Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project (e.g., "MeetHub")
3. Note your Project ID

##### 3.2 Enable Required APIs

Enable these APIs in your Google Cloud project:
```bash
# Go to: https://console.cloud.google.com/apis/library
```

Required APIs:
- **Google Meet API** (`meet.googleapis.com`)
- **Google Calendar API** (`calendar-json.googleapis.com`)
- **Google Drive API** (`drive.googleapis.com`)

##### 3.3 Create Service Account

1. Navigate to **IAM & Admin > Service Accounts**
2. Click **Create Service Account**
3. Name: `meethub-service-account`
4. Description: "Service account for MeetHub transcription automation"
5. Click **Create and Continue**
6. Skip role assignment (not needed)
7. Click **Done**

##### 3.4 Generate Service Account Key

1. Click on the newly created service account
2. Go to **Keys** tab
3. Click **Add Key > Create New Key**
4. Choose **JSON** format
5. Download the key file
6. Save it as `service-account.json` in the MeetHub project root

⚠️ **IMPORTANT**: Never commit this file to git! It's already in `.gitignore`.

##### 3.5 Enable Domain-Wide Delegation

1. In Service Account details, click **Show Advanced Settings**
2. Click **Enable Google Workspace Domain-wide Delegation**
3. Note the **Client ID** (you'll need it next)

##### 3.6 Configure OAuth Scopes in Google Workspace Admin

1. Go to [Google Workspace Admin Console](https://admin.google.com/)
2. Navigate to **Security > Access and data control > API controls**
3. Click **Manage Domain Wide Delegation**
4. Click **Add new**
5. Enter the **Client ID** from step 3.5
6. Add these OAuth scopes (comma-separated):
   ```
   https://www.googleapis.com/auth/calendar.readonly,
   https://www.googleapis.com/auth/meetings.space.readonly,
   https://www.googleapis.com/auth/drive.file
   ```
7. Click **Authorize**

#### 4. Setup Google Drive Folders

##### 4.1 Create Folder Structure

1. Go to [Google Drive](https://drive.google.com/)
2. Create root folder: **"MeetHub Transcripts"**
3. Inside root folder, create project subfolders:
   - **VNO**
   - **CLIENTE_X**
   - **NOVOS_CLIENTES**
   - **GERAL** (default/fallback folder)

##### 4.2 Share Folders with Service Account

For each folder (including root):
1. Right-click folder → **Share**
2. Enter the service account email (from `service-account.json` - the `client_email` field)
3. Set permission to **Editor**
4. Click **Send**

##### 4.3 Get Folder IDs

For each folder:
1. Open the folder in Google Drive
2. Copy the folder ID from URL: `https://drive.google.com/drive/folders/FOLDER_ID_HERE`
3. Note these IDs for configuration

#### 5. Get Deepgram API Key

1. Sign up at [Deepgram](https://console.deepgram.com/signup)
2. Go to [API Keys](https://console.deepgram.com/project/default/settings/api-keys)
3. Create new API key
4. Copy the key (starts with a long alphanumeric string)

#### 6. Configure Environment Variables

```bash
# Copy example environment file
cp .env.example .env
```

Edit `.env` file with your values:

```bash
# Google API Configuration
GOOGLE_SERVICE_ACCOUNT_PATH=./service-account.json
GOOGLE_WORKSPACE_ADMIN_EMAIL=admin@yourdomain.com  # Your Workspace admin email

# Google Drive Folder IDs
DRIVE_ROOT_FOLDER_ID=your_root_folder_id_here      # From step 4.3

# Deepgram API
DEEPGRAM_API_KEY=your_deepgram_api_key_here        # From step 5

# Polling Configuration (optional - defaults shown)
POLL_INTERVAL_MINUTES=15          # How often to check for new meetings
MAX_CONCURRENT_JOBS=3             # Max meetings to process simultaneously
MAX_RETRIES=3                     # Max retry attempts for failed jobs

# Transcription Configuration (optional)
TRANSCRIPTION_LANGUAGE=pt         # Language code (pt=Portuguese, en=English)
DEEPGRAM_MODEL=nova-2             # Deepgram model to use
TRANSCRIPTION_TIMEOUT_SECONDS=300 # Timeout for transcription (5 minutes)

# Database (optional - SQLite default)
DATABASE_URL=sqlite:///./meethub.db

# Logging (optional)
LOG_LEVEL=INFO                    # DEBUG, INFO, WARNING, ERROR, CRITICAL
LOG_FORMAT=json                   # json or console
```

#### 7. Configure Project Folders Mapping

Edit `project_folders.json` with your actual folder IDs:

```json
{
  "VNO": "PASTE_VNO_FOLDER_ID_HERE",
  "CLIENTE_X": "PASTE_CLIENTE_X_FOLDER_ID_HERE",
  "NOVOS_CLIENTES": "PASTE_NOVOS_CLIENTES_FOLDER_ID_HERE",
  "GERAL": "PASTE_GERAL_FOLDER_ID_HERE"
}
```

Replace each `PASTE_*_FOLDER_ID_HERE` with the actual folder IDs from step 4.3.

#### 8. Configure Classification Rules (Optional)

Edit `classification_rules.json` to customize how meetings are classified:

```json
{
  "rules": [
    {
      "project": "VNO",
      "type": "title_prefix",
      "pattern": "[VNO]"
    },
    {
      "project": "CLIENTE_X",
      "type": "participant_domain",
      "pattern": "@cliente.com"
    },
    {
      "project": "NOVOS_CLIENTES",
      "type": "keyword",
      "pattern": "kickoff|onboarding|demo"
    }
  ],
  "default": "GERAL"
}
```

**Rule Types:**
- `title_prefix`: Match text in meeting title (e.g., "[VNO]")
- `participant_domain`: Match email domain of participants (e.g., "@cliente.com")
- `keyword`: Match keywords with regex (e.g., "kickoff|onboarding")

**Note**: First matching rule wins. Meetings that don't match any rule go to default project.

#### 9. Initialize Database

```bash
# Make sure virtual environment is activated
source venv/bin/activate  # or venv\Scripts\activate on Windows

# Run database migrations
alembic upgrade head
```

You should see:
```
INFO  [alembic.runtime.migration] Running upgrade -> 20251101_001_initial_schema
INFO  [alembic.runtime.migration] Running upgrade -> 20251101_002_seed_default_projects
```

#### 10. Test Configuration

Before running the full service, test your configuration:

```bash
# Test Google authentication
python -m src.cli test-auth

# Test classification rules
python -m src.cli test-classification

# Show current configuration
python -m src.cli show-config

# Test polling (optional - will query for meetings in last 24 hours)
python -m src.cli poll-meetings --since-hours 24
```

If all tests pass, you're ready to run the service!

#### 11. Run the Service

##### Option A: Development Mode (Foreground)

```bash
# Run in foreground with console logging
LOG_FORMAT=console python -m src.main
```

Press `Ctrl+C` to stop.

##### Option B: Production Mode (Docker - Recommended)

```bash
# Build and start the service
docker-compose up -d

# View logs
docker-compose logs -f meethub

# Check status
docker-compose ps

# Stop the service
docker-compose down
```

##### Option C: Production Mode (Background Process)

```bash
# Run in background
nohup python -m src.main > meethub.log 2>&1 &

# View logs
tail -f meethub.log

# Stop (find PID and kill)
ps aux | grep "src.main"
kill <PID>
```

#### 12. Verify It's Working

After starting the service:

1. **Check logs** for successful startup:
   ```bash
   # Docker
   docker-compose logs meethub | grep "MeetHub starting"

   # Background process
   tail -f meethub.log | grep "MeetHub starting"
   ```

2. **Wait for first poll** (occurs immediately, then every 15 minutes):
   ```bash
   docker-compose logs meethub | grep "Starting meeting polling job"
   ```

3. **Hold a test meeting**:
   - Start a Google Meet with recording enabled
   - End the meeting
   - Wait 2-5 minutes for recording to process
   - Wait for next polling interval (up to 15 minutes)

4. **Check for processed meeting**:
   ```bash
   # View logs
   docker-compose logs meethub | grep "Meeting processing completed"

   # Check database
   sqlite3 meethub.db "SELECT meeting_id, title, status FROM meetings;"

   # Check Google Drive for transcript
   ```

### Quick Reference

**Configuration Files:**
- `.env` - Environment variables (create from `.env.example`)
- `service-account.json` - Google service account key (download from GCP)
- `project_folders.json` - Drive folder ID mappings
- `classification_rules.json` - Meeting classification rules

**Important Commands:**
```bash
# Test configuration
python -m src.cli test-auth
python -m src.cli test-classification

# Manual operations
python -m src.cli poll-meetings --since-hours 24
python -m src.cli process-meeting --meeting-id <id>

# Docker operations
docker-compose up -d          # Start service
docker-compose logs -f        # View logs
docker-compose restart        # Restart service
docker-compose down           # Stop service

# Database operations
alembic upgrade head          # Apply migrations
sqlite3 meethub.db            # Access database
```

### What Happens After Setup?

Once running, MeetHub will:

1. **Poll every 15 minutes** for ended Google Meet meetings
2. **Check for recordings** (meetings without recordings are skipped)
3. **Download recordings** to temporary storage
4. **Transcribe with Deepgram** (speaker diarization enabled)
5. **Classify meetings** based on your rules
6. **Upload transcripts** to appropriate Google Drive folders
7. **Clean up** temporary files
8. **Retry failures** automatically with exponential backoff
9. **Log everything** for monitoring and debugging

You can monitor all activity through the logs!

## Architecture

```
src/
├── models/          # Database models (SQLAlchemy)
├── services/        # Business logic
│   ├── google_meet.py      # Google Meet API client
│   ├── google_drive.py     # Google Drive API client
│   ├── transcription.py    # Deepgram integration
│   ├── classification.py   # Project classification
│   └── scheduler.py        # Background job scheduling
├── utils/           # Utilities
│   ├── logging.py          # Structured logging
│   ├── retry.py            # Retry decorator
│   ├── validators.py       # Input validation
│   └── exceptions.py       # Custom exceptions
├── config.py        # Configuration (Pydantic)
└── main.py          # Application entry point
```

## Configuration

All configuration is managed via environment variables in `.env`:

### Required Variables
- `GOOGLE_SERVICE_ACCOUNT_PATH` - Path to service account JSON
- `DRIVE_ROOT_FOLDER_ID` - Google Drive root folder ID
- `DEEPGRAM_API_KEY` - Deepgram API key

### Optional Variables
- `POLL_INTERVAL_MINUTES` - Polling interval (default: 15)
- `MAX_CONCURRENT_JOBS` - Max concurrent processing (default: 3)
- `MAX_RETRIES` - Max retry attempts (default: 3)
- `TRANSCRIPTION_LANGUAGE` - Language code (default: pt)
- `LOG_LEVEL` - Logging level (default: INFO)

See [.env.example](.env.example) for full list.

## Testing

```bash
# Run all tests
pytest

# Run unit tests only
pytest tests/unit/

# Run with coverage
pytest --cov=src --cov-report=html

# Run integration tests (requires API credentials)
pytest tests/integration/ --run-integration

# Run end-to-end tests
pytest tests/e2e/ --run-e2e
```

## Deployment

### Docker Deployment (Recommended)

```bash
# Build and start
docker-compose up -d

# View logs
docker-compose logs -f

# Stop
docker-compose down
```

### Manual Deployment

```bash
# Run in background
nohup python -m src.main > meethub.log 2>&1 &

# Check logs
tail -f meethub.log
```

## Project Structure

```
meethub/
├── src/                    # Source code
├── tests/                  # Test suite
├── alembic/                # Database migrations
├── specs/                  # Feature specifications
├── .env.example            # Environment template
├── requirements.txt        # Python dependencies
├── pyproject.toml          # Project metadata
├── Dockerfile              # Container definition
├── docker-compose.yml      # Compose configuration
└── README.md               # This file
```

## Development

### Running Locally

```bash
# Setup virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run database migrations
alembic upgrade head

# Start application
python -m src.main
```

### Creating Database Migrations

```bash
# Auto-generate migration from model changes
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head

# Rollback migration
alembic downgrade -1
```

### Code Quality

```bash
# Format code
black src/ tests/

# Lint code
ruff check src/ tests/

# Type checking
mypy src/
```

## Monitoring

### Health Check

```bash
# Check if service is running (if health endpoint implemented)
curl http://localhost:8000/health
```

### Logs

Logs are written to stdout in JSON format (or console format in development).

```bash
# View all logs
docker-compose logs -f meethub

# Filter by level
cat meethub.log | jq 'select(.level == "ERROR")'

# Filter by meeting
cat meethub.log | jq 'select(.meeting_id == "abc123")'
```

## Troubleshooting

### Common Issues

#### Authentication Errors

**Issue**: "Authentication failed" or "Service account authentication error"
- **Solution**:
  1. Verify `service-account.json` file exists and is valid JSON
  2. Check domain-wide delegation is enabled in Google Workspace Admin Console
  3. Ensure OAuth scopes are configured: `meet.readonly`, `calendar.readonly`, `drive.file`
  4. Verify `GOOGLE_WORKSPACE_ADMIN_EMAIL` is set correctly in `.env`

#### Meeting Detection Issues

**Issue**: "No meetings found" after polling
- **Solution**:
  1. Ensure meetings have **recordings enabled** (host must enable recording)
  2. Wait 2-5 minutes after meeting ends for recording to finalize
  3. Check that admin email has access to Google Meet data
  4. Verify polling time window: check `POLL_INTERVAL_MINUTES` setting

#### Transcription Errors

**Issue**: "Deepgram API error" or "Transcription failed"
- **Solution**:
  1. Verify `DEEPGRAM_API_KEY` is correct in `.env`
  2. Check Deepgram account balance and usage limits
  3. Ensure audio file format is supported (mp3, mp4, wav, m4a, flac, ogg)
  4. Check audio file size is under 500MB
  5. Review logs for specific error message

**Issue**: "Transcription timeout exceeded"
- **Solution**:
  1. Increase `TRANSCRIPTION_TIMEOUT_SECONDS` in `.env` (default: 300)
  2. Check audio file size - very large files may timeout
  3. Verify network connectivity to Deepgram API

#### Database Issues

**Issue**: "Database locked" or "OperationalError"
- **Solution**:
  1. Ensure only one instance of MeetHub is running
  2. Check database file permissions (`meethub.db`)
  3. Verify sufficient disk space
  4. Run `alembic upgrade head` to ensure schema is current
  5. For production with multiple workers, migrate to PostgreSQL

#### Google Drive Upload Errors

**Issue**: "Drive upload failed" or "Folder not found"
- **Solution**:
  1. Verify `DRIVE_ROOT_FOLDER_ID` is correct in `.env`
  2. Check `project_folders.json` has valid folder IDs
  3. Ensure service account has write access to Drive folders
  4. Verify OAuth scope `drive.file` is enabled
  5. Check Drive storage quota is not exceeded

#### Classification Issues

**Issue**: "All meetings go to GERAL folder" or "Classification not working"
- **Solution**:
  1. Check `classification_rules.json` exists and is valid JSON
  2. Verify rules are ordered correctly (first match wins)
  3. Test classification with: `python -m src.cli test-classification`
  4. Check meeting title and participant emails match rules
  5. Ensure default project is defined in rules

#### Processing Failures

**Issue**: "Processing job stuck in RUNNING state"
- **Solution**:
  1. Check logs for specific error: `docker-compose logs -f meethub`
  2. Verify all API credentials are correct
  3. Check network connectivity to Google and Deepgram APIs
  4. Restart the service: `docker-compose restart meethub`
  5. Failed jobs will auto-retry with exponential backoff

#### High API Costs

**Issue**: "Unexpected high costs from Deepgram"
- **Solution**:
  1. Monitor daily usage alerts in logs (>20 meetings/day warning)
  2. Check `estimated_cost_usd` in transcription logs
  3. Reduce polling frequency if needed: increase `POLL_INTERVAL_MINUTES`
  4. Review meeting classification rules - ensure meetings are properly filtered
  5. Consider implementing meeting duration limits

### Production Deployment Tips

1. **Environment Variables**: Never commit `.env` or `service-account.json` to git
2. **Database Backups**: Regularly backup `meethub.db` (or configure automated backups)
3. **Log Rotation**: Configure log rotation to prevent disk space issues
4. **Monitoring**: Set up alerts for failed jobs using log analysis tools
5. **Resource Limits**: Monitor CPU and memory usage, especially with concurrent processing
6. **API Rate Limits**: Be aware of Google API quotas and Deepgram usage limits
7. **Security**: Keep service account credentials secure and rotate regularly

### Debug Commands

```bash
# Test authentication
python -m src.cli test-auth

# Test classification rules
python -m src.cli test-classification

# Poll for recent meetings (manual test)
python -m src.cli poll-meetings --since-hours 24

# Process specific meeting
python -m src.cli process-meeting --meeting-id <meeting-id>

# Check database status
sqlite3 meethub.db "SELECT COUNT(*) FROM meetings;"
sqlite3 meethub.db "SELECT status, COUNT(*) FROM meetings GROUP BY status;"

# View error logs only
docker-compose logs meethub | grep -i error

# View specific meeting logs
docker-compose logs meethub | grep -i "meeting_id=abc123"
```

See [quickstart.md](specs/001-meeting-transcription-mvp/quickstart.md#troubleshooting) for detailed troubleshooting guide.

## Documentation

- [Feature Specification](specs/001-meeting-transcription-mvp/spec.md)
- [Implementation Plan](specs/001-meeting-transcription-mvp/plan.md)
- [Quickstart Guide](specs/001-meeting-transcription-mvp/quickstart.md)
- [Data Model](specs/001-meeting-transcription-mvp/data-model.md)
- [Task Breakdown](specs/001-meeting-transcription-mvp/tasks.md)

## License

MIT License - see LICENSE file for details

## Contributing

This project uses Speckit for specification-driven development. See [CLAUDE.md](CLAUDE.md) for development workflow.

## Support

- Issue Tracker: https://github.com/your-org/meethub/issues
- Documentation: See `specs/` directory
- Google Meet API: https://developers.google.com/meet/api
- Deepgram API: https://developers.deepgram.com/
