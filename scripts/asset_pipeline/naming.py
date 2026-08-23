"""Валидация безопасных имён для references — латиница/цифры/underscore, без UUID-мусора."""

import re

SAFE_NAME_RE = re.compile(r"^[a-zA-Z0-9_]+$")


class UnsafeNameError(ValueError):
    pass


def validate_safe_name(name: str) -> str:
    """Возвращает имя как есть, если оно безопасно, иначе кидает понятную ошибку."""
    if not name:
        raise UnsafeNameError("Имя reference не может быть пустым.")
    if not SAFE_NAME_RE.match(name):
        raise UnsafeNameError(
            f"Небезопасное имя reference: '{name}'. "
            "Разрешены только латиница, цифры и подчёркивание (a-z, A-Z, 0-9, _). "
            "Пробелы, дефисы, точки, юникод и случайные UUID не допускаются."
        )
    return name


def safe_stem_from_filename(filename: str) -> str:
    """Для watch-режима: превращает имя входящего файла в кандидата на --name (без валидации)."""
    stem = filename.rsplit(".", 1)[0]
    return re.sub(r"[^a-zA-Z0-9_]", "_", stem)


def reference_stem(project_id: str, category: str, name: str) -> str:
    """
    Canonical basename для reference (без расширения):
        {project_id}_ref_{category}_{name}
    Например: video_002_ref_character_main_character
    """
    return f"{project_id}_ref_{category}_{name}"
