"""Integration tests for SchedulerService.

These tests verify the scheduler's behavior with a real database but mocked external APIs.
"""

import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.orm import Session

from src.models import Meeting, MeetingStatus, ProcessingJob, ProcessingJobStatus
from src.services.scheduler import SchedulerService


@pytest.fixture
def mock_google_meet_service():
    """Mock Google Meet service."""
    with patch("src.services.scheduler.GoogleMeetService") as mock:
        instance = MagicMock()
        instance.poll_ended_meetings.return_value = [
            {
                "meeting_id": "test-meeting-1",
                "title": "Test Meeting 1",
                "start_time": datetime.utcnow() - timedelta(hours=2),
                "end_time": datetime.utcnow() - timedelta(hours=1),
                "duration_minutes": 60,
                "organizer_email": "test@example.com",
            }
        ]
        mock.return_value = instance
        yield instance


@pytest.fixture
def mock_meeting_processor():
    """Mock meeting processor."""
    with patch("src.services.scheduler.MeetingProcessor") as mock:
        instance = MagicMock()
        instance.process_meeting = AsyncMock(
            return_value={
                "success": True,
                "meeting_id": "test-meeting-1",
                "status": "completed",
            }
        )
        mock.return_value = instance
        yield instance


@pytest.mark.asyncio
async def test_scheduler_initialization():
    """Test scheduler initializes correctly."""
    scheduler = SchedulerService()

    assert scheduler.scheduler is not None
    assert scheduler.google_meet_service is not None
    assert scheduler.meeting_processor is not None
    assert scheduler.semaphore._value == 3  # Default max_concurrent_jobs
    assert scheduler.is_running is False


@pytest.mark.asyncio
async def test_scheduler_start_and_stop():
    """Test scheduler can start and stop."""
    scheduler = SchedulerService()

    # Start scheduler
    scheduler.start()
    assert scheduler.is_running is True
    assert scheduler.scheduler.running is True

    # Stop scheduler
    scheduler.stop()
    assert scheduler.is_running is False
    assert scheduler.scheduler.running is False


@pytest.mark.asyncio
async def test_polling_job_creates_meetings(
    db_session: Session,
    mock_google_meet_service,
    mock_meeting_processor,
):
    """Test polling job creates new meetings in database."""
    scheduler = SchedulerService()

    # Run polling job
    await scheduler._polling_job()

    # Verify meeting was created
    meeting = db_session.query(Meeting).filter(Meeting.meeting_id == "test-meeting-1").first()
    assert meeting is not None
    assert meeting.title == "Test Meeting 1"
    assert meeting.status == MeetingStatus.DETECTED

    # Verify processing job was created
    await asyncio.sleep(0.1)  # Give async task time to start
    job = (
        db_session.query(ProcessingJob).filter(ProcessingJob.meeting_id == "test-meeting-1").first()
    )
    assert job is not None


@pytest.mark.asyncio
async def test_polling_job_skips_existing_meetings(
    db_session: Session,
    mock_google_meet_service,
    mock_meeting_processor,
):
    """Test polling job skips meetings that are already completed."""
    # Create existing completed meeting
    existing_meeting = Meeting(
        meeting_id="test-meeting-1",
        title="Existing Meeting",
        start_time=datetime.utcnow() - timedelta(hours=2),
        end_time=datetime.utcnow() - timedelta(hours=1),
        duration_minutes=60,
        status=MeetingStatus.COMPLETED,
    )
    db_session.add(existing_meeting)
    db_session.commit()

    scheduler = SchedulerService()

    # Run polling job
    await scheduler._polling_job()

    # Verify no processing job was created
    job = (
        db_session.query(ProcessingJob).filter(ProcessingJob.meeting_id == "test-meeting-1").first()
    )
    assert job is None


@pytest.mark.asyncio
async def test_process_meeting_async_success(
    db_session: Session,
    mock_meeting_processor,
):
    """Test async meeting processing updates job status correctly."""
    # Create meeting and job
    meeting = Meeting(
        meeting_id="test-meeting-2",
        title="Test Meeting",
        start_time=datetime.utcnow() - timedelta(hours=1),
        end_time=datetime.utcnow(),
        duration_minutes=60,
        status=MeetingStatus.DETECTED,
    )
    db_session.add(meeting)
    db_session.commit()

    job = ProcessingJob(
        meeting_id="test-meeting-2",
        status=ProcessingJobStatus.PENDING,
        retry_count=0,
    )
    db_session.add(job)
    db_session.commit()
    job_id = job.job_id

    scheduler = SchedulerService()

    # Process meeting
    await scheduler._process_meeting_async(job_id, "test-meeting-2")

    # Verify job was updated
    db_session.refresh(job)
    assert job.status == ProcessingJobStatus.COMPLETED
    assert job.started_at is not None
    assert job.completed_at is not None


@pytest.mark.asyncio
async def test_process_meeting_async_failure(
    db_session: Session,
):
    """Test async meeting processing handles failures correctly."""
    # Create meeting and job
    meeting = Meeting(
        meeting_id="test-meeting-3",
        title="Test Meeting",
        start_time=datetime.utcnow() - timedelta(hours=1),
        end_time=datetime.utcnow(),
        duration_minutes=60,
        status=MeetingStatus.DETECTED,
    )
    db_session.add(meeting)
    db_session.commit()

    job = ProcessingJob(
        meeting_id="test-meeting-3",
        status=ProcessingJobStatus.PENDING,
        retry_count=0,
    )
    db_session.add(job)
    db_session.commit()
    job_id = job.job_id

    # Mock processor to raise exception
    with patch("src.services.scheduler.MeetingProcessor") as mock:
        instance = MagicMock()
        instance.process_meeting = AsyncMock(side_effect=Exception("Processing failed"))
        mock.return_value = instance

        scheduler = SchedulerService()

        # Process meeting
        await scheduler._process_meeting_async(job_id, "test-meeting-3")

    # Verify job was marked as failed
    db_session.refresh(job)
    assert job.status == ProcessingJobStatus.FAILED
    assert job.error_message == "Processing failed"


