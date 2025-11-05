"""Unit tests for ClassificationService."""

import json
import pytest
import tempfile
from pathlib import Path

from src.services.classification import ClassificationService
from src.utils.exceptions import ClassificationError, ConfigurationError


class TestClassificationService:
    """Unit tests for meeting classification logic."""

    @pytest.fixture
    def sample_rules_file(self):
        """Create a temporary rules file for testing."""
        rules = {
            "rules": [
                {
                    "project": "VNO",
                    "type": "title_prefix",
                    "pattern": "[VNO]",
                },
                {
                    "project": "CLIENTE_X",
                    "type": "participant_domain",
                    "pattern": "@cliente.com",
                },
                {
                    "project": "NOVOS_CLIENTES",
                    "type": "keyword",
                    "pattern": "kickoff|onboarding",
                },
            ],
            "default": "GERAL",
        }

        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".json") as f:
            json.dump(rules, f)
            temp_file = Path(f.name)

        yield temp_file

        # Cleanup
        temp_file.unlink()

    def test_classification_by_title_prefix(self, sample_rules_file):
        """Test classification by title prefix."""
        service = ClassificationService(rules_file=sample_rules_file)

        project = service.classify_meeting("[VNO] Weekly Standup")
        assert project == "VNO"

    def test_classification_by_participant_domain(self, sample_rules_file):
        """Test classification by participant email domain."""
        service = ClassificationService(rules_file=sample_rules_file)

        project = service.classify_meeting(
            meeting_title="Project Review",
            participant_emails=["user@cliente.com", "another@example.com"],
        )
        assert project == "CLIENTE_X"

    def test_classification_by_keyword(self, sample_rules_file):
        """Test classification by keyword in title."""
        service = ClassificationService(rules_file=sample_rules_file)

        project = service.classify_meeting("Client Onboarding Session")
        assert project == "NOVOS_CLIENTES"

        project = service.classify_meeting("Project Kickoff Meeting")
        assert project == "NOVOS_CLIENTES"

    def test_classification_default_fallback(self, sample_rules_file):
        """Test default project when no rules match."""
        service = ClassificationService(rules_file=sample_rules_file)

        project = service.classify_meeting(
            meeting_title="Random Meeting",
            participant_emails=["user@example.com"],
        )
        assert project == "GERAL"

    def test_classification_first_match_wins(self, sample_rules_file):
        """Test that first matching rule takes precedence."""
        service = ClassificationService(rules_file=sample_rules_file)

        # Title has both [VNO] prefix and "kickoff" keyword
        # Should match VNO (first rule)
        project = service.classify_meeting("[VNO] Kickoff Meeting")
        assert project == "VNO"

    def test_classification_case_insensitive(self, sample_rules_file):
        """Test that classification is case-insensitive."""
        service = ClassificationService(rules_file=sample_rules_file)

        # Lowercase prefix
        project = service.classify_meeting("[vno] weekly standup")
        assert project == "VNO"

        # Uppercase keyword
        project = service.classify_meeting("CLIENT ONBOARDING")
        assert project == "NOVOS_CLIENTES"

    def test_missing_rules_file(self):
        """Test handling of missing rules file."""
        service = ClassificationService(rules_file="nonexistent.json")

        # Should use default project for all meetings
        project = service.classify_meeting("Any Meeting")
        assert project == "GERAL"

    def test_invalid_json_in_rules_file(self):
        """Test error handling for invalid JSON."""
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".json") as f:
            f.write("{ invalid json")
            temp_file = Path(f.name)

        try:
            with pytest.raises(ConfigurationError) as exc_info:
                ClassificationService(rules_file=temp_file)

            assert "Invalid JSON" in str(exc_info.value)
        finally:
            temp_file.unlink()

    def test_invalid_rule_missing_fields(self):
        """Test validation of rule structure."""
        rules = {
            "rules": [
                {
                    "project": "TEST",
                    # Missing 'type' and 'pattern'
                }
            ],
            "default": "GERAL",
        }

        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".json") as f:
            json.dump(rules, f)
            temp_file = Path(f.name)

        try:
            with pytest.raises(ConfigurationError) as exc_info:
                ClassificationService(rules_file=temp_file)

            assert "missing 'type' field" in str(exc_info.value)
        finally:
            temp_file.unlink()

    def test_get_project_folder_mapping(self):
        """Test loading project folder mapping."""
        mapping = {
            "VNO": "folder_id_1",
            "CLIENTE_X": "folder_id_2",
            "GERAL": "folder_id_3",
        }

        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".json") as f:
            json.dump(mapping, f)
            temp_file = Path(f.name)

        try:
            service = ClassificationService()
            result = service.get_project_folder_mapping(folder_mapping_file=temp_file)

            assert result == mapping
        finally:
            temp_file.unlink()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
