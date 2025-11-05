"""Pytest configuration and shared fixtures."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.models import Base


@pytest.fixture(scope="function")
def test_db():
    """Create a test database for each test function."""
    # Use in-memory SQLite for tests
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = TestSessionLocal()

    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(engine)


@pytest.fixture(scope="function")
def db_session():
    """Create a test database session (alias for test_db)."""
    # Use in-memory SQLite for tests
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = TestSessionLocal()

    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(engine)


@pytest.fixture
def sample_meeting_data():
    """Sample meeting data for testing."""
    from datetime import datetime

    return {
        "meeting_id": "test-meeting-123",
        "title": "[VNO] Test Meeting",
        "start_time": datetime(2025, 11, 1, 10, 0, 0),
        "end_time": datetime(2025, 11, 1, 11, 0, 0),
        "duration_minutes": 60,
        "project_name": "VNO",
    }


@pytest.fixture
def sample_transcription_data():
    """Sample transcription data for testing."""
    return {
        "full_text": "Hello everyone. Let's get started with today's meeting.",
        "utterances": [
            {
                "speaker": "speaker_0",
                "text": "Hello everyone.",
                "start": 0.0,
                "end": 2.5,
                "confidence": 0.95,
            },
            {
                "speaker": "speaker_1",
                "text": "Let's get started with today's meeting.",
                "start": 3.0,
                "end": 6.0,
                "confidence": 0.92,
            },
        ],
        "word_count": 9,
        "speaker_count": 2,
        "speakers": ["speaker_0", "speaker_1"],
    }
