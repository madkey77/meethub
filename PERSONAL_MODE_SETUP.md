# Personal Mode Setup Guide

This guide explains how to set up MeetHub in **Personal Mode** to transcribe YOUR OWN Google Meet recordings without requiring admin access to a Google Workspace organization.

## What is Personal Mode?

**Personal Mode** uses **OAuth 2.0** authentication instead of service account domain-wide delegation. This means:

✅ **No admin access required**
✅ **Works with personal Google accounts**
✅ **Works with regular Workspace user accounts**
✅ **Only accesses YOUR meetings**
❌ Cannot access other users' meetings
❌ Requires manual authentication (browser popup) on first run

## When to Use Personal Mode

Choose Personal Mode if:
- You want to test MeetHub with your own account
- You don't have Google Workspace admin access
- You only need to transcribe YOUR OWN meetings
- You're using a personal Gmail account

Choose Service Account Mode (organization-wide) if:
- You have Google Workspace admin access
- You need to transcribe meetings for your entire organization
- You want fully automated, hands-off operation

## Setup Instructions

### Step 1: Install MeetHub

```bash
git clone https://github.com/your-org/meethub.git
cd meethub
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### Step 2: Create Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Click **Select a project** → **New Project**
3. Project name: `MeetHub Personal`
4. Click **Create**
5. Wait for project to be created

### Step 3: Enable Required APIs

1. Make sure your new project is selected
2. Go to [API Library](https://console.cloud.google.com/apis/library)
3. Search for and enable each API:
   - **Google Meet API**
   - **Google Calendar API**
   - **Google Drive API**

Click **Enable** for each one.

### Step 4: Configure OAuth Consent Screen

1. Go to [OAuth consent screen](https://console.cloud.google.com/apis/credentials/consent)
2. Choose **External** (unless you have Workspace and want Internal)
3. Click **Create**

**Fill in required fields:**
- App name: `MeetHub Personal`
- User support email: your-email@gmail.com
- Developer contact: your-email@gmail.com

**Scopes:** (Click "Add or Remove Scopes")
- `https://www.googleapis.com/auth/calendar.readonly`
- `https://www.googleapis.com/auth/meetings.space.readonly`
- `https://www.googleapis.com/auth/drive.file`

Click **Save and Continue** through all steps.

### Step 5: Create OAuth Client Credentials

