"""Integration tests for multiple JSON chat formats.

Tests format-specific parsing for Slack, Teams, and WhatsApp exports.
"""

import json

import pytest

from src.services.file_ingestion import FileIngestionService


class TestMultipleChatFormats:
    """Integration tests for different chat export formats."""

    def test_slack_format_parsing(self, db_session, tmp_path):
        """Test Slack-specific JSON schema parsing."""
        slack_data = [
            {"user": "U123", "text": "Hello", "ts": "1699012345.000100"},
            {"user": "U456", "text": "Hi there", "ts": "1699012350.000200"}
        ]

        slack_path = tmp_path / "slack.json"
        slack_path.write_text(json.dumps(slack_data))

        service = FileIngestionService(db_session)
        text, metadata = service.extract_text(str(slack_path), "application/json")

        assert metadata["format"] == "slack/teams"
        assert "Hello" in text

    def test_teams_format_parsing(self, db_session, tmp_path):
        """Test Microsoft Teams JSON schema parsing."""
        teams_data = [
            {"from": "alice@example.com", "message": "Meeting at 2pm", "timestamp": "2025-11-04T14:00:00Z"},
            {"from": "bob@example.com", "message": "Confirmed", "timestamp": "2025-11-04T14:01:00Z"}
        ]

        teams_path = tmp_path / "teams.json"
        teams_path.write_text(json.dumps(teams_data))

        service = FileIngestionService(db_session)
        text, metadata = service.extract_text(str(teams_path), "application/json")

        assert "Meeting at 2pm" in text or "Confirmed" in text

    def test_whatsapp_format_parsing(self, db_session, tmp_path):
        """Test WhatsApp JSON schema parsing."""
        whatsapp_data = {
            "messages": [
                {"sender": "+5511999999999", "content": "Hello WhatsApp", "timestamp": "2025-11-04T10:00:00Z"},
                {"sender": "+5511888888888", "content": "Hi!", "timestamp": "2025-11-04T10:01:00Z"}
            ]
        }

        whatsapp_path = tmp_path / "whatsapp.json"
        whatsapp_path.write_text(json.dumps(whatsapp_data))

        service = FileIngestionService(db_session)
        text, metadata = service.extract_text(str(whatsapp_path), "application/json")

        assert "Hello WhatsApp" in text or "Hi!" in text

    def test_generic_json_fallback(self, db_session, tmp_path):
        """Test generic JSON format handling."""
        generic_data = {"conversations": [{"speaker": "User", "message": "Generic message"}]}

        generic_path = tmp_path / "generic.json"
        generic_path.write_text(json.dumps(generic_data))

        service = FileIngestionService(db_session)
        text, metadata = service.extract_text(str(generic_path), "application/json")

        # Should handle gracefully even if format unknown
        assert metadata["format"] == "unknown"
