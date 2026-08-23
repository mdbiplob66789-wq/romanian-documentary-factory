#!/usr/bin/env python3
"""
scripts/stage_remotion.py --project video_002

Временно копирует ассеты проекта в public/ для Remotion, СНИМАЯ project_id-префикс
ТОЛЬКО в staging-копии (п.6 ТЗ) — canonical-имена в projects/<id>/shots/ не трогаются:

  projects/video_002/shots/video_002_shot_017.jpg  ->  public/shots/shot_017.jpg
  projects/video_002/voiceover.mp3                 ->  public/voiceover.mp3

И кладёт props-файл для `remotion render --props=...`:
  projects/video_002/aligned_timeline.json -> render_props.json (обёрнутый как {"timeline": ...})

--clean удаляет public/shots и public/voiceover.mp3 (пост-render очистка, п.6 ТЗ).
"""

import argparse
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from asset_pipeline.project import ProjectError, load_project
from asset_pipeline.repo import REPO_ROOT

PUBLIC_SHOTS_DIR = REPO_ROOT / "public" / "shots"
PUBLIC_VOICEOVER = REPO_ROOT / "public" / "voiceover.mp3"
RENDER_PROPS_PATH = REPO_ROOT / "render_props.json"


def fail(msg: str, code: int = 1):
    print(f"\nОШИБКА: {msg}", file=sys.stderr)
    sys.exit(code)


def stage(project):
    if not project.aligned_timeline_path.exists():
        fail(f"Нет aligned_timeline.json — сначала запустите align_project.py --project {project.id}")

    PUBLIC_SHOTS_DIR.mkdir(parents=True, exist_ok=True)
    timeline = json.loads(project.aligned_timeline_path.read_text(encoding="utf-8"))

    # render_props.json должен содержать имена ПОСЛЕ снятия префикса (то, что реально
    # лежит в public/shots/) — иначе Remotion будет искать несуществующий файл.
    staged_timeline = json.loads(json.dumps(timeline))  # deep copy

    staged = 0
    for shot, staged_shot in zip(timeline["shots"], staged_timeline["shots"]):
        src_name = shot["image"]  # canonical: video_002_shot_017.jpg
        src = project.shots_dir / src_name
        if not src.exists():
            fail(f"Файл шота исчез между alignment и staging: {src}")

        # Снимаем префикс project_id_shot_ -> shot_ ТОЛЬКО в staging-копии.
        stripped_name = src_name.replace(f"{project.id}_shot_", "shot_", 1)
        dst = PUBLIC_SHOTS_DIR / stripped_name
        shutil.copyfile(src, dst)
        staged_shot["image"] = stripped_name
        staged += 1

    if not project.voiceover_path.exists():
        fail(f"Нет voiceover: {project.voiceover_path}")
    shutil.copyfile(project.voiceover_path, PUBLIC_VOICEOVER)

    RENDER_PROPS_PATH.write_text(json.dumps({"timeline": staged_timeline}, ensure_ascii=False), encoding="utf-8")

    print(f"Staged: {staged} shots -> {PUBLIC_SHOTS_DIR}")
    print(f"Staged: voiceover -> {PUBLIC_VOICEOVER}")
    print(f"Staged: render props -> {RENDER_PROPS_PATH}")


def clean():
    if PUBLIC_SHOTS_DIR.exists():
        shutil.rmtree(PUBLIC_SHOTS_DIR)
    if PUBLIC_VOICEOVER.exists():
        PUBLIC_VOICEOVER.unlink()
    if RENDER_PROPS_PATH.exists():
        RENDER_PROPS_PATH.unlink()
    print("Staging очищен (public/shots, public/voiceover.mp3, render_props.json).")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--project")
    p.add_argument("--clean", action="store_true")
    args = p.parse_args()

    if args.clean:
        clean()
        return

    if not args.project:
        fail("Нужен --project (или --clean).")

    try:
        project = load_project(args.project)
    except ProjectError as e:
        fail(str(e))
        return

    stage(project)


if __name__ == "__main__":
    main()
