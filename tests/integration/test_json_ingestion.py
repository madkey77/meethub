"""Integration tests for JSON chat export ingestion.

Tests JSON parsing for Slack/Teams/WhatsApp exports with message extraction
and participant tracking.
"""

import json
from pathlib import Path

import pytest

from src.models import Project
from src.services.file_ingestion import FileIngestionService


@pytest.fixture
def slack_export_file(tmp_path):
    """Create sample Slack JSON export."""
    slack_data = [
        {
            "user": "alice",
            "text": "Hey team, let's discuss the new feature",
            "ts": "1699012345.000100"
        },
        {
            "user": "bob",
            "text": "Sounds good! I think we should prioritize the RAG pipeline",
            "ts": "1699012350.000200"
        },
        {
            "user": "alice",
            "text": "Agreed. Let's start with file ingestion",
            "ts": "1699012355.000300"
        },
        {
            "user": "charlie",
            "text": "I can help with the testing",
            "ts": "1699012360.000400"
        }
    ]

    slack_path = tmp_path / "slack_export.json"
    slack_path.write_text(json.dumps(slack_data, indent=2))
    return slack_path


@pytest.fixture
def test_project(db_session):
    """Create test project."""
    project = Project(
        name="json-test-project",
        drive_folder_id="test-folder-json",
        classification_rules=[],
        is_default=False,
    )
    db_session.add(project)
    db_session.commit()
    db_session.refresh(project)
    return project


class TestJSONIngestion:
    """Integration tests for JSON chat export ingestion."""

    def test_slack_json_message_extraction(self, db_session, test_project, slack_export_file):
        """Test message extraction from Slack JSON export.

        Verifies:
        - Messages are parsed correctly
        - User names are extracted
        - Text content is complete
        """
        service = FileIngestionService(db_session)

        text, metadata = service.extract_text(
            file_path=str(slack_export_file),
            mime_type="application/json"
        )

        # Verify messages extracted
        assert text is not None
        assert "alice" in text.lower()
        assert "RAG pipeline" in text
        assert "file ingestion" in text

    def test_slack_json_metadata_message_count(self, db_session, slack_export_file):
        """Test message count tracking.

        Verifies:
        - message_count is calculated
        - Matches number of messages in file
        """
        service = FileIngestionService(db_session)

        text, metadata = service.extract_text(
            file_path=str(slack_export_file),
            mime_type="application/json"
        )

        assert "message_count" in metadata
        assert metadata["message_count"] == 4

    def test_slack_json_participants_extraction(self, db_session, slack_export_file):
        """Test participant extraction from Slack export.

        Verifies:
        - Unique participants are tracked
        - participants list is in metadata
        """
        service = FileIngestionService(db_session)

        text, metadata = service.extract_text(
            file_path=str(slack_export_file),
            mime_type="application/json"
        )

        assert "participants" in metadata
        participants = metadata["participants"]
        assert len(participants) == 3  # alice, bob, charlie
        assert "alice" in participants
        assert "bob" in participants
        assert "charlie" in participants

    def test_json_format_detection(self, db_session, slack_export_file):
        """Test JSON format detection.

        Verifies:
        - format field indicates Slack/Teams
        - extraction_method is 'json'
        """
        service = FileIngestionService(db_session)

        text, metadata = service.extract_text(
            file_path=str(slack_export_file),
            mime_type="application/json"
        )

        assert "format" in metadata
        assert metadata["format"] in ["slack/teams", "generic"]
        assert metadata["extraction_method"] == "json"
