"""Integration tests for GoogleMeetService."""

import pytest
from datetime import datetime, timedelta

from src.services.google_meet import GoogleMeetService
from src.utils.exceptions import AuthenticationError, GoogleMeetAPIError


@pytest.mark.integration
class TestGoogleMeetService:
    """Integration tests for Google Meet API service."""

    def test_service_initialization(self):
        """Test that GoogleMeetService initializes with valid credentials."""
        try:
            service = GoogleMeetService()
            assert service.credentials is not None
            assert service.meet_service is not None
            assert service.drive_service is not None
        except AuthenticationError:
            pytest.skip("Service account credentials not configured")

    @pytest.mark.integration
    def test_poll_ended_meetings(self):
        """Test polling for ended meetings.

        Note: This test requires actual Google Meet API access and may not find meetings
        depending on when it's run.
        """
        try:
            service = GoogleMeetService()
            since = datetime.utcnow() - timedelta(hours=24)

            meetings = service.poll_ended_meetings(since=since, limit=10)

            # Should return a list (may be empty if no meetings in time range)
            assert isinstance(meetings, list)

            # If meetings found, validate structure
            if meetings:
                meeting = meetings[0]
                assert "meeting_id" in meeting
                assert "title" in meeting
                assert "start_time" in meeting
                assert "end_time" in meeting
                assert "duration_minutes" in meeting
                assert isinstance(meeting["start_time"], datetime)
                assert isinstance(meeting["end_time"], datetime)

        except AuthenticationError:
            pytest.skip("Service account credentials not configured")
        except GoogleMeetAPIError as e:
            pytest.skip(f"Google Meet API error (may be permissions): {e}")

    @pytest.mark.integration
    def test_check_recording_exists_not_found(self):
        """Test checking for a non-existent recording."""
        try:
            service = GoogleMeetService()

            # Use a fake meeting ID that shouldn't exist
            recording_info = service.check_recording_exists("nonexistent-meeting-id-12345")

            # Should return None for non-existent recording
            assert recording_info is None

        except AuthenticationError:
            pytest.skip("Service account credentials not configured")
        except GoogleMeetAPIError as e:
            pytest.skip(f"Google Meet API error: {e}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--run-integration"])
