"""
upload_state.json — журнал загрузок по каждому проекту отдельно.
ВАЖНО (п.13 ТЗ): этот файл — только журнал/аудит. Источник истины для нумерации
шотов — реальные файлы на диске (см. numbering.py), state.json для этого не читается.
"""

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_state(state_path: Path) -> list[dict]:
    if not state_path.exists():
        return []
    try:
        data = json.loads(state_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        # Не роняем весь процесс из-за повреждённого журнала — просто предупреждаем.
        print(f"ПРЕДУПРЕЖДЕНИЕ: {state_path} повреждён (невалидный JSON), журнал будет пересоздан.")
        return []
    return data if isinstance(data, list) else []


def append_state_record(state_path: Path, record: dict) -> None:
    records = load_state(state_path)
    records.append(record)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")


def new_record(
    *,
    source_file: str,
    destination: str,
    asset_type: str,
    shot_number: int | None,
    sha256: str,
    push_status: str,
    commit_hash: str | None = None,
) -> dict:
    return {
        "source_file": source_file,
        "destination": destination,
        "type": asset_type,
        "shot_number": shot_number,
        "sha256": sha256,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "commit_hash": commit_hash,
        "push_status": push_status,
    }
