#!/usr/bin/env python3
"""
scripts/build_project.py video_002 [--force]

Одна команда полной локальной сборки (п.19, п.36 ТЗ):
  check_project -> align_shots -> render_video -> qc_visual ->
  build_audio -> qc_audio -> qc_final

Если не хватает обязательного ассета — останавливается ДО тяжёлого рендера
(check_project делает это первым шагом).

--force игнорирует hash-based invalidation (п.38-40) и пересобирает всё заново.
Без --force: если хэши voiceover/map/shots не изменились с прошлого успешного
alignment — align_shots.py и render_video.py всё равно перезапускаются (само
определение "актуально или нет" — на их совести через state_hashes.json),
но ничего не рендерится ВТОРОЙ раз впустую при повторном --force=False запуске
с теми же входами: увидев, что финальный мастер уже собран из тех же хэшей,
build_project.py останавливается с сообщением "уже собрано".
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from asset_pipeline.hashing import compute_project_hashes, load_hashes, save_hashes
from asset_pipeline.project import ProjectError, load_project
from asset_pipeline.repo import REPO_ROOT
from check_project import check

SCRIPTS_DIR = Path(__file__).resolve().parent


def fail(msg: str, code: int = 1):
    print(f"\nОШИБКА: {msg}", file=sys.stderr)
    sys.exit(code)


def run_step(name: str, args: list[str]):
    print(f"\n{'=' * 60}\n{name}\n{'=' * 60}")
    r = subprocess.run([sys.executable, *args], cwd=REPO_ROOT)
    if r.returncode != 0:
        fail(f"Шаг '{name}' упал (exit {r.returncode}). Дальше не идём.")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("project")
    p.add_argument("--force", action="store_true", help="Пересобрать всё, даже если ничего не изменилось")
    args = p.parse_args()

    project_id = args.project

    ready, problems = check(project_id)
    if not ready:
        print("NOT READY — сборка не начата:")
        for pr in problems:
            print(f"- {pr}")
        sys.exit(1)
    print("READY TO RENDER")

    project = load_project(project_id)

    if not args.force and project.final_master_path.exists():
        old_hashes = load_hashes(project.state_hashes_path).get("final", {})
        current = compute_project_hashes(project)
        if old_hashes and all(old_hashes.get(k) == current.get(k) for k in ("voiceover", "map", "music_map", "shots", "music")):
            print(f"\nUже собрано из тех же входов: {project.final_master_path}")
            print("Ничего не изменилось (voiceover/map/music_map/shots/music). Используйте --force для пересборки.")
            return

    script = lambda name: str(SCRIPTS_DIR / name)

    run_step("1/6 Align shots (faster-whisper)", [script("align_shots.py"), "--project", project_id])
    run_step("2/6 Render visual (ffmpeg)", [script("render_video.py"), "--project", project_id])
    run_step("3/6 Visual QC", [script("qc_visual.py"), "--project", project_id])
    run_step("4/6 Build audio", [script("build_audio.py"), "--project", project_id])
    run_step("5/6 Audio QC", [script("qc_audio.py"), "--project", project_id])
    run_step("6/6 Final QC", [script("qc_final.py"), "--project", project_id])

    hashes = load_hashes(project.state_hashes_path)
    hashes["final"] = compute_project_hashes(project)
    save_hashes(project.state_hashes_path, hashes)

    print(f"\nDONE: {project.final_master_path}")


if __name__ == "__main__":
    main()
