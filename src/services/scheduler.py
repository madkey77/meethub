"""Background scheduler service for automated meeting polling and processing."""

import asyncio
import signal
from datetime import datetime, timedelta
from typing import Any

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy.orm import Session

from src.config import settings
from src.models import Meeting, MeetingStatus, ProcessingJob, JobStatus, Transcript, get_db
from src.services.google_meet import GoogleMeetService
from src.services.meeting_processor import MeetingProcessor
from src.services.meeting_rag_bridge import MeetingRAGBridge
from src.utils.exceptions import MeetHubError
from src.utils.logging import bind_context, clear_context, get_logger

logger = get_logger(__name__)


class SchedulerService:
    """Background scheduler for automatic meeting polling and processing."""

    def __init__(self) -> None:
        """Initialize scheduler service."""
        self.scheduler = AsyncIOScheduler()
        self.google_meet_service = GoogleMeetService()
        self.meeting_processor = MeetingProcessor()
        self.semaphore = asyncio.Semaphore(settings.max_concurrent_jobs)
        self.is_running = False
        self.shutdown_event = asyncio.Event()
        self.last_poll_time: datetime | None = None

        logger.info(
            "Scheduler service initialized",
            poll_interval_minutes=settings.poll_interval_minutes,
            max_concurrent_jobs=settings.max_concurrent_jobs,
        )

    def start(self) -> None:
        """Start the scheduler with polling job."""
        if self.is_running:
            logger.warning("Scheduler already running")
            return

        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)

        # Schedule polling job
        self.scheduler.add_job(
            func=self._polling_job,
            trigger=IntervalTrigger(minutes=settings.poll_interval_minutes),
            id="meeting_polling",
            name="Poll for new meetings",
            replace_existing=True,
            max_instances=1,  # Prevent overlapping polls
        )

        # Schedule hourly health check
        self.scheduler.add_job(
            func=self._health_check_job,
            trigger=IntervalTrigger(hours=1),
            id="health_check",
            name="Health check logging",
            replace_existing=True,
        )

        # Schedule retry job (runs every 5 minutes to check for failed jobs)
        self.scheduler.add_job(
            func=self._retry_job,
            trigger=IntervalTrigger(minutes=5),
            id="retry_failed_jobs",
            name="Retry failed jobs",
            replace_existing=True,
            max_instances=1,
        )

        self.scheduler.start()
        self.is_running = True
        logger.info("Scheduler started")

    def stop(self) -> None:
        """Stop the scheduler gracefully."""
        if not self.is_running:
            logger.warning("Scheduler not running")
            return

        logger.info("Stopping scheduler...")
        self.scheduler.shutdown(wait=True)
        self.is_running = False
        logger.info("Scheduler stopped")

    async def run_forever(self) -> None:
        """Run scheduler until shutdown signal received."""
        try:
            # Trigger initial poll immediately
            logger.info("Running initial poll")
            await self._polling_job()

            # Wait for shutdown signal
            await self.shutdown_event.wait()
        except Exception as e:
            logger.error("Scheduler run error", error=str(e), error_type=type(e).__name__)
            raise
        finally:
            self.stop()

    def _signal_handler(self, signum: int, frame: Any) -> None:
        """Handle shutdown signals (SIGTERM, SIGINT).

        Args:
            signum: Signal number
            frame: Current stack frame
        """
        signal_name = signal.Signals(signum).name
        logger.info(f"Received {signal_name}, initiating graceful shutdown")
        self.shutdown_event.set()

    async def _polling_job(self) -> None:
        """Poll for new meetings and queue them for processing."""
        bind_context(job_type="polling")

        try:
            logger.info("Starting meeting polling job")

            db: Session = next(get_db())

            try:
                # Determine polling window (default: since last poll or 1 hour ago)
                since_time = self._get_last_poll_time(db)
                logger.info("Polling for meetings", since=since_time.isoformat())

                # Poll for ended meetings
                meetings_data = self.google_meet_service.poll_ended_meetings(since_time)

                if not meetings_data:
                    logger.info("No new meetings found")
                    return

                logger.info(f"Found {len(meetings_data)} meetings to process")

                # Create or update meeting records
                for meeting_data in meetings_data:
                    meeting_id = meeting_data["meeting_id"]

                    # Check if meeting already exists
                    existing_meeting = (
                        db.query(Meeting).filter(Meeting.meeting_id == meeting_id).first()
                    )

                    if existing_meeting:
                        logger.debug(
                            "Meeting already exists",
                            meeting_id=meeting_id,
                            status=existing_meeting.status.value,
                        )

                        # Only process if not already completed or in progress
                        if existing_meeting.status in [
                            MeetingStatus.COMPLETED,
                            MeetingStatus.DOWNLOADING,
                            MeetingStatus.TRANSCRIBING,
                            MeetingStatus.UPLOADING,
                        ]:
                            continue
                    else:
                        # Create new meeting record
                        new_meeting = Meeting(
                            meeting_id=meeting_id,
                            title=meeting_data["title"],
                            start_time=meeting_data["start_time"],
                            end_time=meeting_data["end_time"],
                            duration_minutes=meeting_data["duration_minutes"],
                            status=MeetingStatus.DETECTED,
                        )
                        db.add(new_meeting)
                        db.commit()

                        logger.info(
                            "New meeting detected",
                            meeting_id=meeting_id,
                            title=meeting_data["title"],
                        )

                    # Queue processing job
                    await self._queue_processing_job(meeting_id, db)

                # Update last poll time to now
                self.last_poll_time = datetime.utcnow()
                logger.debug("Poll completed", timestamp=self.last_poll_time.isoformat())

            finally:
                db.close()

        except Exception as e:
            logger.error(
                "Polling job failed",
                error=str(e),
                error_type=type(e).__name__,
            )
        finally:
            clear_context()

    async def _queue_processing_job(self, meeting_id: str, db: Session) -> None:
        """Queue a meeting for processing with concurrency control.

        Args:
            meeting_id: Meeting ID to process
            db: Database session
        """
        # Check if job already exists
        existing_job = (
            db.query(ProcessingJob)
            .filter(
                ProcessingJob.meeting_id == meeting_id,
                ProcessingJob.status.in_([JobStatus.PENDING, JobStatus.PROCESSING]),
            )
            .first()
        )

        if existing_job:
            logger.debug(
                "Processing job already exists",
                meeting_id=meeting_id,
                job_id=existing_job.job_id,
            )
            return

        # Create processing job
        job = ProcessingJob(
            meeting_id=meeting_id,
            status=JobStatus.PENDING,
            retry_count=0,
        )
        db.add(job)
        db.commit()

        logger.info("Processing job queued", meeting_id=meeting_id, job_id=job.job_id)

        # Process asynchronously with concurrency control
        asyncio.create_task(self._process_meeting_async(job.job_id, meeting_id))

    async def _process_meeting_async(self, job_id: int, meeting_id: str) -> None:
        """Process a meeting asynchronously with semaphore control.

        Args:
            job_id: Processing job ID
            meeting_id: Meeting ID to process
        """
        async with self.semaphore:
            bind_context(job_id=job_id, meeting_id=meeting_id)

            db: Session = next(get_db())

            try:
                # Update job status to running
                job = db.query(ProcessingJob).filter(ProcessingJob.job_id == job_id).first()
                if not job:
                    logger.error("Processing job not found", job_id=job_id)
                    return

                job.status = JobStatus.PROCESSING
                job.started_at = datetime.utcnow()
                db.commit()

                logger.info("Processing meeting", job_id=job_id, meeting_id=meeting_id)

                # Process meeting
                result = await self.meeting_processor.process_meeting(meeting_id, db)

                # Update job status based on result
                if result.get("success"):
                    job.status = JobStatus.COMPLETED
                    job.completed_at = datetime.utcnow()
                    logger.info("Meeting processing completed", job_id=job_id, meeting_id=meeting_id)

                    # NEW: Trigger RAG bridge after successful transcription
                    await self._trigger_rag_bridge(meeting_id, db)
                else:
                    job.status = JobStatus.FAILED
                    job.error_message = result.get("reason", "Unknown error")
                    logger.warning(
                        "Meeting processing failed",
                        job_id=job_id,
                        meeting_id=meeting_id,
                        reason=job.error_message,
                    )

                db.commit()

            except Exception as e:
                logger.error(
                    "Meeting processing error",
                    job_id=job_id,
                    meeting_id=meeting_id,
                    error=str(e),
                    error_type=type(e).__name__,
                )

                # Update job as failed
                job = db.query(ProcessingJob).filter(ProcessingJob.job_id == job_id).first()
                if job:
                    job.status = JobStatus.FAILED
                    job.error_message = str(e)
                    db.commit()

            finally:
                db.close()
                clear_context()

    async def _trigger_rag_bridge(self, meeting_id: str, db: Session) -> None:
        """Trigger RAG bridge to ingest completed transcript.

        This is called after a meeting is successfully transcribed and uploaded.
        It triggers the RAG pipeline to create embeddings and make the meeting
        searchable.

        Args:
            meeting_id: Meeting ID to process
            db: Database session
        """
        try:
            # Find the transcript for this meeting
            transcript = (
                db.query(Transcript)
                .filter(Transcript.meeting_id == meeting_id)
                .first()
            )

            if not transcript:
                logger.warning(
                    "rag_bridge.transcript_not_found",
                    meeting_id=meeting_id,
                )
                return

            # Create RAG bridge (without RAG pipeline for now - will be async)
            bridge = MeetingRAGBridge(
                db_session=db,
                rag_pipeline=None,  # RAG pipeline will be triggered separately
                file_ingestion_service=None,
            )

            # Execute bridge to create File/FileVersion
            file = bridge.on_transcription_complete(transcript.transcript_id)

            if file:
                logger.info(
                    "rag_bridge.file_created",
                    meeting_id=meeting_id,
                    file_id=file.file_id,
                    transcript_id=transcript.transcript_id,
                )
            else:
                logger.info(
                    "rag_bridge.skipped",
                    meeting_id=meeting_id,
                    transcript_id=transcript.transcript_id,
                )

        except Exception as e:
            logger.error(
                "rag_bridge.failed",
                meeting_id=meeting_id,
                error=str(e),
                error_type=type(e).__name__,
            )
            # Don't fail the transcription job if RAG bridge fails

    async def _retry_job(self) -> None:
        """Check for failed jobs and retry with exponential backoff."""
        bind_context(job_type="retry")

        try:
            db: Session = next(get_db())

            try:
                # Find failed jobs that haven't exceeded max retries
                failed_jobs = (
                    db.query(ProcessingJob)
                    .filter(
                        ProcessingJob.status == JobStatus.FAILED,
                        ProcessingJob.retry_count < settings.max_retries,
                    )
                    .all()
                )

                if not failed_jobs:
                    return

                logger.info(f"Found {len(failed_jobs)} failed jobs to retry")

                for job in failed_jobs:
                    # Calculate backoff delay
                    retry_delay_seconds = self._calculate_retry_delay(job.retry_count)

                    # Check if enough time has passed since last attempt
                    if job.started_at:
                        time_since_failure = datetime.utcnow() - job.started_at
                        if time_since_failure.total_seconds() < retry_delay_seconds:
                            logger.debug(
                                "Job not ready for retry",
                                job_id=job.job_id,
                                retry_count=job.retry_count,
                                wait_remaining_seconds=retry_delay_seconds
                                - time_since_failure.total_seconds(),
                            )
                            continue

                    # Retry job
                    logger.info(
                        "Retrying failed job",
                        job_id=job.job_id,
                        meeting_id=job.meeting_id,
                        retry_count=job.retry_count + 1,
                        max_retries=settings.max_retries,
                    )

                    job.retry_count += 1
                    job.status = JobStatus.PENDING
                    job.error_message = None
                    db.commit()

                    # Queue for processing
                    asyncio.create_task(self._process_meeting_async(job.job_id, job.meeting_id))

            finally:
                db.close()

        except Exception as e:
            logger.error(
                "Retry job failed",
                error=str(e),
                error_type=type(e).__name__,
            )
        finally:
            clear_context()

    async def _health_check_job(self) -> None:
        """Log health check status with job statistics."""
        bind_context(job_type="health_check")

        try:
            db: Session = next(get_db())

            try:
                # Get job statistics
                total_jobs = db.query(ProcessingJob).count()
                pending_jobs = (
                    db.query(ProcessingJob)
                    .filter(ProcessingJob.status == JobStatus.PENDING)
                    .count()
                )
                running_jobs = (
                    db.query(ProcessingJob)
                    .filter(ProcessingJob.status == JobStatus.PROCESSING)
                    .count()
                )
                completed_jobs = (
                    db.query(ProcessingJob)
                    .filter(ProcessingJob.status == JobStatus.COMPLETED)
                    .count()
                )
                failed_jobs = (
                    db.query(ProcessingJob)
                    .filter(ProcessingJob.status == JobStatus.FAILED)
                    .count()
                )

                # Calculate success rate
                total_finished = completed_jobs + failed_jobs
                success_rate = (completed_jobs / total_finished * 100) if total_finished > 0 else 0.0

                # Check for high usage (>20 meetings/day)
                from datetime import timedelta

                today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
                today_jobs = (
                    db.query(ProcessingJob)
                    .filter(ProcessingJob.created_at >= today_start)
                    .count()
                )

                logger.info(
                    "Health check",
                    total_jobs=total_jobs,
                    pending=pending_jobs,
                    running=running_jobs,
                    completed=completed_jobs,
                    failed=failed_jobs,
                    success_rate_pct=round(success_rate, 2),
                    jobs_today=today_jobs,
                    scheduler_running=self.is_running,
                )

                # Alert if high usage detected
                if today_jobs > 20:
                    logger.warning(
                        "High meeting volume detected",
                        jobs_today=today_jobs,
                        threshold=20,
                        message="Consider reviewing Deepgram API costs",
                    )

            finally:
                db.close()

        except Exception as e:
            logger.error(
                "Health check failed",
                error=str(e),
                error_type=type(e).__name__,
            )
        finally:
            clear_context()

    def _calculate_retry_delay(self, retry_count: int) -> int:
        """Calculate exponential backoff delay for retry.

        Args:
            retry_count: Current retry count

        Returns:
            Delay in seconds
        """
        delay = settings.retry_initial_delay_seconds * (settings.retry_multiplier**retry_count)
        return min(int(delay), settings.retry_max_delay_seconds)

    def _get_last_poll_time(self, db: Session) -> datetime:
        """Get last successful poll time or default to 1 hour ago.

        Args:
            db: Database session

        Returns:
            Last poll timestamp
        """
        # Use stored last poll time if available
        if self.last_poll_time:
            logger.debug("Using stored last poll time", last_poll=self.last_poll_time.isoformat())
            return self.last_poll_time

        # On first run, try to get the most recent meeting in database
        last_meeting = (
            db.query(Meeting)
            .order_by(Meeting.end_time.desc())
            .first()
        )

        if last_meeting and last_meeting.end_time:
            # Poll from last meeting end time to catch any we might have missed
            logger.debug("Using last meeting end time", end_time=last_meeting.end_time.isoformat())
            return last_meeting.end_time

        # Default to 1 hour ago on completely fresh start
        default_time = datetime.utcnow() - timedelta(hours=1)
        logger.debug("Using default poll time (1 hour ago)", poll_time=default_time.isoformat())
        return default_time
