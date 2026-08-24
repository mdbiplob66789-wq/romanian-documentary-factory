"""
Конфиг проекта: projects/<id>/project.json

Naming standard (video_002 и все последующие проекты; video_001 — legacy, вне projects/):
    shot:      {project_id}_shot_{number:03d}.{ext}
    reference: {project_id}_ref_{category}_{name}.{ext}

Local-first pipeline (video_002+): Python + ffmpeg + faster-whisper. Никакого
Remotion/Node — visual render делает ffmpeg через render_video.py. video_001
(Remotion) остаётся legacy, не трогается.
"""

import json
from dataclasses import dataclass
from pathlib import Path

from .repo import PROJECTS_DIR

REFERENCE_CATEGORIES = ("character", "environment", "props", "style", "other")

DEFAULT_PROJECT_CONFIG = {
    "language": "ro",
    "shots_dir": "shots",
    "references_dir": "references",
    "music_dir": "music",
    "voiceover": "voiceover.mp3",
    "map": "map.json",
    "music_map": "music_map.json",
}

# Утверждённые правила музыки (п.12 ТЗ) — фиксированные, не читаются из music_map,
# чтобы их нельзя было случайно переопределить неверным значением в конкретном проекте.
VOICE_TARGET_LUFS = -14.0
MUSIC_BELOW_VOICE_DB = -20.0
DUCKING_ENABLED = False
DEFAULT_CROSSFADE_SEC = 60.0
INTRO_FADE_SEC = 6.0
OUTRO_FADE_SEC = 10.0

# Approved motion amplitudes (п.8 ТЗ) — должны совпадать 1:1 со значениями в src/Root.jsx.
MOTION_AMPLITUDE = {"low": 0.04, "medium": 0.07}
MOTION_AMPLITUDE_HARD_CAP = 0.08


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

    @property
    def map_path(self) -> Path:
        return self.root / self.config.get("map", DEFAULT_PROJECT_CONFIG["map"])

    @property
    def music_map_path(self) -> Path:
        return self.root / self.config.get("music_map", DEFAULT_PROJECT_CONFIG["music_map"])

    @property
    def voiceover_path(self) -> Path:
        return self.root / self.config.get("voiceover", DEFAULT_PROJECT_CONFIG["voiceover"])

    # --- новые рабочие директории (local-first pipeline, п.4 ТЗ) ---
    @property
    def work_dir(self) -> Path:
        return self.root / "work"

    @property
    def qc_dir(self) -> Path:
        return self.root / "qc"

    @property
    def output_dir(self) -> Path:
        return self.root / "output"

    @property
    def logs_dir(self) -> Path:
        return self.root / "logs"

    @property
    def aligned_timeline_path(self) -> Path:
        return self.work_dir / "aligned_timeline.json"

    @property
    def alignment_report_path(self) -> Path:
        return self.work_dir / "alignment_report.json"

    @property
    def state_hashes_path(self) -> Path:
        """Хэши voiceover/map/music_map/shots/music — для resume/idempotency (п.39 ТЗ)."""
        return self.work_dir / "state_hashes.json"

    @property
    def generation_state_path(self) -> Path:
        """Прогресс генерации картинок по shot — для --resume (п.6, п.40 ТЗ)."""
        return self.work_dir / "generation_state.json"

    @property
    def language(self) -> str:
        return self.config.get("language", DEFAULT_PROJECT_CONFIG["language"])

    @property
    def output_name(self) -> str:
        return self.config.get("output_name", f"{self.id}_FINAL_YOUTUBE.mp4")

    @property
    def final_master_path(self) -> Path:
        return self.output_dir / self.output_name

    @property
    def visual_master_name(self) -> str:
        return f"{self.id}_visual_master.mp4"

    @property
    def visual_master_path(self) -> Path:
        return self.work_dir / self.visual_master_name

    def ensure_work_dirs(self) -> None:
        for d in (self.work_dir, self.qc_dir, self.output_dir, self.logs_dir):
            d.mkdir(parents=True, exist_ok=True)


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
