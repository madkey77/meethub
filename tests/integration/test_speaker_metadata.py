"""Integration tests for speaker metadata preservation.

Tests that speaker labels and timestamps flow correctly from Deepgram
through chunking to ChromaDB metadata.
"""

import pytest
from typing import List

from src.services.chunking.meeting_chunker import MeetingChunker
from src.services.chunking.base import ChunkResult


class TestSpeakerMetadataPreservation:
    """Test speaker metadata preservation through chunking."""

    @pytest.fixture
    def sample_deepgram_response(self) -> dict:
        """Sample Deepgram API response with utterances."""
        return {
            "results": {
                "utterances": [
                    {
                        "speaker": 0,
                        "start": 0.5,
                        "end": 5.2,
                        "transcript": "Hello everyone, let's start the meeting. Today we have an important agenda.",
                        "confidence": 0.98,
                    },
                    {
                        "speaker": 1,
                        "start": 5.8,
                        "end": 12.3,
                        "transcript": "Thanks for joining. I'm excited to discuss our progress on the project.",
                        "confidence": 0.95,
                    },
                    {
                        "speaker": 0,
                        "start": 13.0,
                        "end": 18.5,
                        "transcript": "Let's start with the first topic. We need to review the timeline.",
                        "confidence": 0.97,
                    },
                    {
                        "speaker": 2,
                        "start": 19.0,
                        "end": 25.2,
                        "transcript": "I have some concerns about the current schedule that I'd like to raise.",
                        "confidence": 0.93,
                    },
                ]
            }
        }

    def test_chunks_contain_speaker_labels(self, sample_deepgram_response: dict):
        """Test that chunks have speaker metadata in correct format."""
        chunker = MeetingChunker(chunk_size=150, chunk_overlap=30)
        chunks: List[ChunkResult] = chunker.chunk_from_deepgram(sample_deepgram_response)

        # Assert at least one chunk created
        assert len(chunks) > 0

        # Check each chunk has speaker metadata
        for chunk in chunks:
            assert "speaker" in chunk.metadata
            assert chunk.metadata["speaker"].startswith("Speaker ")
            # Extract speaker number and verify it's valid
            speaker_num = chunk.metadata["speaker"].split(" ")[1]
            assert speaker_num.isdigit()
            assert int(speaker_num) >= 0

    def test_chunks_contain_timestamps(self, sample_deepgram_response: dict):
        """Test that chunks have timestamps in HH:MM:SS format."""
        chunker = MeetingChunker(chunk_size=150, chunk_overlap=30)
        chunks: List[ChunkResult] = chunker.chunk_from_deepgram(sample_deepgram_response)

        for chunk in chunks:
            assert "timestamp" in chunk.metadata
            timestamp = chunk.metadata["timestamp"]

            # Verify HH:MM:SS format
            parts = timestamp.split(":")
            assert len(parts) == 3

            hours, minutes, seconds = parts
            assert hours.isdigit() and len(hours) == 2
            assert minutes.isdigit() and len(minutes) == 2
            assert seconds.isdigit() and len(seconds) == 2

    def test_speaker_labels_match_deepgram_format(self, sample_deepgram_response: dict):
        """Test that speaker labels match Deepgram's speaker IDs."""
        chunker = MeetingChunker(chunk_size=150, chunk_overlap=30)
        chunks: List[ChunkResult] = chunker.chunk_from_deepgram(sample_deepgram_response)

        # Extract unique speaker IDs from Deepgram response
        utterances = sample_deepgram_response["results"]["utterances"]
        deepgram_speakers = set(u["speaker"] for u in utterances)

        # Extract speaker numbers from chunks
        chunk_speakers = set()
        for chunk in chunks:
            speaker_label = chunk.metadata["speaker"]
            speaker_num = int(speaker_label.split(" ")[1])
            chunk_speakers.add(speaker_num)

        # Verify chunk speakers are subset of Deepgram speakers
        assert chunk_speakers.issubset(deepgram_speakers)

    def test_participant_mapping_adds_speaker_names(self, sample_deepgram_response: dict):
        """Test that participant mapping adds speaker_name to metadata."""
        chunker = MeetingChunker(chunk_size=150, chunk_overlap=30)

        # Provide participant mapping
        participant_mapping = {
            0: "Alice Smith",
            1: "Bob Jones",
            2: "Carol White",
        }

        chunks: List[ChunkResult] = chunker.chunk_from_deepgram(
            sample_deepgram_response, participant_mapping=participant_mapping
        )

        for chunk in chunks:
            assert "speaker_name" in chunk.metadata

            # If speaker_name is set, verify it's in our mapping
            if chunk.metadata["speaker_name"] is not None:
                assert chunk.metadata["speaker_name"] in participant_mapping.values()

    def test_timestamp_conversion_accuracy(self):
        """Test that timestamp conversion from seconds to HH:MM:SS is accurate."""
        chunker = MeetingChunker()

        # Test various timestamp conversions
        test_cases = [
            (0.5, "00:00:00"),
            (65.0, "00:01:05"),
            (3661.0, "01:01:01"),
            (7265.5, "02:01:05"),
        ]

        for seconds, expected in test_cases:
            result = chunker._format_timestamp(seconds)
            assert result == expected, f"Expected {expected}, got {result} for {seconds}s"

    def test_chunks_preserve_all_metadata_fields(self, sample_deepgram_response: dict):
        """Test that chunk metadata structure is complete."""
        chunker = MeetingChunker(chunk_size=150, chunk_overlap=30)
        chunks: List[ChunkResult] = chunker.chunk_from_deepgram(sample_deepgram_response)

        expected_fields = ["speaker", "timestamp", "speaker_name"]

        for chunk in chunks:
            for field in expected_fields:
                assert field in chunk.metadata, f"Missing field: {field}"

    def test_empty_utterances_returns_empty_chunks(self):
        """Test that empty utterances list returns empty chunks."""
        chunker = MeetingChunker()

        empty_response = {"results": {"utterances": []}}
        chunks: List[ChunkResult] = chunker.chunk_from_deepgram(empty_response)

        assert len(chunks) == 0

    def test_speaker_metadata_preserved_across_chunk_boundaries(
        self, sample_deepgram_response: dict
    ):
        """Test that speaker changes are preserved when chunks split."""
        # Use small chunk size to force splitting
        chunker = MeetingChunker(chunk_size=80, chunk_overlap=20)
        chunks: List[ChunkResult] = chunker.chunk_from_deepgram(sample_deepgram_response)

        # Verify multiple chunks created
        assert len(chunks) > 1

        # Collect all unique speakers from chunks
        chunk_speakers = set()
        for chunk in chunks:
            speaker_label = chunk.metadata["speaker"]
            chunk_speakers.add(speaker_label)

        # Should have multiple speakers represented
        assert len(chunk_speakers) > 1
