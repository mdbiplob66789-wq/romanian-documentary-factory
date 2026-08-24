#!/usr/bin/env python3
"""
scripts/run_project.py video_002 [--generate-images] [--render] [--upload] [--resume]

Полный production orchestration (п.37 ТЗ). Без флагов — ничего не делает, кроме
показа READY/NOT READY (безопасный no-op по умолчанию).

Пример полного цикла:
  python scripts/run_project.py video_002 --generate-images --render --upload
"""

import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from asset_pipeline.project import ProjectError, load_project
from asset_pipeline.repo import REPO_ROOT
from check_project import check

SCRIPTS_DIR = Path(__file__).resolve().parent


def fail(msg: str, code: int = 1):
    print(f"\nОШИБКА: {msg}", file=sys.stderr)
    sys.exit(code)


def run(args_list: list[str]):
    r = subprocess.run([sys.executable, *args_list], cwd=REPO_ROOT)
    if r.returncode != 0:
        fail(f"Шаг упал: {' '.join(args_list)}")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("project")
    p.add_argument("--generate-images", action="store_true")
    p.add_argument("--render", action="store_true")
    p.add_argument("--upload", action="store_true")
    p.add_argument("--resume", action="store_true")
    p.add_argument("--force", action="store_true")
    args = p.parse_args()

    project_id = args.project
    script = lambda name: str(SCRIPTS_DIR / name)

    if args.generate_images:
        print(f"\n{'=' * 60}\nGenerate images ({project_id})\n{'=' * 60}")
        gen_args = [script("generate_project.py"), project_id, "--commit"]
        if args.resume:
            gen_args.append("--resume")
        run(gen_args)

    if args.render:
        build_args = [script("build_project.py"), project_id]
        if args.force:
            build_args.append("--force")
        run(build_args)

    if args.upload:
        try:
            project = load_project(project_id)
        except ProjectError as e:
            fail(str(e))
            return
        if not project.final_master_path.exists():
            fail(f"Нет финального файла для загрузки: {project.final_master_path}. Сначала --render.")

        print(f"\n{'=' * 60}\nUpload to Google Drive\n{'=' * 60}")
        dest = f"gdrive:URME_RECI/{project_id}/{project_id}_FINAL_YOUTUBE.mp4"
        r = subprocess.run(
            ["rclone", "copyto", str(project.final_master_path), dest,
             "--drive-chunk-size", "128M", "--transfers", "1", "--checkers", "4",
             "--stats", "15s", "--stats-one-line"],
        )
        if r.returncode != 0:
            fail("Загрузка на Google Drive не прошла.")
        verify = subprocess.run(["rclone", "size", dest], capture_output=True, text=True)
        if verify.returncode != 0:
            fail("Не удалось подтвердить наличие файла на Drive после загрузки.")
        print(f"OK: {dest}\n{verify.stdout}")

    if not any([args.generate_images, args.render, args.upload]):
        ready, problems = check(project_id)
        print("READY TO RENDER" if ready else "NOT READY")
        for pr in problems:
            print(f"- {pr}")
        print("\nНичего не делал — ни один из флагов --generate-images/--render/--upload не передан.")
        print(f"Пример: python scripts/run_project.py {project_id} --generate-images --render --upload")


if __name__ == "__main__":
    main()
