#!/usr/bin/env python3
"""
scripts/new_project.py video_003 — создаёт новый изолированный проект.

projects/video_003/
  project.json
  map.json            (пустой placeholder — НЕ anchors другого проекта)
  music_map.json       (пустой placeholder)
  upload_state.json
  shots/
  references/{character,environment,props,style,other}/
  music/
"""

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from asset_pipeline.project import DEFAULT_PROJECT_CONFIG, REFERENCE_CATEGORIES
from asset_pipeline.repo import PROJECTS_DIR

PROJECT_ID_RE = re.compile(r"^[a-zA-Z0-9_]+$")


def main():
    p = argparse.ArgumentParser(description="Создать новый проект.")
    p.add_argument("project_id", help="Например: video_003")
    args = p.parse_args()

    project_id = args.project_id
    if not PROJECT_ID_RE.match(project_id):
        print(f"ОШИБКА: небезопасный project_id '{project_id}' — только латиница/цифры/underscore.", file=sys.stderr)
        sys.exit(1)

    root = PROJECTS_DIR / project_id
    if root.exists():
        print(f"ОШИБКА: проект '{project_id}' уже существует ({root}). Ничего не трогаю.", file=sys.stderr)
        sys.exit(1)

    # git не отслеживает пустые папки — кладём .gitkeep, чтобы скелет проекта
    # был виден и коммитился сразу, а не только после первого реального файла.
    (root / "shots").mkdir(parents=True)
    (root / "shots" / ".gitkeep").touch()
    for category in REFERENCE_CATEGORIES:
        cat_dir = root / "references" / category
        cat_dir.mkdir(parents=True)
        (cat_dir / ".gitkeep").touch()
    (root / "music").mkdir(parents=True)
    (root / "music" / ".gitkeep").touch()

    project_json = {
        "id": project_id,
        "status": "draft",
        **DEFAULT_PROJECT_CONFIG,
        "output_name": f"{project_id}_FINAL_YOUTUBE.mp4",
    }
    (root / "project.json").write_text(
        json.dumps(project_json, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (root / "upload_state.json").write_text("[]\n", encoding="utf-8")

    # Пустые placeholder'ы — НЕ копия anchors/narration map другого проекта (п.29 ТЗ).
    map_placeholder = {"shots": []}
    (root / "map.json").write_text(json.dumps(map_placeholder, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    music_map_placeholder = {
        "version": "music_map/v1",
        "crossfade_sec": 60,
        "intro_fade_sec": 6,
        "outro_fade_sec": 10,
        "blocks": [],
    }
    (root / "music_map.json").write_text(
        json.dumps(music_map_placeholder, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    print(f"Проект '{project_id}' создан: {root}")
    print("Структура:")
    for line in sorted(str(p.relative_to(root)) for p in root.rglob("*")):
        print(f"  {line}")
    print()
    print("Не забудьте закоммитить скелет проекта в git отдельно, если нужно, например:")
    print(f"  git add projects/{project_id}/project.json projects/{project_id}/upload_state.json")
    print(f"  git commit -m \"Init project {project_id}\"")
    print("  git push origin main")


if __name__ == "__main__":
    main()