@pytest.mark.asyncio
async def test_retry_job_retries_failed_jobs(
    db_session: Session,
    mock_meeting_processor,
):
    """Test retry job retries failed jobs with exponential backoff."""
    # Create failed job (old enough to retry)
    meeting = Meeting(
        meeting_id="test-meeting-4",
        title="Test Meeting",
        start_time=datetime.utcnow() - timedelta(hours=1),
        end_time=datetime.utcnow(),
        duration_minutes=60,
        status=MeetingStatus.FAILED,
    )
    db_session.add(meeting)
    db_session.commit()

    job = ProcessingJob(
        meeting_id="test-meeting-4",
        status=ProcessingJobStatus.FAILED,
        retry_count=0,
        started_at=datetime.utcnow() - timedelta(minutes=10),  # Old enough to retry
        error_message="Previous error",
    )
    db_session.add(job)
    db_session.commit()

    scheduler = SchedulerService()

    # Run retry job
    await scheduler._retry_job()

    # Wait for async task
    await asyncio.sleep(0.1)

    # Verify job was updated for retry
    db_session.refresh(job)
    assert job.retry_count == 1
    assert job.status in [ProcessingJobStatus.PENDING, ProcessingJobStatus.RUNNING]


@pytest.mark.asyncio
async def test_retry_job_respects_max_retries(
    db_session: Session,
):
    """Test retry job does not retry jobs that exceeded max retries."""
    # Create failed job with max retries exceeded
    meeting = Meeting(
        meeting_id="test-meeting-5",
        title="Test Meeting",
        start_time=datetime.utcnow() - timedelta(hours=1),
        end_time=datetime.utcnow(),
        duration_minutes=60,
        status=MeetingStatus.FAILED,
    )
    db_session.add(meeting)
    db_session.commit()

    job = ProcessingJob(
        meeting_id="test-meeting-5",
        status=ProcessingJobStatus.FAILED,
        retry_count=3,  # Already at max
        started_at=datetime.utcnow() - timedelta(minutes=10),
        error_message="Previous error",
    )
    db_session.add(job)
    db_session.commit()

    scheduler = SchedulerService()

    # Run retry job
    await scheduler._retry_job()

    # Wait for async task
    await asyncio.sleep(0.1)

    # Verify job was NOT retried
    db_session.refresh(job)
    assert job.retry_count == 3
    assert job.status == ProcessingJobStatus.FAILED


@pytest.mark.asyncio
async def test_health_check_job_logs_statistics(
    db_session: Session,
):
    """Test health check job logs statistics correctly."""
    # Create various jobs
    for i in range(5):
        job = ProcessingJob(
            meeting_id=f"meeting-{i}",
            status=ProcessingJobStatus.COMPLETED if i < 3 else ProcessingJobStatus.FAILED,
            retry_count=0,
        )
        db_session.add(job)
    db_session.commit()

    scheduler = SchedulerService()
    scheduler.is_running = True

    # Run health check (should not raise exception)
    await scheduler._health_check_job()


@pytest.mark.asyncio
async def test_calculate_retry_delay():
    """Test exponential backoff calculation."""
    scheduler = SchedulerService()

    # First retry: 120s * (2^0) = 120s
    assert scheduler._calculate_retry_delay(0) == 120

    # Second retry: 120s * (2^1) = 240s
    assert scheduler._calculate_retry_delay(1) == 240

    # Third retry: 120s * (2^2) = 480s
    assert scheduler._calculate_retry_delay(2) == 480

    # Fourth retry: capped at max (480s)
    assert scheduler._calculate_retry_delay(3) == 480


@pytest.mark.asyncio
async def test_get_last_poll_time_with_existing_meeting(
    db_session: Session,
):
    """Test get_last_poll_time returns last completed meeting end time."""
    # Create completed meeting
    meeting = Meeting(
        meeting_id="test-meeting-6",
        title="Test Meeting",
        start_time=datetime.utcnow() - timedelta(hours=2),
        end_time=datetime.utcnow() - timedelta(hours=1),
        duration_minutes=60,
        status=MeetingStatus.COMPLETED,
    )
    db_session.add(meeting)
    db_session.commit()

    scheduler = SchedulerService()

    last_poll_time = scheduler._get_last_poll_time(db_session)

    # Should return meeting end time
    assert last_poll_time == meeting.end_time


@pytest.mark.asyncio
async def test_get_last_poll_time_without_meetings(
    db_session: Session,
):
    """Test get_last_poll_time returns 1 hour ago when no meetings exist."""
    scheduler = SchedulerService()

    last_poll_time = scheduler._get_last_poll_time(db_session)

    # Should return approximately 1 hour ago
    expected_time = datetime.utcnow() - timedelta(hours=1)
    time_diff = abs((last_poll_time - expected_time).total_seconds())
    assert time_diff < 5  # Within 5 seconds
