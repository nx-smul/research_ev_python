"""Shared I/O helpers for research extension modules."""

from pathlib import Path

import pandas as pd


def write_csv(frame: pd.DataFrame, path: Path) -> Path:
    """Write DataFrame to CSV, creating parent directories as needed."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False)
    return path
