from dataclasses import dataclass
from pathlib import Path


def find_project_root(start: Path | None = None) -> Path:
    """Locate repository assets when run from source or an installed wheel."""

    working_directory = (start or Path.cwd()).resolve()
    source_root = Path(__file__).resolve().parents[2]
    candidates = (working_directory, *working_directory.parents, source_root)
    for candidate in candidates:
        if (candidate / "alembic.ini").is_file() and (candidate / "migrations").is_dir():
            return candidate
    return source_root


PROJECT_ROOT = find_project_root()


@dataclass(frozen=True)
class ProjectPaths:
    root: Path = PROJECT_ROOT

    @property
    def raw(self) -> Path:
        return self.root / "data" / "raw"

    @property
    def processed(self) -> Path:
        return self.root / "data" / "processed"

    @property
    def reports(self) -> Path:
        return self.root / "reports" / "eda"


DEFAULT_UCI_URL = "https://archive.ics.uci.edu/static/public/502/online+retail+ii.zip"
