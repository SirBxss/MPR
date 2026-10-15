"""Disposable two-database staging and cooperative bounded-readiness checks."""

from __future__ import annotations

from contextlib import closing
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import time

from ..domain.recording_ingestion import RecordingIngestionError
from .recording_decode_check import MAX_INDEX_BYTES, _snapshot, failure_code

MAX_SCIENCE_BYTES = 8 * 1024**3
MAX_COMBINED_BYTES = MAX_INDEX_BYTES + MAX_SCIENCE_BYTES
INITIAL_SCRATCH_BYTES = 19_864_223_744
RUNTIME_SCRATCH_BYTES = 10 * 1024**3
PAGE_CACHE_BYTES = 8 * 1024**2
PROCESSING_SECONDS = 1800


def configure(connection, maximum_bytes):
    """Set AND verify the complete no-sidecar disposable DB configuration."""
    settings = {"page_size": 4096, "cache_size": -8192, "journal_mode": "OFF", "synchronous": "OFF", "temp_store": "MEMORY", "mmap_size": 0, "max_page_count": maximum_bytes // 4096}
    for key, value in settings.items():
        connection.execute(f"PRAGMA {key}={value}")
    expected = {"page_size": 4096, "cache_size": -8192, "journal_mode": "off", "synchronous": 0, "temp_store": 2, "mmap_size": 0, "max_page_count": maximum_bytes // 4096}
    for key, value in expected.items():
        row = connection.execute("PRAGMA "+key).fetchone()
        if row is None or row[0] != value:
            raise RecordingIngestionError("readiness_sqlite_configuration_unsupported")


def check_configuration(scratch):
    """Dependency preflight happens before any raw hash or result directory."""
    try:
        with TemporaryDirectory(prefix="mpr-readiness-sqlite-check-", dir=scratch) as temp:
            for name, limit in (("index.sqlite", MAX_INDEX_BYTES), ("science.sqlite", MAX_SCIENCE_BYTES)):
                with closing(sqlite3.connect(Path(temp)/name)) as connection:
                    configure(connection, limit)
    except sqlite3.Error as error:
        raise RecordingIngestionError("readiness_sqlite_configuration_unsupported") from error


class Observations:
    def __init__(self):
        self.elapsed = dict.fromkeys(("raw_hash", "fresh_summary", "descriptor_binding", "selected_decode", "scientific_finalize"))
        self.current = None
        self.started = None
        self.peak = None

    def phase(self, name):
        now = time.monotonic()
        if self.current is not None:
            self.elapsed[self.current] = max(0., now-self.started)
        self.current, self.started = name, now
        self.sample()

    def sample(self):
        rss = _snapshot()["process_resident_memory_bytes"]
        if rss is not None:
            self.peak = rss if self.peak is None else max(self.peak, rss)

    def summary(self):
        self.phase(None)
        return {"elapsed_seconds": self.elapsed.copy(), "peak_resident_memory_bytes": self.peak}


class Workspace:
    """Own only the temporary recording directory, never source/report paths."""
    def __init__(self, scratch, resource_check, observations, deadline):
        self.scratch, self.resource_check = scratch, resource_check
        self.observations, self.deadline = observations, deadline
        self.temporary = None
        self.connections = []
        self.unexpected_scratch_names = []

    def __enter__(self):
        self.temporary = TemporaryDirectory(prefix="mpr-bounded-readiness-", dir=self.scratch)
        self.directory = Path(self.temporary.name)
        try:
            self.index = self._connect("index.sqlite", MAX_INDEX_BYTES)
            self.science = self._connect("science.sqlite", MAX_SCIENCE_BYTES)
            self.checkpoint()
            return self
        except BaseException:
            self.__exit__(None, None, None)
            raise

    def _connect(self, name, maximum):
        connection = sqlite3.connect(self.directory/name)
        self.connections.append(connection)
        configure(connection, maximum)
        return connection

    def checkpoint(self):
        self.observations.sample()
        if time.monotonic() > self.deadline:
            raise RecordingIngestionError("readiness_processing_time_limit")
        self.resource_check()
        total = 0
        unexpected = False
        for path in self.directory.iterdir():
            state = path.lstat()
            allocation = max(state.st_size, state.st_blocks*512)
            total += allocation
            if path.name not in ("index.sqlite", "science.sqlite") or path.is_symlink() or not path.is_file():
                unexpected = True
                self.unexpected_scratch_names.append(path.name)
            elif allocation > (MAX_INDEX_BYTES if path.name == "index.sqlite" else MAX_SCIENCE_BYTES):
                raise RecordingIngestionError("readiness_database_limit")
        if unexpected:
            raise RecordingIngestionError("readiness_unexpected_scratch_file")
        if total > MAX_COMBINED_BYTES:
            raise RecordingIngestionError("readiness_database_limit")

    def __exit__(self, *_):
        for connection in reversed(self.connections):
            connection.close()
        if self.temporary is not None:
            self.temporary.cleanup()


def scientific_failure(error):
    if isinstance(error, sqlite3.Error):
        message = str(error).lower()  # Internal classification; never publish it.
        if "memory" in message:
            return "memory_limit"
        if "full" in message:
            return "readiness_database_limit"
    code = failure_code(error)
    return "readiness_processing_time_limit" if code == "decode_execution_timeout" else code
