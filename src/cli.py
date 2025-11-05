import sys
from datetime import datetime, timedelta

import click

from src.config import settings
from src.models import get_db
from src.services.classification import ClassificationService
from src.services.google_drive import GoogleDriveService
from src.services.google_meet import GoogleMeetService
from src.services.meeting_processor import MeetingProcessor
from src.utils.logging import get_logger, setup_logging

# Setup logging
setup_logging()
logger = get_logger(__name__)


@click.group()
def cli() -> None:
    """MeetHub CLI for manual meeting processing and testing."""
    pass


@cli.command()
@click.option("--meeting-id", required=True, help="Meeting ID to process")
def process_meeting(meeting_id: str) -> None:
    """Process a single meeting manually.

    Args:
        meeting_id: Meeting ID to process
    """
    logger.info("Manual meeting processing requested", meeting_id=meeting_id)

    try:
        processor = MeetingProcessor()
        db = next(get_db())

        # Run async processing
        result = asyncio.run(processor.process_meeting(meeting_id, db))

        if result["success"]:
            click.echo(f"✓ Meeting processed successfully!")
            click.echo(f"  Meeting ID: {meeting_id}")
            click.echo(f"  Status: {result['status']}")
            click.echo(f"  Words: {result.get('word_count', 'N/A')}")
            click.echo(f"  Speakers: {result.get('speaker_count', 'N/A')}")
            click.echo(f"  Drive File ID: {result.get('drive_file_id', 'N/A')}")
        else:
            click.echo(f"✗ Meeting processing failed: {result.get('reason', 'unknown')}")
            sys.exit(1)

    except Exception as e:
        logger.error("Meeting processing failed", meeting_id=meeting_id, error=str(e))
        click.echo(f"✗ Error: {e}", err=True)
        sys.exit(1)


