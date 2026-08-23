"""
Git-операции: pull --rebase, add конкретного файла, commit, push.
При сбое push — файл и коммит остаются на месте (п.11 ТЗ), можно повторить push отдельно.
"""

import subprocess
from pathlib import Path


class GitError(RuntimeError):
    pass


def _run(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
    )


def pull_rebase(repo_root: Path) -> None:
    result = _run(["pull", "--rebase", "origin", "main"], repo_root)
    if result.returncode != 0:
        raise GitError(
            "git pull --rebase не прошёл — возможен конфликт или нет сети.\n"
            f"{result.stderr.strip()}\n"
            "Разрешите конфликт вручную (git status / git rebase --abort) и повторите."
        )


def add_file(repo_root: Path, relative_path: str) -> None:
    result = _run(["add", relative_path], repo_root)
    if result.returncode != 0:
        raise GitError(f"git add не прошёл для {relative_path}: {result.stderr.strip()}")


def commit(repo_root: Path, message: str) -> str:
    """Возвращает short-хэш коммита."""
    result = _run(["commit", "-m", message], repo_root)
    if result.returncode != 0:
        raise GitError(f"git commit не прошёл: {result.stderr.strip() or result.stdout.strip()}")

    rev = _run(["rev-parse", "--short", "HEAD"], repo_root)
    return rev.stdout.strip() if rev.returncode == 0 else "unknown"


def push(repo_root: Path) -> tuple[bool, str]:
    """Возвращает (успех, сообщение)."""
    result = _run(["push", "origin", "main"], repo_root)
    if result.returncode == 0:
        return True, "ok"
    return False, result.stderr.strip()
