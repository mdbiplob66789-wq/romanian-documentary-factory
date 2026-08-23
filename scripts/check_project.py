#!/usr/bin/env python3
"""scripts/check_project.py --project video_002 — readiness check (п.26 ТЗ)."""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from asset_pipeline import numbering
from asset_pipeline.project import ProjectError, load_project, project_exists


def check(project_id: str) -> tuple[bool, list[str]]:
    problems = []
    if not project_exists(project_id):
        return False, [f"Проект '{project_id}' не существует (нет project.json)."]

    project = load_project(project_id)

    if not project.map_path.exists():
        problems.append(f"Нет map.json: {project.map_path}")
        map_data = {"shots": []}
    else:
        try:
            map_data = json.loads(project.map_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            problems.append(f"map.json невалиден: {e}")
            map_data = {"shots": []}

    if not project.music_map_path.exists():
        problems.append(f"Нет music_map.json: {project.music_map_path}")

    if not project.voiceover_path.exists():
        problems.append(f"Нет voiceover: {project.voiceover_path}")

    expected_shots = len(map_data.get("shots", []))
    if expected_shots == 0:
        problems.append("map.json не содержит ни одного шота.")
    else:
        numbers = numbering.scan_shot_numbers(project.shots_dir, project_id)
        missing = numbering.find_gaps(numbers) if numbers else list(range(1, expected_shots + 1))
        if numbers and max(numbers) < expected_shots:
            missing = sorted(set(missing) | set(range(max(numbers) + 1, expected_shots + 1)))
        if len(numbers) < expected_shots or missing:
            have = len(numbers)
            problems.append(f"Не хватает шотов: {have}/{expected_shots}. Отсутствуют: "
                             + ", ".join(numbering.shot_filename(project_id, n).rsplit(".", 1)[0] for n in missing[:20]))

    if project.music_map_path.exists():
        try:
            music_map = json.loads(project.music_map_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            problems.append(f"music_map.json невалиден: {e}")
            music_map = {}
        for block in music_map.get("blocks", []):
            f = project.music_dir / block["file"]
            if not f.exists():
                problems.append(f"Нет музыкального файла: {f}")

    return (len(problems) == 0), problems


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--project", required=True)
    args = p.parse_args()

    try:
        ready, problems = check(args.project)
    except ProjectError as e:
        print(f"NOT READY\n- {e}")
        sys.exit(1)

    if ready:
        print("READY TO RENDER")
        sys.exit(0)
    else:
        print("NOT READY")
        for pr in problems:
            print(f"- {pr}")
        sys.exit(1)


if __name__ == "__main__":
    main()