@cli.command()
def test_auth() -> None:
    """Test Google service account authentication."""
    logger.info("Testing Google API authentication")

    try:
        # Test Google Meet API
        click.echo("Testing Google Meet API authentication...")
        meet_service = GoogleMeetService()
        click.echo("✓ Google Meet API authenticated successfully")

        # Test Google Drive API
        click.echo("Testing Google Drive API authentication...")
        drive_service = GoogleDriveService()
        click.echo("✓ Google Drive API authenticated successfully")

        # List project folders
        click.echo("\nListing project folders...")
        folders = drive_service.list_project_folders()
        if folders:
            click.echo(f"Found {len(folders)} project folders:")
            for folder in folders:
                click.echo(f"  - {folder['name']} (ID: {folder['id']})")
        else:
            click.echo("  No project folders found")

        click.echo("\n✓ All authentication tests passed!")

    except Exception as e:
        logger.error("Authentication test failed", error=str(e))
        click.echo(f"✗ Authentication failed: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.option(
    "--since-hours",
    default=1,
    type=int,
    help="Poll for meetings since N hours ago (default: 1)",
)
@click.option(
    "--limit",
    default=10,
    type=int,
    help="Maximum number of meetings to retrieve (default: 10)",
)
def poll_meetings(since_hours: int, limit: int) -> None:
    """Poll for ended meetings from Google Meet API.

    Args:
        since_hours: Hours to look back
        limit: Maximum meetings to retrieve
    """
    logger.info("Polling for ended meetings", since_hours=since_hours, limit=limit)

    try:
        meet_service = GoogleMeetService()
        since = datetime.utcnow() - timedelta(hours=since_hours)

        click.echo(f"Polling for meetings since {since.isoformat()}...")
        meetings = meet_service.poll_ended_meetings(since=since, limit=limit)

        if meetings:
            click.echo(f"\n✓ Found {len(meetings)} ended meetings:")
            for i, meeting in enumerate(meetings, 1):
                click.echo(f"\n{i}. {meeting['title']}")
                click.echo(f"   Meeting ID: {meeting['meeting_id']}")
                click.echo(f"   Start: {meeting['start_time'].isoformat()}")
                click.echo(f"   End: {meeting['end_time'].isoformat()}")
                click.echo(f"   Duration: {meeting['duration_minutes']} minutes")
        else:
            click.echo("No ended meetings found in the specified time range")

    except Exception as e:
        logger.error("Polling failed", error=str(e))
        click.echo(f"✗ Polling failed: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.option("--meeting-id", required=True, help="Meeting ID to check")
def check_recording(meeting_id: str) -> None:
    """Check if recording exists for a meeting.

    Args:
        meeting_id: Meeting ID to check
    """
    logger.info("Checking for recording", meeting_id=meeting_id)

    try:
        meet_service = GoogleMeetService()

        click.echo(f"Checking for recording: {meeting_id}...")
        recording_info = meet_service.check_recording_exists(meeting_id)

        if recording_info:
            click.echo("\n✓ Recording found!")
            click.echo(f"  Drive File ID: {recording_info['drive_id']}")
            click.echo(f"  Size: {round(recording_info['size_bytes'] / (1024 * 1024), 2)} MB")
            click.echo(f"  URL: {recording_info.get('url', 'N/A')}")
        else:
            click.echo("✗ No recording found for this meeting")

    except Exception as e:
        logger.error("Recording check failed", meeting_id=meeting_id, error=str(e))
        click.echo(f"✗ Error: {e}", err=True)
        sys.exit(1)


@cli.command()
def test_classification() -> None:
    """Test classification rules with sample meetings."""
    logger.info("Testing classification rules")

    try:
        service = ClassificationService()

        # Test cases
        test_cases = [
            {
                "title": "[VNO] Weekly Standup",
                "emails": [],
                "expected": "VNO",
            },
            {
                "title": "Project Review",
                "emails": ["user@cliente.com"],
                "expected": "CLIENTE_X",
            },
            {
                "title": "Client Onboarding Session",
                "emails": [],
                "expected": "NOVOS_CLIENTES",
            },
            {
                "title": "Random Meeting",
                "emails": [],
                "expected": "GERAL",
            },
        ]

        click.echo("Testing classification rules:\n")
        all_passed = True

        for i, test in enumerate(test_cases, 1):
            project = service.classify_meeting(
                meeting_title=test["title"],
                participant_emails=test["emails"],
            )

            passed = project == test["expected"]
            all_passed = all_passed and passed

            status = "✓" if passed else "✗"
            click.echo(f"{i}. {status} Title: '{test['title']}'")
            click.echo(f"   Emails: {test['emails'] if test['emails'] else 'None'}")
            click.echo(f"   Expected: {test['expected']}, Got: {project}")
            click.echo()

        if all_passed:
            click.echo("✓ All classification tests passed!")
        else:
            click.echo("✗ Some classification tests failed")
            sys.exit(1)

    except Exception as e:
        logger.error("Classification test failed", error=str(e))
        click.echo(f"✗ Error: {e}", err=True)
        sys.exit(1)


@cli.command()
def show_config() -> None:
    """Display current configuration."""
    click.echo("MeetHub Configuration:")
    click.echo(f"  Environment: {settings.environment}")
    click.echo(f"  Log Level: {settings.log_level}")
    click.echo(f"  Database URL: {settings.database_url}")
    click.echo(f"  Service Account: {settings.google_service_account_path}")
    click.echo(f"  Drive Root Folder: {settings.drive_root_folder_id}")
    click.echo(f"  Deepgram Model: {settings.deepgram_model}")
    click.echo(f"  Transcription Language: {settings.transcription_language}")
    click.echo(f"  Poll Interval: {settings.poll_interval_minutes} minutes")
    click.echo(f"  Max Concurrent Jobs: {settings.max_concurrent_jobs}")
    click.echo(f"  Max Retries: {settings.max_retries}")


if __name__ == "__main__":
    cli()
