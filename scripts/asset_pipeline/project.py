"""
Конфиг проекта: projects/<id>/project.json

Naming standard (video_002 и все последующие проекты; video_001 — legacy, вне projects/):
    shot:      {project_id}_shot_{number:03d}.{ext}
    reference: {project_id}_ref_{category}_{name}.{ext}

Заметка на будущее про Remotion (render.yml сейчас НЕ трогается этим модулем):
render.yml сегодня жёстко ждёт файлы вида shot_XXX.ext в public/shots/ (video_001-стиль,
без префикса project_id). Когда render.yml научится работать по project_id, шаг подготовки
ассетов для Remotion должен будет СНИМАТЬ префикс "{project_id}_" при копировании
в public/shots/, а не менять сам canonical naming в projects/<id>/shots/.
"""

import json
from dataclasses import dataclass
from pathlib import Path

from .repo import PROJECTS_DIR

REFERENCE_CATEGORIES = ("character", "environment", "props", "style", "other")

DEFAULT_PROJECT_CONFIG = {
    "shots_dir": "shots",
    "references_dir": "references",
    "music_dir": "music",
    "voiceover": "voiceover.mp3",
    "map": "map.json",
}


class ProjectError(RuntimeError):
    pass


@dataclass
class Project:
    id: str
    root: Path
    config: dict

    @property
    def shots_dir(self) -> Path:
        return self.root / self.config.get("shots_dir", DEFAULT_PROJECT_CONFIG["shots_dir"])

    @property
    def references_dir(self) -> Path:
        return self.root / self.config.get("references_dir", DEFAULT_PROJECT_CONFIG["references_dir"])

    @property
    def music_dir(self) -> Path:
        return self.root / self.config.get("music_dir", DEFAULT_PROJECT_CONFIG["music_dir"])

    @property
    def upload_state_path(self) -> Path:
        return self.root / "upload_state.json"


def load_project(project_id: str) -> Project:
    """Загружает проект по id. Падает с понятным сообщением, если проекта нет."""
    root = PROJECTS_DIR / project_id
    config_path = root / "project.json"

    if not root.is_dir():
        raise ProjectError(
            f"Проект '{project_id}' не найден: нет папки {root}.\n"
            f"Создайте его через: python scripts/new_project.py {project_id}"
        )
    if not config_path.exists():
        raise ProjectError(
            f"В проекте '{project_id}' нет project.json ({config_path}). "
            "Проект повреждён или создан не через new_project.py."
        )

    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ProjectError(f"project.json проекта '{project_id}' повреждён (невалидный JSON): {e}")

    if config.get("id") != project_id:
        raise ProjectError(
            f"project.json проекта '{project_id}' указывает id={config.get('id')!r} — "
            "несоответствие, проверьте файл вручную."
        )

    return Project(id=project_id, root=root, config=config)


def project_exists(project_id: str) -> bool:
    return (PROJECTS_DIR / project_id / "project.json").exists()
