"""Google Meet API service for polling ended meetings and downloading recordings."""

import io
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseDownload

from src.config import settings
from src.utils.exceptions import (
    AuthenticationError,
    GoogleMeetAPIError,
    NetworkError,
    RateLimitError,
    TemporaryAPIError,
)
from src.utils.google_auth import get_google_credentials
from src.utils.logging import get_logger
from src.utils.retry import retry_with_backoff

logger = get_logger(__name__)


class GoogleMeetService:
    """Service for interacting with Google Meet API."""

    def __init__(self) -> None:
        """Initialize Google Meet service with authentication."""
        self.credentials = get_google_credentials()
        self.meet_service = None
        self.drive_service = None
        self._initialize_services()

    def _initialize_services(self) -> None:
        """Initialize Google API service clients.

        Raises:
            AuthenticationError: If service initialization fails
        """
        try:
            self.meet_service = build("meet", "v2", credentials=self.credentials)
            self.drive_service = build("drive", "v3", credentials=self.credentials)
            logger.info("Google API services initialized successfully")

        except Exception as e:
            raise AuthenticationError(
                f"Failed to initialize Google API services: {e}",
                details={},
            ) from e

    @retry_with_backoff(
        retryable_exceptions=(NetworkError, TemporaryAPIError, RateLimitError)
    )
    def poll_ended_meetings(
        self, since: datetime | None = None, limit: int = 100
    ) -> list[dict[str, Any]]:
        """Poll for ended meetings since a given timestamp.

        Args:
            since: Start timestamp (default: 1 hour ago)
            limit: Maximum number of meetings to retrieve (default: 100)

        Returns:
            List of meeting dictionaries with metadata

        Raises:
            GoogleMeetAPIError: If API call fails
            RateLimitError: If rate limit is exceeded
        """
        if since is None:
            since = datetime.utcnow() - timedelta(hours=1)

        try:
            # Format datetime properly for Google Meet API (RFC 3339 without microseconds)
            since_str = since.strftime('%Y-%m-%dT%H:%M:%SZ')

            logger.info(
                "Polling for ended meetings",
                since=since_str,
                limit=limit,
            )

            # Query for conference records (ended meetings)
            # Note: Google Meet API v2 uses conferenceRecords resource
            request = self.meet_service.conferenceRecords().list(
                filter=f'end_time >= "{since_str}"',
                pageSize=min(limit, 100),
            )

            meetings = []
            page_token = None

            while True:
                if page_token:
                    request = self.meet_service.conferenceRecords().list(
                        filter=f'end_time >= "{since_str}"',
                        pageSize=min(limit, 100),
                        pageToken=page_token,
                    )

                response = request.execute()
                conference_records = response.get("conferenceRecords", [])

                for record in conference_records:
                    meeting_data = self._parse_conference_record(record)
                    if meeting_data:
                        meetings.append(meeting_data)

                # Check if there are more pages
                page_token = response.get("nextPageToken")
                if not page_token or len(meetings) >= limit:
                    break

            logger.info(
                "Polling completed",
                meetings_found=len(meetings),
                since=since.isoformat(),
            )
            return meetings[:limit]

        except HttpError as e:
            if e.resp.status == 429:
                raise RateLimitError(
                    "Google Meet API rate limit exceeded",
                    details={"status_code": 429},
                ) from e
            elif e.resp.status >= 500:
                raise TemporaryAPIError(
                    f"Google Meet API temporary error: {e}",
                    details={"status_code": e.resp.status},
                ) from e
            else:
                raise GoogleMeetAPIError(
                    f"Google Meet API error: {e}",
                    details={"status_code": e.resp.status},
                ) from e

        except Exception as e:
            raise GoogleMeetAPIError(
                f"Unexpected error polling meetings: {e}",
                details={},
            ) from e

    def _parse_conference_record(self, record: dict[str, Any]) -> dict[str, Any] | None:
        """Parse conference record into meeting data.

        Args:
            record: Conference record from API

        Returns:
            Parsed meeting data or None if invalid
        """
        try:
            # Extract meeting ID from resource name (e.g., "conferenceRecords/abc-def-ghi")
            meeting_id = record.get("name", "").split("/")[-1]

            # Parse timestamps
            start_time_str = record.get("startTime")
            end_time_str = record.get("endTime")

            if not start_time_str or not end_time_str:
                logger.warning(
                    "Conference record missing timestamps, skipping",
                    record_name=record.get("name"),
                )
                return None

            start_time = datetime.fromisoformat(start_time_str.replace("Z", "+00:00"))
            end_time = datetime.fromisoformat(end_time_str.replace("Z", "+00:00"))
            duration_minutes = int((end_time - start_time).total_seconds() / 60)

            # Get space details for title
            # Note: In the API response, 'space' is just a string ID like 'spaces/xxx'
            # We'll use the meeting ID as title for now, or you can fetch space details separately
            space = record.get("space", "")
            if isinstance(space, dict):
                title = space.get("title", f"Meeting {meeting_id[:8]}")
            else:
                # Space is just an ID string, use a generated title
                title = f"Meeting {meeting_id[:8]}"

            # Get organizer if available
            organizer_email = None
            if "organizer" in record:
                organizer = record.get("organizer", {})
                if isinstance(organizer, dict):
                    organizer_email = organizer.get("email")

            return {
                "meeting_id": meeting_id,
                "title": title,
                "start_time": start_time,
                "end_time": end_time,
                "duration_minutes": duration_minutes,
                "organizer_email": organizer_email,
                "recording_url": None,  # Will be populated by check_recording_exists
                "recording_drive_id": None,
            }

        except Exception as e:
            logger.error(
                "Failed to parse conference record",
                error=str(e),
                record=record,
            )
            return None

    @retry_with_backoff(
        retryable_exceptions=(NetworkError, TemporaryAPIError, RateLimitError)
    )
    def check_recording_exists(self, meeting_id: str) -> dict[str, Any] | None:
        """Check if recording exists for a meeting and get file details.

        Args:
            meeting_id: Meeting ID (conference record ID)

        Returns:
            Recording metadata (drive_id, url) or None if not found

        Raises:
            GoogleMeetAPIError: If API call fails
        """
        try:
            logger.info("Checking for recording", meeting_id=meeting_id)

            # Use Google Meet API to list recordings for this conference record
            # Format: conferenceRecords/{meeting_id}/recordings
            parent = f"conferenceRecords/{meeting_id}"

            try:
                response = (
                    self.meet_service.conferenceRecords()
                    .recordings()
                    .list(parent=parent)
                    .execute()
                )
            except HttpError as e:
                if e.resp.status == 404:
                    logger.info("No recordings found for meeting", meeting_id=meeting_id)
                    return None
                raise

            recordings = response.get("recordings", [])
            if not recordings:
                logger.info("No recording found", meeting_id=meeting_id)
                return None

            # Take the first recording
            recording = recordings[0]

            # Log the full recording response for debugging
            logger.info("Recording response from Meet API", recording=recording)

            drive_destination = recording.get("driveDestination", {})
            drive_file_id = drive_destination.get("file")

            if not drive_file_id:
                logger.warning(
                    "Recording exists but has no Drive file ID",
                    meeting_id=meeting_id,
                    recording=recording,
                )
                return None

            # Extract file ID from the resource name (format: "files/{fileId}")
            original_file_id = drive_file_id
            if "/" in drive_file_id:
                drive_file_id = drive_file_id.split("/")[-1]

            logger.info(
                "Extracted Drive file ID",
                original=original_file_id,
                extracted=drive_file_id,
            )

            # Try to get file metadata from Drive API
            # Note: This may fail if permissions haven't propagated yet
            try:
                file_metadata = (
                    self.drive_service.files()
                    .get(fileId=drive_file_id, fields="id,name,webViewLink,size,createdTime")
                    .execute()
                )

                logger.info(
                    "Recording found with Drive metadata",
                    meeting_id=meeting_id,
                    drive_id=drive_file_id,
                    size_mb=round(int(file_metadata.get("size", 0)) / (1024 * 1024), 2),
                )

                return {
                    "drive_id": drive_file_id,
                    "url": file_metadata.get("webViewLink"),
                    "size_bytes": int(file_metadata.get("size", 0)),
                    "created_time": file_metadata.get("createdTime"),
                }
            except HttpError as e:
                if e.resp.status == 404:
                    # File exists in Meet API but not accessible via Drive API yet
                    # Use the exportUri from the recording instead
                    export_uri = drive_destination.get("exportUri")

                    logger.warning(
                        "Recording file not accessible via Drive API yet, using exportUri",
                        meeting_id=meeting_id,
                        drive_id=drive_file_id,
                        export_uri=export_uri,
                    )

                    return {
                        "drive_id": drive_file_id,
                        "url": export_uri,
                        "size_bytes": 0,  # Unknown, will get it during download
                        "created_time": recording.get("startTime"),
                    }
                else:
                    raise

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
                raise GoogleMeetAPIError(
                    f"Google Drive API error: {e}",
                    details={"status_code": e.resp.status},
                ) from e

        except Exception as e:
            raise GoogleMeetAPIError(
                f"Unexpected error checking recording: {e}",
                details={"meeting_id": meeting_id},
            ) from e

    @retry_with_backoff(
        retryable_exceptions=(NetworkError, TemporaryAPIError, RateLimitError)
    )
    def download_recording(
        self, drive_file_id: str, output_path: Path | str
    ) -> Path:
        """Download recording from Google Drive.

        Args:
            drive_file_id: Google Drive file ID
            output_path: Local path to save the recording

        Returns:
            Path to downloaded file

        Raises:
            GoogleMeetAPIError: If download fails
        """
        output_path = Path(output_path) if isinstance(output_path, str) else output_path

        try:
            logger.info(
                "Starting recording download",
                drive_file_id=drive_file_id,
                output_path=str(output_path),
            )

            # Get file metadata
            file_metadata = (
                self.drive_service.files()
                .get(fileId=drive_file_id, fields="name,size")
                .execute()
            )
            file_size = int(file_metadata.get("size", 0))

            # Download file
            request = self.drive_service.files().get_media(fileId=drive_file_id)

            # Create parent directory if needed
            output_path.parent.mkdir(parents=True, exist_ok=True)

            # Download with progress tracking
            with open(output_path, "wb") as fh:
                downloader = MediaIoBaseDownload(fh, request)
                done = False
                while not done:
                    status, done = downloader.next_chunk()
                    if status:
                        progress_pct = int(status.progress() * 100)
                        logger.debug(
                            "Download progress",
                            drive_file_id=drive_file_id,
                            progress_percent=progress_pct,
                        )

            logger.info(
                "Recording downloaded successfully",
                drive_file_id=drive_file_id,
                output_path=str(output_path),
                size_mb=round(file_size / (1024 * 1024), 2),
            )
            return output_path

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
                raise GoogleMeetAPIError(
                    f"Google Drive API error during download: {e}",
                    details={"status_code": e.resp.status, "drive_file_id": drive_file_id},
                ) from e

        except Exception as e:
            # Clean up partial download
            if output_path.exists():
                output_path.unlink()

            raise GoogleMeetAPIError(
                f"Unexpected error downloading recording: {e}",
                details={"drive_file_id": drive_file_id},
            ) from e
