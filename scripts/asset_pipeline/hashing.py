"""
Хэши входов для resume/idempotency (п.38-40 ТЗ).

Если voiceover изменился -> alignment невалиден.
Если shot-картинка изменилась -> visual render невалиден.
Если music_map/music изменились -> audio master невалиден.

Ничего не решает само — просто даёт "что изменилось", решения принимают
вызывающие скрипты (align_shots.py, render_video.py, build_audio.py).
"""

import hashlib
import json
from pathlib import Path


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_files_combined(paths: list) -> str:
    """Один хэш по списку файлов (сортированному) — для «все шоты» / «вся музыка»."""
    h = hashlib.sha256()
    for p in sorted(paths, key=lambda x: str(x)):
        h.update(str(Path(p).name).encode("utf-8"))
        h.update(sha256_file(p).encode("utf-8"))
    return h.hexdigest()


def load_hashes(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def save_hashes(path: Path, hashes: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(hashes, ensure_ascii=False, indent=2), encoding="utf-8")


def compute_project_hashes(project) -> dict:
    """Снимок хэшей всех входов проекта на текущий момент."""
    result = {}

    if project.voiceover_path.exists():
        result["voiceover"] = sha256_file(project.voiceover_path)
    if project.map_path.exists():
        result["map"] = sha256_file(project.map_path)
    if project.music_map_path.exists():
        result["music_map"] = sha256_file(project.music_map_path)

    if project.shots_dir.is_dir():
        shot_files = list(project.shots_dir.glob(f"{project.id}_shot_*.*"))
        if shot_files:
            result["shots"] = sha256_files_combined(shot_files)

    if project.music_dir.is_dir():
        music_files = [p for p in project.music_dir.iterdir() if p.is_file() and not p.name.startswith(".")]
        if music_files:
            result["music"] = sha256_files_combined(music_files)

    return result


def diff_hashes(old: dict, new: dict) -> list:
    """Какие категории (voiceover/map/music_map/shots/music) реально изменились."""
    keys = set(old) | set(new)
    return sorted(k for k in keys if old.get(k) != new.get(k))
