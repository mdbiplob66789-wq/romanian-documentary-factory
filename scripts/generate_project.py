#!/usr/bin/env python3
"""
scripts/generate_project.py video_002 [--resume] [--shot N] [--force] [--commit]

Читает map.json, для каждого shot вызывает NordRouter (router.cheap) и сохраняет
результат СРАЗУ под canonical именем в projects/<id>/shots/ — без inbox, без
ручного перемещения (п.5, п.6 ТЗ).

Останавливается на первом shot, который не удалось сгенерировать после всех
попыток (не "молча продолжает") — состояние сохраняется, --resume продолжает
именно с этого shot, не трогая уже готовые (п.6, п.40 ТЗ).
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from asset_pipeline import gitops, imageops, numbering
from asset_pipeline.logs import StageLogger
from asset_pipeline.project import ProjectError, load_project
from asset_pipeline.repo import REPO_ROOT
from nordrouter_client import GenerationError, generate_image


def fail(msg: str, code: int = 1):
    print(f"\nОШИБКА: {msg}", file=sys.stderr)
    sys.exit(code)


def load_generation_state(project) -> dict:
    if not project.generation_state_path.exists():
        return {}
    try:
        return json.loads(project.generation_state_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def save_generation_state(project, state: dict):
    project.work_dir.mkdir(parents=True, exist_ok=True)
    project.generation_state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def main():
    p = argparse.ArgumentParser(description="Генерация изображений проекта через NordRouter.")
    p.add_argument("project", help="project_id, например video_002")
    p.add_argument("--resume", action="store_true", help="Продолжить с первого негенерированного/неудачного shot")
    p.add_argument("--shot", type=int, help="Сгенерировать только один конкретный shot")
    p.add_argument("--force", action="store_true", help="Перегенерировать, даже если файл уже есть")
    p.add_argument("--commit", action="store_true", help="Один batch-коммит+push новых кадров в конце")
    args = p.parse_args()

    try:
        project = load_project(args.project)
    except ProjectError as e:
        fail(str(e))
        return

    if not project.map_path.exists():
        fail(f"Нет map.json: {project.map_path}")

    map_data = json.loads(project.map_path.read_text(encoding="utf-8"))
    shots_plan = sorted(map_data.get("shots", []), key=lambda r: r["SHOT"])
    if not shots_plan:
        fail("map.json не содержит shots[]")

    if args.shot:
        shots_plan = [r for r in shots_plan if r["SHOT"] == args.shot]
        if not shots_plan:
            fail(f"Shot {args.shot} не найден в map.json")

    project.shots_dir.mkdir(parents=True, exist_ok=True)
    state = load_generation_state(project)
    logger = StageLogger(project, "generation")

    new_files = []
    generated = 0
    skipped = 0

    for row in shots_plan:
        shot_number = row["SHOT"]
        prompt = row.get("prompt") or row.get("PROMPT")
        if not prompt:
            fail(f"Shot {shot_number}: в map.json нет поля 'prompt'")

        existing = numbering.existing_shot_path(project.shots_dir, project.id, shot_number)
        if existing and not args.force:
            skipped += 1
            state[str(shot_number)] = {"status": "success", "file": existing.name, "skipped_existing": True}
            continue

        logger.log(f"Generating shot {shot_number}/{shots_plan[-1]['SHOT']}: {prompt[:80]}")

        try:
            image_bytes, ext = generate_image(prompt)
        except GenerationError as e:
            state[str(shot_number)] = {"status": "failed", "error": str(e),
                                        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds")}
            save_generation_state(project, state)
            logger.error(f"Shot {shot_number} failed: {e}")
            fail(
                f"Shot {shot_number} не удалось сгенерировать: {e}\n"
                f"Состояние сохранено. Продолжить с этого места: "
                f"python scripts/generate_project.py {project.id} --resume"
            )
            return

        dst = project.shots_dir / numbering.shot_filename(project.id, shot_number, ext)
        dst.write_bytes(image_bytes)

        try:
            imageops.validate_image(dst)
        except imageops.ImageValidationError as e:
            dst.unlink(missing_ok=True)
            state[str(shot_number)] = {"status": "failed", "error": f"invalid image: {e}"}
            save_generation_state(project, state)
            fail(f"Shot {shot_number}: сгенерированный файл не открывается как изображение: {e}")
            return

        state[str(shot_number)] = {
            "status": "success", "file": dst.name,
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        save_generation_state(project, state)
        new_files.append(dst)
        generated += 1
        logger.log(f"Saved: {dst.relative_to(REPO_ROOT)}")

    print(f"\nDONE: сгенерировано {generated}, пропущено (уже было) {skipped}")

    if args.commit and new_files:
        try:
            gitops.pull_rebase(REPO_ROOT)
            for f in new_files:
                gitops.add_file(REPO_ROOT, str(f.relative_to(REPO_ROOT)))
            gitops.add_file(REPO_ROOT, str(project.generation_state_path.relative_to(REPO_ROOT)))
            commit_hash = gitops.commit(REPO_ROOT, f"Generate {len(new_files)} shot(s) for {project.id}")
            ok, msg = gitops.push(REPO_ROOT)
            if ok:
                print(f"Закоммичено и запушено: {commit_hash}")
            else:
                print(f"Закоммичено локально ({commit_hash}), push не прошёл: {msg}")
        except gitops.GitError as e:
            print(f"ПРЕДУПРЕЖДЕНИЕ: коммит не удался: {e}")

    logger.close()


if __name__ == "__main__":
    main()
