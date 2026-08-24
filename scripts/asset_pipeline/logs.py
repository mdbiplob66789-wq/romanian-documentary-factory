"""projects/<id>/logs/<stage>.log — простые понятные логи по этапам (п.41 ТЗ)."""

import sys
from datetime import datetime, timezone
from pathlib import Path


class StageLogger:
    def __init__(self, project, stage: str):
        project.logs_dir.mkdir(parents=True, exist_ok=True)
        self.path = project.logs_dir / f"{stage}.log"
        self._fh = open(self.path, "a", encoding="utf-8")

    def _ts(self) -> str:
        return datetime.now(timezone.utc).isoformat(timespec="seconds")

    def log(self, message: str):
        line = f"[{self._ts()}] {message}"
        print(line)
        self._fh.write(line + "\n")
        self._fh.flush()

    def error(self, message: str):
        line = f"[{self._ts()}] ERROR: {message}"
        print(line, file=sys.stderr)
        self._fh.write(line + "\n")
        self._fh.flush()

    def close(self):
        self._fh.close()
