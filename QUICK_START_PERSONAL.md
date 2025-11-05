# Quick Start - Personal Mode (Existing Installation)

Since you already have MeetHub on your hard drive, follow these steps:

## Prerequisites Check

You already have:
- ✅ Project cloned
- ✅ Python installed

## Step 1: Update Dependencies

```bash
# Navigate to project
cd /mnt/e/projetos/meethub/meethub

# Activate virtual environment (if you have one)
# If you don't have a venv yet, create one:
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install/update dependencies (includes new OAuth libraries)
pip install -r requirements.txt
```

## Step 2: Create Google Cloud Project

Follow **Step 2** in [PERSONAL_MODE_SETUP.md](PERSONAL_MODE_SETUP.md#step-2-create-google-cloud-project)

## Step 3: Enable Required APIs

Follow **Step 3** in [PERSONAL_MODE_SETUP.md](PERSONAL_MODE_SETUP.md#step-3-enable-required-apis)

Enable:
- Google Meet API
- Google Calendar API
- Google Drive API

## Step 4: Configure OAuth Consent Screen

Follow **Step 4** in [PERSONAL_MODE_SETUP.md](PERSONAL_MODE_SETUP.md#step-4-configure-oauth-consent-screen)

Add these scopes:
- `https://www.googleapis.com/auth/calendar.readonly`
- `https://www.googleapis.com/auth/meetings.space.readonly`
- `https://www.googleapis.com/auth/drive.file`

## Step 5: Create OAuth Client Credentials

Follow **Step 5** in [PERSONAL_MODE_SETUP.md](PERSONAL_MODE_SETUP.md#step-5-create-oauth-client-credentials)

Download as `credentials.json` in project root.

## Step 6: Configure Environment

```bash
cp .env.example .env
```

Edit `.env`:
```bash
# IMPORTANT: Set this to oauth!
GOOGLE_AUTH_MODE=oauth

# OAuth Credentials
GOOGLE_OAUTH_CREDENTIALS_PATH=./credentials.json
GOOGLE_OAUTH_TOKEN_PATH=./token.json

# Get these in next steps
DRIVE_ROOT_FOLDER_ID=your_root_folder_id_here
DEEPGRAM_API_KEY=your_deepgram_api_key_here

# These are fine as defaults
POLL_INTERVAL_MINUTES=15
TRANSCRIPTION_LANGUAGE=pt
LOG_FORMAT=console
```

## Step 7: Setup Google Drive Folders

Follow **Step 7** in [PERSONAL_MODE_SETUP.md](PERSONAL_MODE_SETUP.md#step-7-setup-google-drive-folders)

Create folders and update `project_folders.json`

## Step 8: Get Deepgram API Key

Follow **Step 8** in [PERSONAL_MODE_SETUP.md](PERSONAL_MODE_SETUP.md#step-8-get-deepgram-api-key)

## Step 9: Initialize Database

```bash
alembic upgrade head
```

## Step 10: First Authentication

```bash
# This will open your browser
LOG_FORMAT=console python -m src.cli test-auth
```

Sign in with YOUR Google account (your worker account).

## Step 11: Test

```bash
# Test config
python -m src.cli show-config

# Test classification
python -m src.cli test-classification

# List your recent meetings
python -m src.cli poll-meetings --since-hours 24
```

## Step 12: Run MeetHub

```bash
LOG_FORMAT=console python -m src.main
```

## Summary Checklist

- [ ] Updated dependencies (`pip install -r requirements.txt`)
- [ ] Created Google Cloud project
- [ ] Enabled 3 APIs (Meet, Calendar, Drive)
- [ ] Configured OAuth consent screen
- [ ] Downloaded `credentials.json`
- [ ] Created `.env` with `GOOGLE_AUTH_MODE=oauth`
- [ ] Created Google Drive folders
- [ ] Got Deepgram API key
- [ ] Ran `alembic upgrade head`
- [ ] Authenticated (`python -m src.cli test-auth`)
- [ ] Tested configuration
- [ ] Running MeetHub!

---

**Full details**: See [PERSONAL_MODE_SETUP.md](PERSONAL_MODE_SETUP.md)
