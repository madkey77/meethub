"""Transcription service using Deepgram API for audio transcription with speaker diarization."""

import asyncio
from pathlib import Path
from typing import Any

from deepgram import AsyncDeepgramClient, DeepgramClient

from src.config import settings
from src.utils.exceptions import (
    AudioValidationError,
    DeepgramAPIError,
    TranscriptionError,
    TranscriptionTimeoutError,
)
from src.utils.logging import get_logger
from src.utils.retry import retry_with_backoff
from src.utils.validators import validate_audio_file

logger = get_logger(__name__)


class TranscriptionService:
    """Service for transcribing audio using Deepgram API."""

    def __init__(self) -> None:
        """Initialize Deepgram client."""
        # Use AsyncDeepgramClient for async operations in SDK v5
        self.client = AsyncDeepgramClient(api_key=settings.deepgram_api_key)
        logger.info("Deepgram client initialized")

    def validate_audio(self, audio_path: Path | str) -> dict[str, Any]:
        """Validate audio file before transcription.

        Args:
            audio_path: Path to audio file

        Returns:
            Validation results

        Raises:
            AudioValidationError: If audio file is invalid
        """
        return validate_audio_file(audio_path)

    @retry_with_backoff(
        retryable_exceptions=(DeepgramAPIError,),
        max_retries=2,  # Deepgram retries are less aggressive
    )
    async def transcribe(self, audio_path: Path | str) -> dict[str, Any]:
        """Transcribe audio file with speaker diarization.

        Args:
            audio_path: Path to audio file

        Returns:
            Transcription result with speaker segments

        Raises:
            AudioValidationError: If audio file is invalid
            DeepgramAPIError: If transcription fails
            TranscriptionTimeoutError: If transcription times out
        """
        audio_path = Path(audio_path) if isinstance(audio_path, str) else audio_path

        # Validate audio file first
        validation = self.validate_audio(audio_path)
        logger.info(
            "Starting transcription",
            audio_path=str(audio_path),
            size_mb=round(validation["size_bytes"] / (1024 * 1024), 2),
        )

        try:
            # Read audio file
            with open(audio_path, "rb") as audio_file:
                buffer_data = audio_file.read()

            # Transcribe with timeout (SDK v5.x API)
            # In SDK v5, transcribe_file takes bytes as first param and options as kwargs
            try:
                response = await asyncio.wait_for(
                    self.client.listen.v1.media.transcribe_file(
                        request=buffer_data,
                        model=settings.deepgram_model,
                        language=settings.transcription_language,
                        diarize=settings.enable_diarization,
                        punctuate=settings.enable_punctuation,
                        paragraphs=True,
                        smart_format=True,
                        utterances=True,
                    ),
                    timeout=settings.transcription_timeout_seconds,
                )
            except asyncio.TimeoutError:
                raise TranscriptionTimeoutError(
                    f"Transcription timed out after {settings.transcription_timeout_seconds}s",
                    details={"audio_path": str(audio_path)},
                )

            # Parse response
            result = self._parse_deepgram_response(response)

            # Extract cost/usage information from metadata
            duration_seconds = 0
            cost_estimate = 0.0

            # Handle both v3 (object) and v5 (dict) responses
            if isinstance(response, dict):
                # v5.x
                metadata = response.get("metadata", {})
                duration_seconds = metadata.get("duration", 0)
            elif hasattr(response, "metadata") and response.metadata:
                # v3.x
                duration_seconds = getattr(response.metadata, "duration", 0)

            # Deepgram pricing: ~$0.0125 per minute for Nova-2 model
            # This is approximate - actual cost may vary
            cost_estimate = (duration_seconds / 60) * 0.0125 if duration_seconds else 0.0

            logger.info(
                "Transcription completed",
                audio_path=str(audio_path),
                word_count=result["word_count"],
                speaker_count=result["speaker_count"],
                duration_seconds=round(duration_seconds, 2),
                estimated_cost_usd=round(cost_estimate, 4),
                model=settings.deepgram_model,
            )

            return result

        except TranscriptionTimeoutError:
            raise

        except AudioValidationError:
            raise

        except Exception as e:
            raise DeepgramAPIError(
                f"Deepgram transcription failed: {e}",
                details={"audio_path": str(audio_path)},
            ) from e

    def _parse_deepgram_response(self, response: Any) -> dict[str, Any]:
        """Parse Deepgram API response into structured format.

        Args:
            response: Deepgram API response (dict or object)

        Returns:
            Parsed transcription data
        """
        try:
            # Handle both v3 (object) and v5 (dict) responses
            if isinstance(response, dict):
                # v5.x returns dict
                results = response.get("results", {})
                channel = results.get("channels", [{}])[0]
                alternatives = channel.get("alternatives", [{}])[0]
                full_text = alternatives.get("transcript", "")
                utterances_data = alternatives.get("utterances", [])
            else:
                # v3.x returns object
                channel = response.results.channels[0]
                alternatives = channel.alternatives[0]
                full_text = alternatives.transcript
                utterances_data = getattr(alternatives, "utterances", []) if hasattr(alternatives, "utterances") else []

            # Extract utterances with speaker diarization
            utterances = []
            speakers = set()

            if utterances_data:
                for utterance in utterances_data:
                    # Handle both dict and object formats
                    if isinstance(utterance, dict):
                        speaker = utterance.get("speaker", 0)
                        text = utterance.get("transcript", "")
                        start = utterance.get("start", 0)
                        end = utterance.get("end", 0)
                        confidence = utterance.get("confidence", 0.0)
                    else:
                        speaker = getattr(utterance, "speaker", 0)
                        text = getattr(utterance, "transcript", "")
                        start = getattr(utterance, "start", 0)
                        end = getattr(utterance, "end", 0)
                        confidence = getattr(utterance, "confidence", 0.0)

                    speaker_id = f"speaker_{speaker}"
                    speakers.add(speaker_id)

                    utterances.append({
                        "speaker": speaker_id,
                        "text": text,
                        "start": start,
                        "end": end,
                        "confidence": confidence,
                    })

            # Count words (approximate)
            word_count = len(full_text.split()) if full_text else 0

            return {
                "full_text": full_text,
                "utterances": utterances,
                "word_count": word_count,
                "speaker_count": len(speakers),
                "speakers": list(speakers),
            }

        except Exception as e:
            raise TranscriptionError(
                f"Failed to parse Deepgram response: {e}",
                details={},
            ) from e

    def format_as_markdown(
        self,
        transcription_data: dict[str, Any],
        meeting_title: str,
        meeting_date: str,
        duration_minutes: int,
        project_name: str,
        participants: list[str] | None = None,
    ) -> str:
        """Format transcription as markdown document.

        Args:
            transcription_data: Parsed transcription data
            meeting_title: Meeting title
            meeting_date: Meeting date (ISO format)
            duration_minutes: Meeting duration in minutes
            project_name: Project name
            participants: List of participant names (optional)

        Returns:
            Formatted markdown text
        """
        lines = [
            f"# Meeting: {meeting_title}",
            "",
            f"**Date**: {meeting_date}",
            f"**Duration**: {duration_minutes} minutes",
            f"**Project**: {project_name}",
        ]

        if participants:
            lines.append(f"**Participants**: {', '.join(participants)}")

        lines.extend([
            "",
            "## Transcript",
            "",
        ])

        # Format utterances with timestamps and speaker labels
        for utterance in transcription_data.get("utterances", []):
            start_seconds = utterance["start"]
            minutes = int(start_seconds // 60)
            seconds = int(start_seconds % 60)
            timestamp = f"[{minutes:02d}:{seconds:02d}]"

            speaker = utterance["speaker"].replace("speaker_", "Speaker ")
            text = utterance["text"]

            lines.append(f"{timestamp} **{speaker}**: {text}")
            lines.append("")

        # If no utterances, use full text
        if not transcription_data.get("utterances"):
            lines.append(transcription_data.get("full_text", "No transcription available."))
            lines.append("")

        # Add metadata footer
        lines.extend([
            "---",
            "",
            f"*Transcribed with Deepgram AI | {transcription_data['word_count']} words | {transcription_data['speaker_count']} speakers*",
        ])

        markdown_text = "\n".join(lines)

        logger.debug(
            "Formatted transcript as markdown",
            word_count=transcription_data["word_count"],
            speaker_count=transcription_data["speaker_count"],
        )

        return markdown_text

    def cleanup_audio_file(self, audio_path: Path | str) -> None:
        """Delete audio file after successful transcription.

        Args:
            audio_path: Path to audio file
        """
        audio_path = Path(audio_path) if isinstance(audio_path, str) else audio_path

        try:
            if audio_path.exists():
                audio_path.unlink()
                logger.info("Audio file deleted", audio_path=str(audio_path))
        except Exception as e:
            logger.warning(
                "Failed to delete audio file",
                audio_path=str(audio_path),
                error=str(e),
            )
