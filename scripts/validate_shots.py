#!/usr/bin/env python3
"""scripts/validate_shots.py --project video_002 — отдельный CLI-шаг для workflow (п.23 ТЗ)."""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from asset_pipeline.project import ProjectError, load_project
from asset_pipeline.shot_validation import ShotValidationError, validate_shots


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--project", required=True)
    args = p.parse_args()

    try:
        project = load_project(args.project)
    except ProjectError as e:
        print(f"ОШИБКА: {e}", file=sys.stderr)
        sys.exit(1)

    if not project.map_path.exists():
        print(f"ОШИБКА: нет map.json: {project.map_path}", file=sys.stderr)
        sys.exit(1)

    map_data = json.loads(project.map_path.read_text(encoding="utf-8"))
    expected = len(map_data.get("shots", []))

    try:
        manifest = validate_shots(project, expected_count=expected)
    except ShotValidationError as e:
        print(f"ОШИБКА: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"OK: {len(manifest)}/{expected} шотов валидны для {project.id}")


if __name__ == "__main__":
    main()
