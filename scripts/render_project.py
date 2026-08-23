#!/usr/bin/env python3
"""
scripts/render_project.py video_002 — one-command render (п.27 ТЗ).

1. readiness check (check_project.py);
2. gh workflow run render.yml -f project_id=<id>;
3. печатает URL запуска, project_id, ожидаемый Drive destination.

Тяжёлый render НЕ выполняется локально — всегда через GitHub Actions.
"""

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from check_project import check

REPO = "mdbiplob66789-wq/romanian-documentary-factory"


def main():
    if len(sys.argv) != 2:
        print("Использование: python scripts/render_project.py <project_id>", file=sys.stderr)
        sys.exit(1)

    project_id = sys.argv[1]

    ready, problems = check(project_id)
    if not ready:
        print("NOT READY — рендер не запущен:")
        for pr in problems:
            print(f"- {pr}")
        sys.exit(1)

    print(f"READY TO RENDER: {project_id}")

    result = subprocess.run(
        ["gh", "workflow", "run", "render.yml", "--repo", REPO, "--ref", "main", "-f", f"project_id={project_id}"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        print(f"ОШИБКА запуска workflow:\n{result.stderr.strip()}", file=sys.stderr)
        sys.exit(1)

    # gh workflow run не всегда возвращает URL напрямую — достаём последний run для этого workflow.
    list_result = subprocess.run(
        ["gh", "run", "list", "--repo", REPO, "--workflow", "render.yml", "--limit", "1",
         "--json", "url,databaseId,status"],
        capture_output=True, text=True,
    )

    print(f"\nproject_id: {project_id}")
    print(f"Drive destination: gdrive:URME_RECI/{project_id}/{project_id}_FINAL_YOUTUBE.mp4")
    if list_result.returncode == 0:
        print(f"Workflow run: {list_result.stdout.strip()}")
    else:
        print("Workflow запущен, но не удалось получить URL — проверьте вручную: "
              f"gh run list --repo {REPO} --workflow render.yml --limit 1")


if __name__ == "__main__":
    main()
