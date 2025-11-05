"""Google Drive API service for uploading transcripts and managing folders."""

from pathlib import Path
from typing import Any

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

from src.config import settings
from src.utils.exceptions import (
    AuthenticationError,
    GoogleDriveAPIError,
    NetworkError,
    QuotaExceededError,
    RateLimitError,
    TemporaryAPIError,
)
from src.utils.google_auth import get_google_credentials
from src.utils.logging import get_logger
from src.utils.retry import retry_with_backoff
from src.utils.validators import sanitize_filename

logger = get_logger(__name__)


class GoogleDriveService:
    """Service for interacting with Google Drive API."""

    def __init__(self) -> None:
        """Initialize Google Drive service with authentication."""
        self.credentials = get_google_credentials()
        self.service = None
        self._initialize_service()

    def _initialize_service(self) -> None:
        """Initialize Google Drive API service client.

        Raises:
            AuthenticationError: If service initialization fails
        """
        try:
            self.service = build("drive", "v3", credentials=self.credentials)
            logger.info("Google Drive API service initialized successfully")

        except Exception as e:
            raise AuthenticationError(
                f"Failed to initialize Google Drive API service: {e}",
                details={},
            ) from e

    @retry_with_backoff(
        retryable_exceptions=(NetworkError, TemporaryAPIError, RateLimitError)
    )
    def ensure_folder_exists(self, folder_name: str, parent_folder_id: str | None = None) -> str:
        """Ensure folder exists in Drive, create if not found.

        Args:
            folder_name: Folder name
            parent_folder_id: Parent folder ID (default: root folder from settings)

        Returns:
            Folder ID

        Raises:
            GoogleDriveAPIError: If folder creation fails
        """
        parent_id = parent_folder_id or settings.drive_root_folder_id

        try:
            # Search for existing folder
            query = f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder' and '{parent_id}' in parents and trashed=false"

            response = (
                self.service.files()
                .list(
                    q=query,
                    spaces="drive",
                    fields="files(id, name)",
                    pageSize=1,
                )
                .execute()
            )

            files = response.get("files", [])
            if files:
                folder_id = files[0]["id"]
                logger.info(
                    "Folder already exists",
                    folder_name=folder_name,
                    folder_id=folder_id,
                )
                return folder_id

            # Create folder if not found
            file_metadata = {
                "name": folder_name,
                "mimeType": "application/vnd.google-apps.folder",
                "parents": [parent_id],
            }

            folder = (
                self.service.files()
                .create(body=file_metadata, fields="id")
                .execute()
            )

            folder_id = folder["id"]
            logger.info(
                "Folder created",
                folder_name=folder_name,
                folder_id=folder_id,
                parent_id=parent_id,
            )
            return folder_id

        except HttpError as e:
            if e.resp.status == 429:
                raise RateLimitError(
                    "Google Drive API rate limit exceeded",
                    details={"status_code": 429},
                ) from e
            elif e.resp.status == 403 and "quotaExceeded" in str(e):
                raise QuotaExceededError(
                    "Google Drive storage quota exceeded",
                    details={"status_code": 403},
                ) from e
            elif e.resp.status >= 500:
                raise TemporaryAPIError(
                    f"Google Drive API temporary error: {e}",
                    details={"status_code": e.resp.status},
                ) from e
            else:
                raise GoogleDriveAPIError(
                    f"Google Drive API error: {e}",
                    details={"status_code": e.resp.status, "folder_name": folder_name},
                ) from e

        except Exception as e:
            raise GoogleDriveAPIError(
                f"Unexpected error ensuring folder exists: {e}",
                details={"folder_name": folder_name},
            ) from e

    @retry_with_backoff(
        retryable_exceptions=(NetworkError, TemporaryAPIError, RateLimitError)
    )
    def upload_transcript(
        self,
        file_path: Path | str,
        folder_id: str,
        meeting_id: str,
        meeting_title: str,
        meeting_date: str,
    ) -> str:
        """Upload transcript markdown file to Google Drive.

        Args:
            file_path: Path to markdown file
            folder_id: Target folder ID
            meeting_id: Meeting ID
            meeting_title: Meeting title
            meeting_date: Meeting date (YYYY-MM-DD)

        Returns:
            Uploaded file ID

        Raises:
            GoogleDriveAPIError: If upload fails
        """
        file_path = Path(file_path) if isinstance(file_path, str) else file_path

        try:
            # Generate filename: YYYY-MM-DD_sanitized-title_meeting-id.md
            sanitized_title = sanitize_filename(meeting_title, max_length=100)
            filename = f"{meeting_date}_{sanitized_title}_{meeting_id}.md"

            logger.info(
                "Uploading transcript to Drive",
                file_path=str(file_path),
                folder_id=folder_id,
                filename=filename,
            )

            # File metadata
            file_metadata = {
                "name": filename,
                "parents": [folder_id],
                "mimeType": "text/markdown",
                "description": f"Meeting transcript: {meeting_title} ({meeting_date})",
            }

            # Upload file
            media = MediaFileUpload(
                str(file_path),
                mimetype="text/markdown",
                resumable=True,
            )

            file = (
                self.service.files()
                .create(
                    body=file_metadata,
                    media_body=media,
                    fields="id, webViewLink",
                )
                .execute()
            )

            file_id = file["id"]
            web_link = file.get("webViewLink", "")

            logger.info(
                "Transcript uploaded successfully",
                file_id=file_id,
                folder_id=folder_id,
                filename=filename,
                web_link=web_link,
            )

            return file_id

        except HttpError as e:
            if e.resp.status == 429:
                raise RateLimitError(
                    "Google Drive API rate limit exceeded",
                    details={"status_code": 429},
                ) from e
            elif e.resp.status == 403 and "quotaExceeded" in str(e):
                raise QuotaExceededError(
                    "Google Drive storage quota exceeded",
                    details={"status_code": 403},
                ) from e
            elif e.resp.status >= 500:
                raise TemporaryAPIError(
                    f"Google Drive API temporary error: {e}",
                    details={"status_code": e.resp.status},
                ) from e
            else:
                raise GoogleDriveAPIError(
                    f"Google Drive API error during upload: {e}",
                    details={"status_code": e.resp.status, "filename": filename},
                ) from e

        except Exception as e:
            raise GoogleDriveAPIError(
                f"Unexpected error uploading transcript: {e}",
                details={"file_path": str(file_path)},
            ) from e

    @retry_with_backoff(
        retryable_exceptions=(NetworkError, TemporaryAPIError, RateLimitError)
    )
    def list_project_folders(self, parent_folder_id: str | None = None) -> list[dict[str, Any]]:
        """List all project folders in the root folder.

        Args:
            parent_folder_id: Parent folder ID (default: root folder from settings)

        Returns:
            List of folder metadata dictionaries

        Raises:
            GoogleDriveAPIError: If listing fails
        """
        parent_id = parent_folder_id or settings.drive_root_folder_id

        try:
            logger.info("Listing project folders", parent_folder_id=parent_id)

            # Query for folders
            query = f"mimeType='application/vnd.google-apps.folder' and '{parent_id}' in parents and trashed=false"

            response = (
                self.service.files()
                .list(
                    q=query,
                    spaces="drive",
                    fields="files(id, name, createdTime, modifiedTime)",
                    pageSize=100,
                )
                .execute()
            )

            folders = response.get("files", [])

            logger.info(
                "Project folders listed",
                parent_folder_id=parent_id,
                folder_count=len(folders),
            )

            return folders

        except HttpError as e:
            if e.resp.status == 429:
                raise RateLimitError(
                    "Google Drive API rate limit exceeded",
                    details={"status_code": 429},
                ) from e
            elif e.resp.status >= 500:
                raise TemporaryAPIError(
                    f"Google Drive API temporary error: {e}",
                    details={"status_code": e.resp.status},
                ) from e
            else:
                raise GoogleDriveAPIError(
                    f"Google Drive API error: {e}",
                    details={"status_code": e.resp.status},
                ) from e

        except Exception as e:
            raise GoogleDriveAPIError(
                f"Unexpected error listing folders: {e}",
                details={},
            ) from e
