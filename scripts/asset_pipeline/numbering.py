"""
Нумерация шотов. Единственный источник истины — реальные файлы в projects/<id>/shots/.
upload_state.json НИКОГДА не используется для определения текущего номера (п.13 ТЗ).
"""

import re
from pathlib import Path

SHOT_RE = re.compile(r"^shot_(\d{3})\.(jpg|jpeg|png|webp)$", re.IGNORECASE)


class ShotSequenceError(RuntimeError):
    pass


def scan_shot_numbers(shots_dir: Path) -> list[int]:
    """Реальные номера шотов на диске, отсортированные по возрастанию."""
    if not shots_dir.is_dir():
        return []
    numbers = set()
    for entry in shots_dir.iterdir():
        m = SHOT_RE.match(entry.name)
        if m:
            numbers.add(int(m.group(1)))
    return sorted(numbers)


def find_gaps(numbers: list[int]) -> list[int]:
    """Пропуски в последовательности 1..max(numbers)."""
    if not numbers:
        return []
    full = set(range(1, max(numbers) + 1))
    return sorted(full - set(numbers))


def next_shot_number(shots_dir: Path) -> int:
    """
    Следующий номер для --next.
    Останавливается с ошибкой, если в последовательности есть пропуски —
    система не должна перескакивать через них (п.4 ТЗ).
    """
    numbers = scan_shot_numbers(shots_dir)
    if not numbers:
        return 1

    gaps = find_gaps(numbers)
    if gaps:
        missing_list = ", ".join(f"shot_{n:03d}" for n in gaps)
        raise ShotSequenceError(
            f"Missing {'shot_' + format(gaps[0], '03d') if len(gaps) == 1 else missing_list}\n"
            f"В последовательности есть пропуски: {missing_list}. "
            f"Автонумерация (--next) остановлена, чтобы не создать shot_{max(numbers) + 1:03d} "
            f"поверх дыры. Заполните пропуск явно: --shot {gaps[0]}"
        )

    return max(numbers) + 1


def shot_filename(shot_number: int, ext: str = "jpg") -> str:
    return f"shot_{shot_number:03d}.{ext.lstrip('.')}"


def existing_shot_path(shots_dir: Path, shot_number: int) -> Path | None:
    """Есть ли уже файл с таким номером, в любом поддерживаемом расширении."""
    for ext in ("jpg", "jpeg", "png", "webp"):
        p = shots_dir / shot_filename(shot_number, ext)
        if p.exists():
            return p
    return None
