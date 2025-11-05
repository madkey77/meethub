# MeetHub Project Overview

This document provides a comprehensive overview of the MeetHub project, its architecture, and development conventions.

## Project Overview

MeetHub is a Python application that automates the transcription and organization of Google Meet recordings. It periodically polls for new meetings, downloads the recordings, transcribes them using Deepgram's AI, and uploads the formatted transcripts to Google Drive. Meetings are automatically classified into project folders based on configurable rules.

**Main Technologies:**

*   **Backend:** Python 3.11+
*   **Transcription:** Deepgram AI
*   **Cloud Services:** Google Meet API, Google Drive API
*   **Database:** SQLAlchemy with SQLite (default) or PostgreSQL
*   **Scheduling:** APScheduler
*   **Containerization:** Docker and Docker Compose

## Building and Running

### Prerequisites

*   Python 3.11+
*   Google Workspace account with Google Meet enabled
*   Google Cloud Platform account
*   Deepgram account
*   Docker and Docker Compose (recommended)

### Setup and Execution

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/your-org/meethub.git
    cd meethub
    ```

2.  **Install dependencies:**
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
    ```

3.  **Configure the environment:**
    *   Copy `.env.example` to `.env` and fill in the required API keys and folder IDs.
    *   Configure `project_folders.json` and `classification_rules.json`.

4.  **Initialize the database:**
    ```bash
    alembic upgrade head
    ```

5.  **Run the application:**
    *   **Development:**
        ```bash
        python -m src.main
        ```
    *   **Production (Docker):**
        ```bash
        docker-compose up -d
        ```

### Testing

*   **Run all tests:**
    ```bash
    pytest
    ```
*   **Run unit tests:**
    ```bash
    pytest tests/unit/
    ```
*   **Run integration tests:**
    ```bash
    pytest tests/integration/ --run-integration
    ```

## Development Conventions

*   **Code Style:** The project uses `black` for code formatting, `ruff` for linting, and `mypy` for type checking.
    *   **Format code:** `black src/ tests/`
    *   **Lint code:** `ruff check src/ tests/`
    *   **Type check:** `mypy src/`
*   **Branching:** (TODO: Add branching strategy if available)
*   **Commits:** (TODO: Add commit message conventions if available)
*   **Testing:** All new features and bug fixes should be accompanied by tests. The project has unit, integration, and end-to-end tests.
