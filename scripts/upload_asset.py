#!/usr/bin/env python3
"""
scripts/upload_asset.py — загрузка одного изображения (шот или reference) в конкретный проект.

Примеры:
  python scripts/upload_asset.py image.png --project video_002 --shot 17
    -> projects/video_002/shots/video_002_shot_017.jpg
  python scripts/upload_asset.py image.png --project video_002 --next
  python scripts/upload_asset.py reference.png --project video_002 --reference character --name main_character
    -> projects/video_002/references/character/video_002_ref_character_main_character.png
  python scripts/upload_asset.py --project video_002 --retry-push

Главный принцип: PROJECT_ID определяет всё. Никакой глобальной нумерации на весь репозиторий.

Canonical filename для шотов (обязателен с video_002, video_001 — legacy, не трогается):
    {project_id}_shot_{number:03d}.{ext}
Canonical filename для references:
    {project_id}_ref_{category}_{name}.{ext}
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from asset_pipeline import gitops, imageops, numbering, state
from asset_pipeline.naming import UnsafeNameError, reference_stem, validate_safe_name
from asset_pipeline.project import REFERENCE_CATEGORIES, ProjectError, load_project
from asset_pipeline.repo import REPO_ROOT

REMOTE_RENDER_REPO = "mdbiplob66789-wq/romanian-documentary-factory"


def fail(message: str, code: int = 1):
    print(f"\nОШИБКА: {message}", file=sys.stderr)
    sys.exit(code)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Загрузка шота или reference в конкретный проект.")
    p.add_argument("source", nargs="?", help="Путь к локальному файлу изображения")
    p.add_argument("--project", required=True, help="ID проекта, например video_002")

    shot_group = p.add_mutually_exclusive_group()
    shot_group.add_argument("--shot", type=int, help="Явный номер шота")
    shot_group.add_argument("--next", action="store_true", help="Автонумерация следующего шота")

    p.add_argument("--reference", choices=REFERENCE_CATEGORIES, help="Категория reference")
    p.add_argument("--name", help="Безопасное имя reference (латиница/цифры/underscore)")

    p.add_argument("--replace", action="store_true", help="Разрешить перезапись существующего файла")
    p.add_argument("--trigger-render", action="store_true", help="Запустить render.yml после успешного push")
    p.add_argument("--retry-push", action="store_true", help="Повторить push для ранее неудачных загрузок")

    return p


def do_retry_push(project) -> int:
    records = state.load_state(project.upload_state_path)
    failed = [r for r in records if r.get("push_status") == "failed"]
    if not failed:
        print("Нет записей со статусом 'failed' — повторять нечего.")
        return 0

    print(f"Найдено {len(failed)} неотправленных загрузок, пробую git push...")
    ok, msg = gitops.push(REPO_ROOT)
    if not ok:
        fail(
            f"Повторный push снова не прошёл:\n{msg}\n"
            "Локальные файлы и коммиты не тронуты, можно повторить позже."
        )

    for r in failed:
        r["push_status"] = "success"
    project.upload_state_path.write_text(
        json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    _commit_and_push_state_file(project, f"retry-push flushed {len(failed)} record(s)")
    print(f"push прошёл успешно. {len(failed)} записей обновлены на 'success'.")
    return 0


def maybe_trigger_render(project_id: str):
    print("\n== --trigger-render ==")
    print(f"Запускаю render.yml с project_id={project_id} (никогда не задевает legacy video_001).")
    result = subprocess.run(
        ["gh", "workflow", "run", "render.yml", "--repo", REMOTE_RENDER_REPO, "--ref", "main",
         "-f", f"project_id={project_id}"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"Не удалось запустить workflow: {result.stderr.strip()}")
    else:
        print("Workflow 'render.yml' запущен (gh workflow run).")


def main():
    args = build_parser().parse_args()

    try:
        project = load_project(args.project)
    except ProjectError as e:
        fail(str(e))
        return

    if args.retry_push:
        sys.exit(do_retry_push(project))

    if not args.source:
        fail("Не указан файл источника (первый позиционный аргумент).")

    src_path = Path(args.source).expanduser().resolve()
    if not src_path.is_file():
        fail(f"Файл не найден: {src_path}")

    is_shot_mode = args.shot is not None or args.next
    is_reference_mode = args.reference is not None

    if is_shot_mode and is_reference_mode:
        fail("Нельзя одновременно указывать --shot/--next и --reference. Выберите один режим.")
    if not is_shot_mode and not is_reference_mode:
        fail("Укажите режим: --shot N, --next (для шота) или --reference CATEGORY --name NAME.")
    if is_reference_mode and not args.name:
        fail("Для --reference обязателен --name.")

    # 1. Синхронизация с origin ДО любых решений о нумерации — п.10, п.13 ТЗ.
    try:
        gitops.pull_rebase(REPO_ROOT)
    except gitops.GitError as e:
        fail(str(e))

    if is_shot_mode:
        handle_shot(args, project, src_path)
    else:
        handle_reference(args, project, src_path)

    if args.trigger_render:
        maybe_trigger_render(project.id)


def handle_shot(args, project, src_path: Path):
    shots_dir = project.shots_dir
    shots_dir.mkdir(parents=True, exist_ok=True)
    project_id = project.id

    if args.next:
        try:
            shot_number = numbering.next_shot_number(shots_dir, project_id)
        except numbering.ShotSequenceError as e:
            fail(str(e))
            return
    else:
        shot_number = args.shot

    existing = numbering.existing_shot_path(shots_dir, project_id, shot_number)
    canonical_name = numbering.shot_filename(project_id, shot_number)
    if existing and not args.replace:
        fail(
            f"{canonical_name.rsplit('.', 1)[0]} уже существует ({existing.name}). "
            "Используйте --replace, чтобы перезаписать явно."
        )

    try:
        imageops.validate_image(src_path)
    except imageops.ImageValidationError as e:
        fail(str(e))
        return

    if existing and existing.suffix.lower() != ".jpg":
        existing.unlink()  # старое расширение больше не актуально после --replace в jpg

    dst_path = shots_dir / numbering.shot_filename(project_id, shot_number, "jpg")
    imageops.convert_shot_to_jpeg(src_path, dst_path)

    relative_path = str(dst_path.relative_to(REPO_ROOT))

    commit_message = f"Add {project.id} shot {shot_number:03d}"
    finish_upload(project, src_path, dst_path, relative_path, "shot", shot_number, commit_message)


def handle_reference(args, project, src_path: Path):
    try:
        name = validate_safe_name(args.name)
    except UnsafeNameError as e:
        fail(str(e))
        return

    try:
        fmt = imageops.validate_image(src_path)
    except imageops.ImageValidationError as e:
        fail(str(e))
        return

    stem = reference_stem(project.id, args.reference, name)

    dest_dir = project.references_dir / args.reference
    dest_dir.mkdir(parents=True, exist_ok=True)
    dst_no_ext = dest_dir / stem

    existing = next((p for p in dest_dir.glob(f"{stem}.*")), None)
    if existing and not args.replace:
        fail(f"Reference '{stem}' уже существует ({existing.name}). Используйте --replace.")
    if existing and args.replace:
        existing.unlink()

    dst_path = imageops.copy_reference_as_is(src_path, dst_no_ext, fmt)
    relative_path = str(dst_path.relative_to(REPO_ROOT))

    commit_message = f"Add {project.id} {args.reference} reference {name}"
    finish_upload(project, src_path, dst_path, relative_path, "reference", None, commit_message)


def _commit_and_push_state_file(project, note: str):
    """
    upload_state.json — отслеживаемый git-файл. Если менять его на диске и не коммитить,
    следующий 'git pull --rebase' спотыкается об незакоммиченные изменения (реальный баг,
    пойманный при повторном тестировании). Поэтому после каждой правки state.json —
    отдельный маленький коммит. Если push здесь не пройдёт — не страшно: он уедет вместе
    с основным коммитом при следующем --retry-push (один 'git push' отправляет все
    накопленные локальные коммиты разом).
    """
    state_relative = str(project.upload_state_path.relative_to(REPO_ROOT))
    try:
        gitops.add_file(REPO_ROOT, state_relative)
        gitops.commit(REPO_ROOT, f"Update upload_state.json for {project.id} ({note})")
    except gitops.GitError:
        return False
    ok, _ = gitops.push(REPO_ROOT)
    return ok


def finish_upload(project, src_path, dst_path, relative_path, asset_type, shot_number, commit_message):
    sha256 = state.sha256_of(dst_path)

    try:
        gitops.add_file(REPO_ROOT, relative_path)
        commit_hash = gitops.commit(REPO_ROOT, commit_message)
    except gitops.GitError as e:
        # Файл на диске остаётся — состояние не теряем, номер не освобождаем (п.11 ТЗ).
        record = state.new_record(
            source_file=str(src_path),
            destination=relative_path,
            asset_type=asset_type,
            shot_number=shot_number,
            sha256=sha256,
            push_status="failed",
            commit_hash=None,
        )
        state.append_state_record(project.upload_state_path, record)
        _commit_and_push_state_file(project, "asset commit failed")
        fail(f"{e}\nФайл сохранён локально ({dst_path}), но не закоммичен. Разберитесь с git и повторите.")
        return

    ok, msg = gitops.push(REPO_ROOT)
    record = state.new_record(
        source_file=str(src_path),
        destination=relative_path,
        asset_type=asset_type,
        shot_number=shot_number,
        sha256=sha256,
        push_status="success" if ok else "failed",
        commit_hash=commit_hash,
    )
    state.append_state_record(project.upload_state_path, record)
    _commit_and_push_state_file(project, f"{asset_type} {relative_path}")

    if not ok:
        fail(
            f"Файл закоммичен локально ({commit_hash}), но push не прошёл:\n{msg}\n"
            f"Локальный файл и коммит НЕ удалены. Повторите позже: "
            f"python scripts/upload_asset.py --project {project.id} --retry-push"
        )

    print(f"\nOK: {relative_path}")
    print(f"commit {commit_hash}, push успешен.")


if __name__ == "__main__":
    main()