1. Go to [Credentials](https://console.cloud.google.com/apis/credentials)
2. Click **Create Credentials** → **OAuth client ID**
3. Application type: **Desktop app**
4. Name: `MeetHub Desktop Client`
5. Click **Create**

**Download credentials:**
1. Click the download icon (⬇️) next to your newly created OAuth client
2. Save the file as `credentials.json` in the MeetHub project root

⚠️ **IMPORTANT**: Never commit this file to git! It's already in `.gitignore`.

### Step 6: Configure Environment for Personal Mode

```bash
# Copy example environment file
cp .env.example .env
```

Edit `.env` file:

```bash
# IMPORTANT: Set auth mode to 'oauth' for personal mode
GOOGLE_AUTH_MODE=oauth

# OAuth Credentials (Personal Mode)
GOOGLE_OAUTH_CREDENTIALS_PATH=./credentials.json
GOOGLE_OAUTH_TOKEN_PATH=./token.json

# Google Drive Folder IDs
DRIVE_ROOT_FOLDER_ID=your_root_folder_id_here

# Deepgram API
DEEPGRAM_API_KEY=your_deepgram_api_key_here

# Polling Configuration
POLL_INTERVAL_MINUTES=15
MAX_CONCURRENT_JOBS=3
MAX_RETRIES=3

# Transcription Configuration
TRANSCRIPTION_LANGUAGE=pt
DEEPGRAM_MODEL=nova-2

# Database
DATABASE_URL=sqlite:///./meethub.db

# Logging
LOG_LEVEL=INFO
LOG_FORMAT=console  # Use console for easier debugging
```

**Key difference**: Set `GOOGLE_AUTH_MODE=oauth` instead of `service_account`!

### Step 7: Setup Google Drive Folders

1. Go to [Google Drive](https://drive.google.com/)
2. Create folder structure:
   ```
   MeetHub Transcripts/
   ├── VNO/
   ├── CLIENTE_X/
   ├── NOVOS_CLIENTES/
   └── GERAL/
   ```

3. Get folder IDs:
   - Open each folder
   - Copy ID from URL: `https://drive.google.com/drive/folders/FOLDER_ID_HERE`

4. Update `DRIVE_ROOT_FOLDER_ID` in `.env`

5. Update `project_folders.json`:
```json
{
  "VNO": "your_vno_folder_id",
  "CLIENTE_X": "your_cliente_x_folder_id",
  "NOVOS_CLIENTES": "your_novos_clientes_folder_id",
  "GERAL": "your_geral_folder_id"
}
```

### Step 8: Get Deepgram API Key

1. Sign up at [Deepgram](https://console.deepgram.com/signup)
2. Go to [API Keys](https://console.deepgram.com/project/default/settings/api-keys)
3. Create new API key
4. Copy and paste into `.env` as `DEEPGRAM_API_KEY`

### Step 9: Initialize Database

```bash
alembic upgrade head
```

### Step 10: First Authentication

On first run, you'll need to authenticate:

```bash
# Test authentication (this will open browser)
LOG_FORMAT=console python -m src.cli test-auth
```

**What happens:**
1. A browser window will open automatically
2. Sign in with YOUR Google account (the one you want to use)
3. Review permissions requested:
   - Read calendar events
   - Read Google Meet recordings
   - Create/modify files in Drive
4. Click **Allow**
5. You'll see "The authentication flow has completed"
6. Close the browser tab

A `token.json` file will be created automatically - this stores your authentication.

⚠️ **IMPORTANT**: Never commit `token.json` to git! It's already in `.gitignore`.

### Step 11: Test Configuration

```bash
# Test classification rules
python -m src.cli test-classification

# Show configuration
python -m src.cli show-config

# Test polling (will list your recent meetings)
python -m src.cli poll-meetings --since-hours 36
```

### Step 12: Run MeetHub

#### Development Mode (Recommended for Testing)

```bash
LOG_FORMAT=console python -m src.main
```

You'll see:
```
MeetHub starting...
Starting meeting polling job...
```

Press `Ctrl+C` to stop.

#### Background Mode

```bash
nohup python -m src.main > meethub.log 2>&1 &
tail -f meethub.log
```

### Step 13: Test with Real Meeting

1. **Start a Google Meet**
   - Use the account you authenticated with
   - **Enable recording** (required!)

2. **End the meeting**

3. **Wait 2-5 minutes** for recording to process

4. **Wait for next poll** (up to 15 minutes, or check logs)

5. **Check Google Drive** for transcript in appropriate folder

## Important Notes for Personal Mode

### Limitations

1. **Only YOUR meetings** are processed
   - Meetings you created
   - Meetings you attended and recorded

2. **Manual authentication** required
   - First time setup requires browser
   - Token expires after ~7 days (will auto-refresh)
   - If token expires completely, re-authentication needed

3. **No organization-wide access**
   - Can't see other users' meetings
   - Can't access organization calendars

### Token Management

**Token expires?** Just run any command and it will auto-refresh:
```bash
python -m src.cli test-auth
```

**Need to log out?** Delete the token:
```bash
rm token.json
```

Next run will prompt for re-authentication.

**Switch accounts?** Delete token and re-run:
```bash
rm token.json
python -m src.cli test-auth
```

### Troubleshooting Personal Mode

**"OAuth credentials not found"**
- Make sure `credentials.json` exists in project root
- Verify `GOOGLE_AUTH_MODE=oauth` in `.env`
- Check `GOOGLE_OAUTH_CREDENTIALS_PATH=./credentials.json` in `.env`

**Browser doesn't open during authentication**
- Check firewall settings
- Try manually opening the URL shown in console
- Make sure you have a default browser set

**"Access blocked: This app's request is invalid"**
- Make sure you enabled all 3 required APIs
- Verify OAuth consent screen is configured
- Check that scopes are added to consent screen

**"No meetings found"**
- Ensure recordings were enabled for your meetings
- You must be the meeting creator or host
- Wait 2-5 minutes after meeting ends
- Check with: `python -m src.cli poll-meetings --since-hours 24`

**Token expired errors**
- Run: `rm token.json && python -m src.cli test-auth`
- Re-authenticate in browser

## Switching Between Modes

You can switch between Personal and Service Account modes by changing `.env`:

**Personal Mode:**
```bash
GOOGLE_AUTH_MODE=oauth
```

**Service Account Mode (Admin):**
```bash
GOOGLE_AUTH_MODE=service_account
```

Just restart MeetHub after changing the mode.

## Comparison: Personal vs Service Account Mode

| Feature | Personal Mode (OAuth) | Service Account Mode |
|---------|----------------------|---------------------|
| **Admin access required** | ❌ No | ✅ Yes |
| **Setup complexity** | ⭐⭐ Easy | ⭐⭐⭐⭐ Complex |
| **Works with** | Personal accounts | Workspace organizations |
| **Access scope** | Your meetings only | All org meetings |
| **Authentication** | Browser (once) | Automatic |
| **Token expires** | ~7 days (auto-refresh) | Never |
| **Best for** | Testing, personal use | Production, organizations |

## Next Steps

Once Personal Mode is working:

1. **Test thoroughly** with your own meetings
2. **Verify transcription quality**
3. **Check classification rules**
4. **Monitor Deepgram costs**

When ready for organization-wide deployment:
1. Request admin access from your IT team
2. Follow [GETTING_STARTED.md](GETTING_STARTED.md) for Service Account setup
3. Switch `GOOGLE_AUTH_MODE=service_account` in `.env`

---

**Questions?** See [README.md#troubleshooting](README.md#troubleshooting) or [GETTING_STARTED.md](GETTING_STARTED.md).
