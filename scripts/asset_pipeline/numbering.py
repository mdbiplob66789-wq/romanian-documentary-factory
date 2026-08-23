"""
Нумерация шотов. Единственный источник истины — реальные файлы в projects/<id>/shots/.
upload_state.json НИКОГДА не используется для определения текущего номера (п.13 ТЗ).

Canonical filename (обязателен для video_002 и всех последующих проектов):
    {project_id}_shot_{number:03d}.{ext}

Изоляция усилена на уровне имени файла, не только пути: regex строится
из конкретного project_id, поэтому файл без префикса нужного проекта
(например, чужой shot_005.jpg или video_003_shot_005.jpg внутри video_002/shots/)
просто не матчится и полностью игнорируется нумерацией — как будто его нет.

video_001 (legacy, лежит вне projects/) этим модулем не затрагивается вообще.
"""

import re
from pathlib import Path

SHOT_EXTENSIONS = ("jpg", "jpeg", "png", "webp")


class ShotSequenceError(RuntimeError):
    pass


def _shot_re(project_id: str) -> re.Pattern:
    """Regex, матчащий ТОЛЬКО канонические имена шотов данного project_id."""
    return re.compile(
        rf"^{re.escape(project_id)}_shot_(\d{{3}})\.(jpg|jpeg|png|webp)$",
        re.IGNORECASE,
    )


def scan_shot_numbers(shots_dir: Path, project_id: str) -> list[int]:
    """Реальные номера шотов ЭТОГО project_id на диске, отсортированные по возрастанию."""
    if not shots_dir.is_dir():
        return []
    pattern = _shot_re(project_id)
    numbers = set()
    for entry in shots_dir.iterdir():
        m = pattern.match(entry.name)
        if m:
            numbers.add(int(m.group(1)))
    return sorted(numbers)


def find_gaps(numbers: list[int]) -> list[int]:
    """Пропуски в последовательности 1..max(numbers)."""
    if not numbers:
        return []
    full = set(range(1, max(numbers) + 1))
    return sorted(full - set(numbers))


def next_shot_number(shots_dir: Path, project_id: str) -> int:
    """
    Следующий номер для --next, СТРОГО в рамках project_id.
    Останавливается с ошибкой, если в последовательности есть пропуски —
    система не должна перескакивать через них (п.4 ТЗ).
    """
    numbers = scan_shot_numbers(shots_dir, project_id)
    if not numbers:
        return 1

    gaps = find_gaps(numbers)
    if gaps:
        missing_list = ", ".join(shot_filename(project_id, n).rsplit(".", 1)[0] for n in gaps)
        first_missing = shot_filename(project_id, gaps[0]).rsplit(".", 1)[0]
        next_would_be = shot_filename(project_id, max(numbers) + 1).rsplit(".", 1)[0]
        raise ShotSequenceError(
            f"Missing {first_missing}\n"
            f"В последовательности {project_id} есть пропуски: {missing_list}. "
            f"Автонумерация (--next) остановлена, чтобы не создать {next_would_be} "
            f"поверх дыры. Заполните пропуск явно: --shot {gaps[0]}"
        )

    return max(numbers) + 1


def shot_filename(project_id: str, shot_number: int, ext: str = "jpg") -> str:
    """Canonical filename: {project_id}_shot_{number:03d}.{ext}"""
    return f"{project_id}_shot_{shot_number:03d}.{ext.lstrip('.')}"


def existing_shot_path(shots_dir: Path, project_id: str, shot_number: int) -> Path | None:
    """Есть ли уже файл с таким номером у этого project_id, в любом поддерживаемом расширении."""
    for ext in SHOT_EXTENSIONS:
        p = shots_dir / shot_filename(project_id, shot_number, ext)
        if p.exists():
            return p
    return None
