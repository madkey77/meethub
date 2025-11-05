# Getting Started with MeetHub

This is a quick-start checklist to get MeetHub up and running. For detailed instructions, see [README.md](README.md).

## Prerequisites Checklist

Before you begin, make sure you have:

- [ ] Python 3.11+ installed
- [ ] Docker and Docker Compose installed (recommended)
- [ ] Google Workspace account with admin access
- [ ] Google Cloud Platform account
- [ ] Deepgram account (sign up at https://console.deepgram.com/signup)

## Setup Checklist

### 1. Clone and Install

```bash
git clone https://github.com/your-org/meethub.git
cd meethub
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

- [ ] Repository cloned
- [ ] Virtual environment created
- [ ] Dependencies installed

### 2. Google Cloud Platform Setup

#### Enable APIs
- [ ] Created Google Cloud project
- [ ] Enabled Google Meet API
- [ ] Enabled Google Calendar API
- [ ] Enabled Google Drive API

#### Service Account
- [ ] Created service account: `meethub-service-account`
- [ ] Downloaded JSON key as `service-account.json`
- [ ] Placed in project root (DO NOT commit to git)
- [ ] Enabled domain-wide delegation
- [ ] Noted Client ID: `___________________________`

#### OAuth Scopes (Google Workspace Admin)
- [ ] Went to admin.google.com → Security → API Controls
- [ ] Added Client ID to domain-wide delegation
- [ ] Added scopes:
  - `https://www.googleapis.com/auth/calendar.readonly`
  - `https://www.googleapis.com/auth/meetings.space.readonly`
  - `https://www.googleapis.com/auth/drive.file`

### 3. Google Drive Setup

- [ ] Created root folder: "MeetHub Transcripts"
- [ ] Created subfolders: VNO, CLIENTE_X, NOVOS_CLIENTES, GERAL
- [ ] Shared all folders with service account email (Editor permission)
- [ ] Copied folder IDs:
  - Root: `___________________________`
  - VNO: `___________________________`
  - CLIENTE_X: `___________________________`
  - NOVOS_CLIENTES: `___________________________`
  - GERAL: `___________________________`

### 4. Deepgram Setup

- [ ] Created Deepgram account
- [ ] Created API key
- [ ] Copied API key: `___________________________`

### 5. Configuration

```bash
cp .env.example .env
# Edit .env with your values
```

- [ ] Copied `.env.example` to `.env`
- [ ] Set `GOOGLE_SERVICE_ACCOUNT_PATH=./service-account.json`
- [ ] Set `GOOGLE_WORKSPACE_ADMIN_EMAIL=your-admin@domain.com`
- [ ] Set `DRIVE_ROOT_FOLDER_ID=<root-folder-id>`
- [ ] Set `DEEPGRAM_API_KEY=<your-api-key>`

Edit `project_folders.json`:
- [ ] Updated VNO folder ID
- [ ] Updated CLIENTE_X folder ID
- [ ] Updated NOVOS_CLIENTES folder ID
- [ ] Updated GERAL folder ID

Edit `classification_rules.json` (optional):
- [ ] Customized rules for your projects

### 6. Database Setup

```bash
alembic upgrade head
```

- [ ] Database migrations completed successfully

### 7. Test Configuration

```bash
python -m src.cli test-auth
python -m src.cli test-classification
python -m src.cli show-config
```

- [ ] Authentication test passed
- [ ] Classification test passed
- [ ] Configuration looks correct

### 8. Deploy

Choose one option:

**Option A: Docker (Recommended)**
```bash
docker-compose up -d
docker-compose logs -f meethub
```
- [ ] Docker containers started
- [ ] Logs show "MeetHub starting"

**Option B: Development Mode**
```bash
LOG_FORMAT=console python -m src.main
```
- [ ] Service running in foreground
- [ ] Logs show "MeetHub starting"

**Option C: Background Process**
```bash
nohup python -m src.main > meethub.log 2>&1 &
tail -f meethub.log
```
- [ ] Service running in background
- [ ] Logs show "MeetHub starting"

### 9. Verify It's Working

- [ ] Logs show first polling job started
- [ ] Held test meeting with recording enabled
- [ ] Meeting ended and waited 2-5 minutes
- [ ] Waited for polling interval (up to 15 minutes)
- [ ] Transcript appeared in Google Drive
- [ ] Database shows meeting as completed

## Quick Commands Reference

```bash
# Test and debug
python -m src.cli test-auth
python -m src.cli test-classification
python -m src.cli poll-meetings --since-hours 24
python -m src.cli process-meeting --meeting-id <id>

# Docker
docker-compose up -d          # Start
docker-compose logs -f        # View logs
docker-compose restart        # Restart
docker-compose down           # Stop

# Database
sqlite3 meethub.db "SELECT meeting_id, title, status FROM meetings;"
sqlite3 meethub.db "SELECT status, COUNT(*) FROM meetings GROUP BY status;"
```

## Common Issues

**"Authentication failed"**
- Check service-account.json exists
- Verify domain-wide delegation is enabled
- Confirm OAuth scopes are configured in Workspace Admin

**"No meetings found"**
- Ensure recordings are enabled for meetings
- Wait 2-5 minutes after meeting ends
- Verify admin email has access to Meet data

**"Deepgram API error"**
- Check API key is correct
- Verify Deepgram account has credits
- Ensure audio format is supported

**"Drive upload failed"**
- Verify folder IDs are correct
- Check service account has Editor permission on folders
- Ensure OAuth scope `drive.file` is enabled

## Need Help?

- **Full Documentation**: See [README.md](README.md)
- **Troubleshooting**: See [README.md#troubleshooting](README.md#troubleshooting)
- **Feature Spec**: See [specs/001-meeting-transcription-mvp/spec.md](specs/001-meeting-transcription-mvp/spec.md)
- **Quickstart Guide**: See [specs/001-meeting-transcription-mvp/quickstart.md](specs/001-meeting-transcription-mvp/quickstart.md)

## What Happens After Setup?

MeetHub will automatically:
1. Poll Google Meet every 15 minutes
2. Download recordings from ended meetings
3. Transcribe audio with Deepgram AI
4. Classify meetings into project folders
5. Upload formatted transcripts to Google Drive
6. Retry failed operations automatically
7. Log all activity for monitoring

**You don't need to do anything else!** Just hold your meetings with recording enabled, and transcripts will appear in Google Drive automatically.

## Next Steps

- [ ] Customize classification rules for your organization
- [ ] Set up log monitoring alerts
- [ ] Configure backup strategy for database
- [ ] Review Deepgram costs after first week
- [ ] Adjust polling interval if needed

---

**Congratulations!** MeetHub is now running and will automatically transcribe your Google Meet recordings. 🎉
