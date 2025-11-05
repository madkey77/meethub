"""Meeting processing orchestrator for end-to-end transcription workflow."""

import asyncio
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from src.models import Meeting, MeetingStatus, Participant, Transcript, get_db
from src.services.classification import ClassificationService
from src.services.google_drive import GoogleDriveService
from src.services.google_meet import GoogleMeetService
from src.services.transcription import TranscriptionService
from src.utils.exceptions import MeetHubError, ProcessingError
from src.utils.logging import bind_context, clear_context, get_logger
from src.utils.validators import validate_meeting_title

logger = get_logger(__name__)


class MeetingProcessor:
    """Orchestrator for processing meetings from detection to transcript upload."""

    def __init__(self) -> None:
        """Initialize meeting processor with required services."""
        self.google_meet_service = GoogleMeetService()
        self.transcription_service = TranscriptionService()
        self.google_drive_service = GoogleDriveService()
        self.classification_service = ClassificationService()
        logger.info("Meeting processor initialized")

    async def process_meeting(
        self,
        meeting_id: str,
        db: Session | None = None,
    ) -> dict[str, Any]:
        """Process a single meeting from start to finish.

        Workflow:
        1. Detect/load meeting metadata
        2. Download recording from Drive
        3. Transcribe audio with Deepgram
        4. Format transcript as markdown
        5. Upload transcript to Drive
        6. Update database with results

        Args:
            meeting_id: Meeting ID to process
            db: Database session (optional, will create if not provided)

        Returns:
            Processing result dictionary

        Raises:
            ProcessingError: If processing fails at any stage
        """
        # Bind meeting_id to all logs in this context
        bind_context(meeting_id=meeting_id)

        should_close_db = False
        if db is None:
            db = next(get_db())
            should_close_db = True

        temp_audio_path: Path | None = None
        temp_transcript_path: Path | None = None

        try:
            start_time = datetime.utcnow()
            logger.info("Starting meeting processing", meeting_id=meeting_id)

            # Get or create meeting record
            meeting = self._get_or_create_meeting(db, meeting_id)

            # State: DETECTED -> DOWNLOADING
            self._update_meeting_status(db, meeting, MeetingStatus.DOWNLOADING)

            # Step 1: Check if recording exists
            recording_info = self.google_meet_service.check_recording_exists(meeting_id)
            if not recording_info:
                logger.warning("No recording found for meeting", meeting_id=meeting_id)
                self._update_meeting_status(db, meeting, MeetingStatus.SKIPPED)
                return {
                    "success": False,
                    "meeting_id": meeting_id,
                    "status": "skipped",
                    "reason": "no_recording",
                }

            # Step 2: Download recording
            temp_audio_path = Path(tempfile.mktemp(suffix=".mp4", prefix=f"meeting_{meeting_id}_"))
            self.google_meet_service.download_recording(
                recording_info["drive_id"],
                temp_audio_path,
            )

            # State: DOWNLOADING -> TRANSCRIBING
            self._update_meeting_status(db, meeting, MeetingStatus.TRANSCRIBING)

            # Step 3: Transcribe audio
            transcription_data = await self.transcription_service.transcribe(temp_audio_path)

            # Step 3.5: Classify meeting into project
            participant_emails = [p.email for p in meeting.participants if p.email]
            classified_project = self.classification_service.classify_meeting(
                meeting_title=meeting.title,
                participant_emails=participant_emails,
            )
            meeting.project_name = classified_project
            db.commit()

            logger.info(
                "Meeting classified",
                meeting_id=meeting_id,
                project=classified_project,
            )

            # Step 4: Format as markdown
            meeting_date = meeting.start_time.strftime("%Y-%m-%d")
            participant_names = [p.name for p in meeting.participants] if meeting.participants else None

            markdown_text = self.transcription_service.format_as_markdown(
                transcription_data=transcription_data,
                meeting_title=meeting.title,
                meeting_date=meeting_date,
                duration_minutes=meeting.duration_minutes,
                project_name=meeting.project_name,
                participants=participant_names,
            )

            # Save markdown to temp file
            temp_transcript_path = Path(
                tempfile.mktemp(suffix=".md", prefix=f"transcript_{meeting_id}_")
            )
            temp_transcript_path.write_text(markdown_text, encoding="utf-8")

            # State: TRANSCRIBING -> UPLOADING
            self._update_meeting_status(db, meeting, MeetingStatus.UPLOADING)

            # Step 5: Upload to Drive
            # TODO: For now, upload to root folder. Will add classification in User Story 2
            drive_file_id = self.google_drive_service.upload_transcript(
                file_path=temp_transcript_path,
                folder_id=self._get_folder_for_project(meeting.project_name),
                meeting_id=meeting_id,
                meeting_title=meeting.title,
                meeting_date=meeting_date,
            )

            # Step 6: Save transcript to database
            transcript = Transcript(
                meeting_id=meeting_id,
                full_text=transcription_data["full_text"],
                markdown_text=markdown_text,
                word_count=transcription_data["word_count"],
                speaker_count=transcription_data["speaker_count"],
                drive_file_id=drive_file_id,
                drive_folder_id=self._get_folder_for_project(meeting.project_name),
            )
            db.add(transcript)

            # Step 7: Update meeting to completed
            self._update_meeting_status(db, meeting, MeetingStatus.COMPLETED)
            db.commit()

            # Calculate processing metrics
            end_time = datetime.utcnow()
            processing_time_seconds = (end_time - start_time).total_seconds()

            logger.info(
                "Meeting processing completed successfully",
                meeting_id=meeting_id,
                word_count=transcription_data["word_count"],
                speaker_count=transcription_data["speaker_count"],
                drive_file_id=drive_file_id,
                processing_time_seconds=round(processing_time_seconds, 2),
                processing_time_minutes=round(processing_time_seconds / 60, 2),
            )

            return {
                "success": True,
                "meeting_id": meeting_id,
                "status": "completed",
                "transcript_id": transcript.transcript_id,
                "drive_file_id": drive_file_id,
                "word_count": transcription_data["word_count"],
                "speaker_count": transcription_data["speaker_count"],
            }

        except Exception as e:
            logger.error(
                "Meeting processing failed",
                meeting_id=meeting_id,
                error=str(e),
                error_type=type(e).__name__,
            )

            # Update meeting status to failed
            if db and meeting:
                try:
                    self._update_meeting_status(db, meeting, MeetingStatus.FAILED)
                    db.commit()
                except Exception as db_error:
                    logger.error(
                        "Failed to update meeting status to failed",
                        meeting_id=meeting_id,
                        error=str(db_error),
                    )

            raise ProcessingError(
                f"Meeting processing failed: {e}",
                details={"meeting_id": meeting_id, "error_type": type(e).__name__},
            ) from e

        finally:
            # Cleanup temporary files
            if temp_audio_path and temp_audio_path.exists():
                try:
                    self.transcription_service.cleanup_audio_file(temp_audio_path)
                except Exception as e:
                    logger.warning(
                        "Failed to cleanup audio file",
                        audio_path=str(temp_audio_path),
                        error=str(e),
                    )

            if temp_transcript_path and temp_transcript_path.exists():
                try:
                    temp_transcript_path.unlink()
                    logger.debug("Temp transcript file deleted", path=str(temp_transcript_path))
                except Exception as e:
                    logger.warning(
                        "Failed to cleanup transcript file",
                        transcript_path=str(temp_transcript_path),
                        error=str(e),
                    )

            # Close database session if we created it
            if should_close_db and db:
                db.close()

            # Clear logging context
            clear_context()

    def _get_or_create_meeting(self, db: Session, meeting_id: str) -> Meeting:
        """Get existing meeting or create new one.

        Args:
            db: Database session
            meeting_id: Meeting ID

        Returns:
            Meeting instance

        Raises:
            ProcessingError: If meeting cannot be loaded or created
        """
        meeting = db.query(Meeting).filter(Meeting.meeting_id == meeting_id).first()

        if meeting:
            logger.info("Existing meeting found", meeting_id=meeting_id, status=meeting.status)
            return meeting

        # If not in database, fetch from Google Meet API
        logger.info("Meeting not in database, fetching from API", meeting_id=meeting_id)

        # TODO: Implement fetching single meeting from API
        # For now, raise error - meetings should be polled first
        raise ProcessingError(
            f"Meeting not found in database: {meeting_id}",
            details={"meeting_id": meeting_id},
        )

    def _update_meeting_status(
        self,
        db: Session,
        meeting: Meeting,
        status: MeetingStatus,
    ) -> None:
        """Update meeting status and log transition.

        Args:
            db: Database session
            meeting: Meeting instance
            status: New status
        """
        old_status = meeting.status
        meeting.status = status
        meeting.updated_at = datetime.utcnow()
        db.commit()

        logger.info(
            "Meeting status updated",
            meeting_id=meeting.meeting_id,
            old_status=old_status.value if old_status else None,
            new_status=status.value,
        )

    def _get_folder_for_project(self, project_name: str) -> str:
        """Get Drive folder ID for project.

        Args:
            project_name: Project name

        Returns:
            Drive folder ID
        """
        # Get folder mapping from classification service
        folder_mapping = self.classification_service.get_project_folder_mapping()

        # If project has folder mapping, use it
        if project_name in folder_mapping:
            return folder_mapping[project_name]

        # Otherwise fall back to root folder
        from src.config import settings

        logger.warning(
            "No folder mapping for project, using root folder",
            project_name=project_name,
        )
        return settings.drive_root_folder_id
