#!/usr/bin/env python3
"""scripts/project_status.py video_002 — человекочитаемый статус (п.28 ТЗ)."""

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from asset_pipeline import numbering
from asset_pipeline.project import ProjectError, load_project

REPO = "mdbiplob66789-wq/romanian-documentary-factory"


def main():
    if len(sys.argv) != 2:
        print("Использование: python scripts/project_status.py <project_id>", file=sys.stderr)
        sys.exit(1)

    project_id = sys.argv[1]

    try:
        project = load_project(project_id)
    except ProjectError as e:
        print(f"ОШИБКА: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"project: {project_id}")

    expected = 0
    if project.map_path.exists():
        try:
            expected = len(json.loads(project.map_path.read_text(encoding="utf-8")).get("shots", []))
        except json.JSONDecodeError:
            pass
    numbers = numbering.scan_shot_numbers(project.shots_dir, project_id)
    print(f"shots:\n  {len(numbers)}/{expected or '?'}")

    print(f"voiceover:\n  {'OK' if project.voiceover_path.exists() else 'MISSING'}")

    if project.alignment_report_path.exists():
        report = json.loads(project.alignment_report_path.read_text(encoding="utf-8"))
        conf = report.get("min_shot_confidence")
        print(f"shot alignment:\n  OK (min confidence {conf:.3f})" if conf is not None else "shot alignment:\n  OK")
    else:
        print("shot alignment:\n  NOT RUN")

    print(f"music map:\n  {'OK' if project.music_map_path.exists() else 'MISSING'}")

    music_have = music_expected = 0
    if project.music_map_path.exists():
        try:
            mm = json.loads(project.music_map_path.read_text(encoding="utf-8"))
            blocks = mm.get("blocks", [])
            music_expected = len(blocks)
            music_have = sum(1 for b in blocks if (project.music_dir / b["file"]).exists())
        except json.JSONDecodeError:
            pass
    print(f"music:\n  {music_have}/{music_expected or '?'}")

    render_status = "unknown"
    r = subprocess.run(
        ["gh", "run", "list", "--repo", REPO, "--workflow", "render.yml", "--limit", "20",
         "--json", "status,conclusion,displayTitle,headBranch"],
        capture_output=True, text=True,
    )
    if r.returncode == 0:
        try:
            runs = json.loads(r.stdout)
            render_status = "no runs found"
            for run in runs:
                render_status = run["status"] if run["status"] != "completed" else (run["conclusion"] or "unknown")
                break
        except (json.JSONDecodeError, KeyError, IndexError):
            pass
    print(f"render:\n  {render_status}")

    drive_status = "unknown (rclone not available or not configured)"
    check_rclone = subprocess.run(["which", "rclone"], capture_output=True, text=True)
    if check_rclone.returncode == 0:
        r = subprocess.run(
            ["rclone", "lsf", f"gdrive:URME_RECI/{project_id}/"],
            capture_output=True, text=True,
        )
        if r.returncode == 0 and f"{project_id}_FINAL_YOUTUBE.mp4" in r.stdout:
            drive_status = "available"
        elif r.returncode == 0:
            drive_status = "missing"
        else:
            drive_status = "missing (folder not found)"
    print(f"Drive master:\n  {drive_status}")


if __name__ == "__main__":
    main()
