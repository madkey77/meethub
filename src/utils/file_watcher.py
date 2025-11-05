"""File system watcher for automatic file ingestion.

This module provides a watchdog-based file system monitor that watches ingestion
folders and triggers automatic file processing when new files are detected.

Features:
- Monitors /ingest/{project_id}/ directories
- Triggers ingestion on file creation events
- Debounces rapid file changes (1 second delay)
- Non-blocking operation using threading
- Graceful start/stop with cleanup

Example:
    >>> from src.utils.file_watcher import FileWatcher
    >>> from src.services.file_ingestion import FileIngestionService
    >>>
    >>> # Create callback for file events
    >>> def on_file_created(file_path, project_id):
    ...     print(f"New file: {file_path} in project {project_id}")
    ...     # Trigger ingestion
    ...     service.ingest_file(file_path, project_id)
    >>>
    >>> # Start watcher
    >>> watcher = FileWatcher(watch_path="/mnt/data/ingest")
    >>> watcher.add_handler(on_file_created)
    >>> watcher.start()
    >>>
    >>> # ... files created in /mnt/data/ingest/project-123/ trigger callback ...
    >>>
    >>> # Stop watcher
    >>> watcher.stop()
"""

import re
import threading
import time
from pathlib import Path
from typing import Callable, Dict, Optional

from watchdog.events import FileCreatedEvent, FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from src.utils.logging import get_logger

logger = get_logger(__name__)


class FileWatcher:
    """File system watcher for automatic file ingestion.

    Monitors ingestion directories and triggers callbacks when new files are created.
    Uses watchdog library for cross-platform file system event monitoring.

    Attributes:
        watch_path: Base directory to monitor (e.g., "/mnt/data/ingest")
        debounce_delay: Delay in seconds before triggering callback (default: 1.0)
        observer: Watchdog observer instance
        event_handler: Custom event handler for file events
        is_running: Flag indicating watcher is active
    """

    def __init__(
        self,
        watch_path: str,
        debounce_delay: float = 1.0,
        recursive: bool = True
    ):
        """Initialize file watcher.

        Args:
            watch_path: Base directory path to watch
            debounce_delay: Delay in seconds before triggering callback (default: 1.0)
            recursive: Watch subdirectories recursively (default: True)

        Example:
            >>> watcher = FileWatcher("/mnt/data/ingest", debounce_delay=1.5)
        """
        self.watch_path = Path(watch_path)
        self.debounce_delay = debounce_delay
        self.recursive = recursive

        self.observer: Optional[Observer] = None
        self.event_handler: Optional[IngestionEventHandler] = None
        self.is_running = False

        self._logger = logger.bind(service="file_watcher", watch_path=str(self.watch_path))

        # Create watch directory if it doesn't exist
        if not self.watch_path.exists():
            self.watch_path.mkdir(parents=True, exist_ok=True)
            self._logger.info("file_watcher.created_watch_dir")

    def add_handler(self, callback: Callable[[str, Optional[int]], None]) -> None:
        """Add callback function to handle file creation events.

        The callback function should accept:
        - file_path (str): Absolute path to the created file
        - project_id (int | None): Extracted project ID from path, or None

        Args:
            callback: Function to call when file is created

        Example:
            >>> def handle_file(file_path, project_id):
            ...     print(f"File: {file_path}, Project: {project_id}")
            >>> watcher.add_handler(handle_file)
        """
        if self.event_handler is None:
            self.event_handler = IngestionEventHandler(
                callback=callback,
                debounce_delay=self.debounce_delay
            )
            self._logger.info("file_watcher.handler_added")
        else:
            self._logger.warning("file_watcher.handler_already_exists")

    def start(self) -> None:
        """Start watching for file system events.

        Creates Observer, schedules event handler, and starts monitoring in background thread.

        Raises:
            RuntimeError: If no handler has been added via add_handler()

        Example:
            >>> watcher = FileWatcher("/mnt/data/ingest")
            >>> watcher.add_handler(my_callback)
            >>> watcher.start()
        """
        if self.event_handler is None:
            raise RuntimeError("No event handler added. Call add_handler() first.")

        if self.is_running:
            self._logger.warning("file_watcher.already_running")
            return

        # Create and configure observer
        self.observer = Observer()
        self.observer.schedule(
            self.event_handler,
            str(self.watch_path),
            recursive=self.recursive
        )

        # Start observer in background thread
        self.observer.start()
        self.is_running = True

        self._logger.info(
            "file_watcher.started",
            recursive=self.recursive,
            debounce_delay=self.debounce_delay
        )

    def stop(self) -> None:
        """Stop watching for file system events.

        Gracefully stops the observer thread and cleans up resources.

        Example:
            >>> watcher.stop()
        """
        if not self.is_running or self.observer is None:
            self._logger.warning("file_watcher.not_running")
            return

        # Stop observer
        self.observer.stop()
        self.observer.join(timeout=5.0)

        self.is_running = False
        self._logger.info("file_watcher.stopped")

    def is_active(self) -> bool:
        """Check if watcher is currently running.

        Returns:
            True if watcher is active, False otherwise

        Example:
            >>> if watcher.is_active():
            ...     print("Watcher is monitoring files")
        """
        return self.is_running and self.observer is not None and self.observer.is_alive()


