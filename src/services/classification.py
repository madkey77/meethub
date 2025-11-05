"""Classification service for organizing meetings into project folders based on rules."""

import json
import re
from pathlib import Path
from typing import Any

from src.utils.exceptions import ClassificationError, ConfigurationError
from src.utils.logging import get_logger
from src.utils.validators import validate_project_name

logger = get_logger(__name__)


class ClassificationService:
    """Service for classifying meetings into projects based on rules."""

    def __init__(self, rules_file: Path | str | None = None) -> None:
        """Initialize classification service.

        Args:
            rules_file: Path to classification rules JSON file (default: classification_rules.json)
        """
        self.rules_file = Path(rules_file) if rules_file else Path("classification_rules.json")
        self.rules: list[dict[str, Any]] = []
        self.default_project: str = "GERAL"
        self._load_rules()

    def _load_rules(self) -> None:
        """Load classification rules from JSON file.

        Raises:
            ConfigurationError: If rules file cannot be loaded or is invalid
        """
        if not self.rules_file.exists():
            logger.warning(
                "Classification rules file not found, using default project only",
                rules_file=str(self.rules_file),
            )
            self.rules = []
            return

        try:
            with open(self.rules_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            self.rules = data.get("rules", [])
            self.default_project = data.get("default", "GERAL")

            # Validate rules
            for i, rule in enumerate(self.rules):
                if "project" not in rule:
                    raise ConfigurationError(
                        f"Rule {i} missing 'project' field",
                        details={"rule_index": i, "rule": rule},
                    )
                if "type" not in rule:
                    raise ConfigurationError(
                        f"Rule {i} missing 'type' field",
                        details={"rule_index": i, "rule": rule},
                    )
                if "pattern" not in rule:
                    raise ConfigurationError(
                        f"Rule {i} missing 'pattern' field",
                        details={"rule_index": i, "rule": rule},
                    )

                # Validate project name
                validate_project_name(rule["project"])

            logger.info(
                "Classification rules loaded",
                rules_count=len(self.rules),
                default_project=self.default_project,
                rules_file=str(self.rules_file),
            )

        except json.JSONDecodeError as e:
            raise ConfigurationError(
                f"Invalid JSON in rules file: {e}",
                details={"rules_file": str(self.rules_file)},
            ) from e
        except Exception as e:
            raise ConfigurationError(
                f"Failed to load classification rules: {e}",
                details={"rules_file": str(self.rules_file)},
            ) from e

    def classify_meeting(
        self,
        meeting_title: str,
        participant_emails: list[str] | None = None,
    ) -> str:
        """Classify meeting into a project based on rules.

        Rules are evaluated in order. First matching rule wins.

        Args:
            meeting_title: Meeting title
            participant_emails: List of participant email addresses (optional)

        Returns:
            Project name

        Raises:
            ClassificationError: If classification fails
        """
        participant_emails = participant_emails or []

        logger.debug(
            "Classifying meeting",
            meeting_title=meeting_title,
            participant_count=len(participant_emails),
        )

        try:
            for rule in self.rules:
                rule_type = rule["type"]
                pattern = rule["pattern"]
                project = rule["project"]

                # Match based on rule type
                if rule_type == "title_prefix":
                    if self._match_title_prefix(meeting_title, pattern):
                        logger.info(
                            "Meeting classified by title prefix",
                            project=project,
                            pattern=pattern,
                            meeting_title=meeting_title,
                        )
                        return project

                elif rule_type == "participant_domain":
                    if self._match_participant_domain(participant_emails, pattern):
                        logger.info(
                            "Meeting classified by participant domain",
                            project=project,
                            pattern=pattern,
                            participant_count=len(participant_emails),
                        )
                        return project

                elif rule_type == "keyword":
                    if self._match_keyword(meeting_title, pattern):
                        logger.info(
                            "Meeting classified by keyword",
                            project=project,
                            pattern=pattern,
                            meeting_title=meeting_title,
                        )
                        return project

                else:
                    logger.warning(
                        "Unknown rule type, skipping",
                        rule_type=rule_type,
                        rule=rule,
                    )

            # No rule matched, use default project
            logger.info(
                "No classification rule matched, using default project",
                default_project=self.default_project,
                meeting_title=meeting_title,
            )
            return self.default_project

        except Exception as e:
            raise ClassificationError(
                f"Failed to classify meeting: {e}",
                details={"meeting_title": meeting_title},
            ) from e

    def _match_title_prefix(self, title: str, prefix: str) -> bool:
        """Check if title starts with prefix (case-insensitive).

        Args:
            title: Meeting title
            prefix: Prefix pattern (e.g., "[VNO]")

        Returns:
            True if title starts with prefix
        """
        return title.lower().startswith(prefix.lower())

    def _match_participant_domain(self, emails: list[str], domain: str) -> bool:
        """Check if any participant has email with given domain.

        Args:
            emails: List of participant emails
            domain: Domain pattern (e.g., "@cliente.com")

        Returns:
            True if any email matches domain
        """
        domain_lower = domain.lower()
        return any(email.lower().endswith(domain_lower) for email in emails)

    def _match_keyword(self, title: str, keyword_pattern: str) -> bool:
        """Check if title contains keyword(s) using regex.

        Args:
            title: Meeting title
            keyword_pattern: Keyword regex pattern (e.g., "kickoff|onboarding")

        Returns:
            True if pattern matches (case-insensitive)
        """
        try:
            return bool(re.search(keyword_pattern, title, re.IGNORECASE))
        except re.error as e:
            logger.warning(
                "Invalid regex pattern in keyword rule",
                pattern=keyword_pattern,
                error=str(e),
            )
            return False

    def get_project_folder_mapping(
        self,
        folder_mapping_file: Path | str | None = None,
    ) -> dict[str, str]:
        """Load project name to Drive folder ID mapping.

        Args:
            folder_mapping_file: Path to mapping file (default: project_folders.json)

        Returns:
            Dictionary mapping project names to folder IDs

        Raises:
            ConfigurationError: If mapping file cannot be loaded
        """
        mapping_file = (
            Path(folder_mapping_file)
            if folder_mapping_file
            else Path("project_folders.json")
        )

        if not mapping_file.exists():
            logger.warning(
                "Project folder mapping file not found",
                mapping_file=str(mapping_file),
            )
            return {}

        try:
            with open(mapping_file, "r", encoding="utf-8") as f:
                mapping = json.load(f)

            logger.info(
                "Project folder mapping loaded",
                project_count=len(mapping),
                mapping_file=str(mapping_file),
            )
            return mapping

        except json.JSONDecodeError as e:
            raise ConfigurationError(
                f"Invalid JSON in folder mapping file: {e}",
                details={"mapping_file": str(mapping_file)},
            ) from e
        except Exception as e:
            raise ConfigurationError(
                f"Failed to load project folder mapping: {e}",
                details={"mapping_file": str(mapping_file)},
            ) from e
