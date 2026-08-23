"""
Валидация шотов проекта ДО alignment (п.5 ТЗ).
Строго project_id-scoped: video_002_shot_* никогда не видит video_003_shot_* и наоборот
(гарантируется regex'ом в numbering.py, построенным из project_id).
"""

from pathlib import Path

from . import imageops, numbering


class ShotValidationError(RuntimeError):
    pass


def validate_shots(project, expected_count: int) -> dict:
    """
    Проверяет, что у project есть РОВНО shot 1..expected_count, без пропусков,
    без дублей (два разных расширения на один номер) и без битых файлов.
    Возвращает манифест {shot_number: relative_filename_in_shots_dir}.
    Кидает ShotValidationError с понятным текстом при любом нарушении.
    """
    shots_dir = project.shots_dir
    project_id = project.id

    numbers = numbering.scan_shot_numbers(shots_dir, project_id)

    # Дубли: два файла с разными расширениями на один и тот же номер.
    pattern = numbering.shot_regex(project_id)
    by_number = {}
    duplicates = []
    for entry in shots_dir.iterdir() if shots_dir.is_dir() else []:
        m = pattern.match(entry.name)
        if not m:
            continue
        n = int(m.group(1))
        by_number.setdefault(n, []).append(entry)
    for n, files in by_number.items():
        if len(files) > 1:
            duplicates.append((n, sorted(f.name for f in files)))
    if duplicates:
        details = "; ".join(f"{numbering.shot_filename(project_id, n).rsplit('.',1)[0]}: {names}" for n, names in duplicates)
        raise ShotValidationError(f"Duplicate shot files: {details}")

    expected = set(range(1, expected_count + 1))
    missing = sorted(expected - set(numbers))
    if missing:
        first = numbering.shot_filename(project_id, missing[0]).rsplit(".", 1)[0]
        raise ShotValidationError(
            f"Missing {first}\n"
            f"Не хватает {len(missing)} из {expected_count} шотов: "
            + ", ".join(numbering.shot_filename(project_id, n).rsplit(".", 1)[0] for n in missing)
        )

    extra = sorted(set(numbers) - expected)
    if extra:
        raise ShotValidationError(
            f"Лишние шоты за пределами map.json (ожидалось {expected_count}): "
            + ", ".join(numbering.shot_filename(project_id, n).rsplit(".", 1)[0] for n in extra)
        )

    manifest = {}
    corrupted = []
    for n in sorted(expected):
        path = by_number[n][0]
        try:
            imageops.validate_image(path)
        except imageops.ImageValidationError as e:
            corrupted.append(str(e))
            continue
        manifest[n] = path.name

    if corrupted:
        raise ShotValidationError("Corrupted shot image(s):\n" + "\n".join(corrupted))

    return manifest