class IngestionEventHandler(FileSystemEventHandler):
    """Event handler for file system events in ingestion directories.

    Handles file creation events with debouncing to avoid duplicate processing
    of rapidly changing files. Extracts project ID from directory structure.

    Expected directory structure: /base/path/{project_name}/file.ext
    where {project_name} can be project ID or project name.
    """

    def __init__(
        self,
        callback: Callable[[str, Optional[int]], None],
        debounce_delay: float = 1.0
    ):
        """Initialize event handler.

        Args:
            callback: Function to call for file creation events
            debounce_delay: Delay in seconds before triggering callback
        """
        super().__init__()
        self.callback = callback
        self.debounce_delay = debounce_delay

        # Track pending events for debouncing
        self._pending_events: Dict[str, threading.Timer] = {}
        self._pending_lock = threading.Lock()

        self._logger = logger.bind(service="ingestion_event_handler")

    def on_created(self, event: FileSystemEvent) -> None:
        """Handle file creation events.

        Args:
            event: File system event from watchdog

        Flow:
            1. Ignore directory creation (only handle files)
            2. Extract file path and project ID
            3. Debounce: cancel existing timer for this file if any
            4. Start new timer to trigger callback after delay
        """
        # Only handle file creation (not directories)
        if event.is_directory:
            return

        # Only handle file created events
        if not isinstance(event, FileCreatedEvent):
            return

        file_path = event.src_path

        # Extract project ID from path
        project_id = self._extract_project_id(file_path)

        self._logger.debug(
            "file_watcher.file_created",
            file_path=file_path,
            project_id=project_id
        )

        # Debounce: cancel existing timer if file already pending
        with self._pending_lock:
            if file_path in self._pending_events:
                self._pending_events[file_path].cancel()
                self._logger.debug("file_watcher.debounce_cancelled", file_path=file_path)

            # Schedule callback after debounce delay
            timer = threading.Timer(
                self.debounce_delay,
                self._trigger_callback,
                args=(file_path, project_id)
            )
            timer.daemon = True
            self._pending_events[file_path] = timer
            timer.start()

    def _trigger_callback(self, file_path: str, project_id: Optional[int]) -> None:
        """Trigger the callback function after debounce delay.

        Args:
            file_path: Absolute path to file
            project_id: Extracted project ID or None
        """
        # Remove from pending events
        with self._pending_lock:
            self._pending_events.pop(file_path, None)

        # Verify file still exists (not deleted during debounce)
        if not Path(file_path).exists():
            self._logger.warning(
                "file_watcher.file_disappeared",
                file_path=file_path
            )
            return

        # Trigger callback
        try:
            self._logger.info(
                "file_watcher.triggering_callback",
                file_path=file_path,
                project_id=project_id
            )
            self.callback(file_path, project_id)

        except Exception as e:
            self._logger.error(
                "file_watcher.callback_error",
                file_path=file_path,
                error=str(e),
                error_type=type(e).__name__
            )

    def _extract_project_id(self, file_path: str) -> Optional[int]:
        """Extract project ID from file path.

        Expected patterns:
        - /base/path/{project_id}/file.ext → returns int(project_id)
        - /base/path/{project_name}/file.ext → returns None (name resolution in caller)
        - /base/path/file.ext → returns None (default project)

        Args:
            file_path: Absolute file path

        Returns:
            Project ID if numeric folder name found, otherwise None

        Example:
            >>> handler._extract_project_id("/ingest/123/doc.pdf")
            123
            >>> handler._extract_project_id("/ingest/project-alpha/doc.pdf")
            None
        """
        path = Path(file_path)

        # Get parent directory name (should be project identifier)
        parent_name = path.parent.name

        # Try to parse as integer (project ID)
        try:
            project_id = int(parent_name)
            return project_id
        except ValueError:
            # Not a numeric ID, could be project name
            # Caller will need to resolve project by name
            return None


# Singleton instance for application-wide file watcher
_global_watcher: Optional[FileWatcher] = None


def get_file_watcher(watch_path: Optional[str] = None) -> FileWatcher:
    """Get or create global file watcher instance.

    This provides a singleton watcher that can be started/stopped by the application.

    Args:
        watch_path: Base directory to watch (only used on first call)

    Returns:
        Global FileWatcher instance

    Example:
        >>> watcher = get_file_watcher("/mnt/data/ingest")
        >>> watcher.add_handler(my_callback)
        >>> watcher.start()
    """
    global _global_watcher

    if _global_watcher is None:
        if watch_path is None:
            raise ValueError("watch_path required for first call to get_file_watcher()")
        _global_watcher = FileWatcher(watch_path)

    return _global_watcher
