#!/usr/bin/env python3
"""
scripts/watch_assets.py --project video_002

Следит за входящими папками ОДНОГО проекта и сам загружает новые файлы.
Изоляция (п.15 ТЗ): пути строятся только из --project, watcher video_002
физически не может увидеть inbox video_003 — они просто разные ветки на диске.

Входящие папки:
  ~/UrmeReci/inbox/<project>/shots/
  ~/UrmeReci/inbox/<project>/references/character/
  ~/UrmeReci/inbox/<project>/references/environment/
  ~/UrmeReci/inbox/<project>/references/props/
  ~/UrmeReci/inbox/<project>/references/style/
  ~/UrmeReci/inbox/<project>/references/other/

Реализовано поллингом (без сторонних зависимостей вроде watchdog) —
раз в POLL_INTERVAL секунд сканирует папки, ждёт стабилизации размера файла
(чтобы не подхватить недокопированный файл), затем вызывает ту же логику,
что и upload_asset.py.
"""

import argparse
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from asset_pipeline.naming import safe_stem_from_filename
from asset_pipeline.project import REFERENCE_CATEGORIES, ProjectError, load_project

INBOX_ROOT = Path.home() / "UrmeReci" / "inbox"
POLL_INTERVAL = 2.0
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}

THIS_SCRIPT_DIR = Path(__file__).resolve().parent
UPLOAD_SCRIPT = THIS_SCRIPT_DIR / "upload_asset.py"


def watched_dirs(project_id: str) -> dict[str, Path]:
    """
    project_id полностью определяет набор путей — другой проект сюда попасть не может.
    П.14 ТЗ явно перечисляет только 4 inbox-категории (character/environment/props/style);
    добавляю сюда же 'other' для полноты — так же, как она присутствует среди
    REFERENCE_CATEGORIES и в структуре new_project.py.
    """
    base = INBOX_ROOT / project_id
    dirs = {"shots": base / "shots"}
    for category in REFERENCE_CATEGORIES:
        dirs[f"reference:{category}"] = base / "references" / category
    return dirs


def is_stable(path: Path) -> bool:
    """
    Сверяет размер файла в двух замерах подряд с паузой — если совпал,
    считаем копирование завершённым. Если нет — вернёт False, и файл
    будет проверен заново на следующем цикле поллинга (не блокируем весь watcher).
    """
    try:
        size_before = path.stat().st_size
        time.sleep(0.5)
        size_after = path.stat().st_size
        return size_before == size_after
    except FileNotFoundError:
        return False


def run_upload(args_list: list[str]) -> bool:
    result = subprocess.run([sys.executable, str(UPLOAD_SCRIPT), *args_list])
    return result.returncode == 0


def move_to_processed(src: Path, success: bool):
    marker = "_uploaded" if success else "_failed"
    dest_dir = src.parent / marker
    dest_dir.mkdir(exist_ok=True)
    dest = dest_dir / src.name
    if dest.exists():
        dest = dest_dir / f"{src.stem}_{int(time.time())}{src.suffix}"
    src.rename(dest)


def process_file(kind: str, path: Path, project_id: str) -> bool:
    """Возвращает True, если файл был реально обработан (и его больше не нужно проверять снова)."""
    print(f"\n[{kind}] новый файл: {path.name}")
    if not is_stable(path):
        print("  файл ещё копируется, проверю на следующем цикле")
        return False

    if kind == "shots":
        args_list = [str(path), "--project", project_id, "--next"]
    else:
        category = kind.split(":", 1)[1]
        name = safe_stem_from_filename(path.name)
        args_list = [str(path), "--project", project_id, "--reference", category, "--name", name]

    ok = run_upload(args_list)
    move_to_processed(path, ok)
    print(f"  {'OK' if ok else 'ОШИБКА, файл перемещён в _failed/'}")
    return True


def main():
    p = argparse.ArgumentParser(description="Watch-режим: авто-загрузка новых файлов проекта.")
    p.add_argument("--project", required=True)
    args = p.parse_args()

    try:
        load_project(args.project)
    except ProjectError as e:
        print(f"ОШИБКА: {e}", file=sys.stderr)
        sys.exit(1)

    dirs = watched_dirs(args.project)
    for d in dirs.values():
        d.mkdir(parents=True, exist_ok=True)

    print(f"Watch-режим для проекта '{args.project}'. Слежу за:")
    for d in dirs.values():
        print(f"  {d}")
    print("Ctrl+C для остановки.\n")

    seen: set[Path] = set()

    try:
        while True:
            for kind, d in dirs.items():
                if not d.is_dir():
                    continue
                for entry in d.iterdir():
                    if not entry.is_file():
                        continue
                    if entry.suffix.lower() not in IMAGE_EXTENSIONS:
                        continue
                    if entry in seen:
                        continue
                    if process_file(kind, entry, args.project):
                        seen.add(entry)  # помечаем как обработанный только после реальной обработки
            time.sleep(POLL_INTERVAL)
    except KeyboardInterrupt:
        print("\nОстановлено пользователем.")


if __name__ == "__main__":
    main()
