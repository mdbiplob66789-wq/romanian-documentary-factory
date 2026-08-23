"""Определение корня репозитория — всё в системе работает от него, без абсолютных путей."""

from pathlib import Path


class NotARepoError(RuntimeError):
    pass


def find_repo_root(start: Path | None = None) -> Path:
    """Ищет корень git-репозитория, поднимаясь от start (по умолчанию — от этого файла)."""
    here = (start or Path(__file__).resolve()).parent
    for candidate in [here, *here.parents]:
        if (candidate / ".git").exists():
            return candidate
    raise NotARepoError(
        "Не найден корень git-репозитория (папка .git). "
        "Запускайте скрипт изнутри клона romanian-documentary-factory."
    )


REPO_ROOT = find_repo_root()
PROJECTS_DIR = REPO_ROOT / "projects"
