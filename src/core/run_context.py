"""Run context: encapsulates all state for a single pipeline execution."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
import uuid

from src.core.paths import PathManager


@dataclass
class RunContext:
    """Immutable context for a single pipeline run.

    Attributes:
        run_id: Unique identifier for this run
        base_dir: Project root directory
        paths: PathManager for resolving artifact locations
        started_at: Timestamp when run began
        config: Configuration dict (will become typed Config object later)
        data_mode: "demo" or "real"
    """

    base_dir: Path
    config: dict
    data_mode: str = "demo"
    run_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self):
        if isinstance(self.base_dir, str):
            self.base_dir = Path(self.base_dir)
        self.paths = PathManager(self.base_dir)

    def research_dir(self) -> Path:
        """Get the research output directory for this run."""
        return self.paths.research_dir(self.run_id)

    def report_path(self) -> Path:
        """Get the markdown report path for this run."""
        return self.paths.run_report(self.run_id)
