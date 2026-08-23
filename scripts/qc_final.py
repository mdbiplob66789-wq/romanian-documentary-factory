#!/usr/bin/env python3
"""scripts/qc_final.py --project video_002 — финальная проверка перед Drive upload (п.21 ТЗ)."""

import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from asset_pipeline.project import ProjectError, load_project
from asset_pipeline.repo import REPO_ROOT

OUT_DIR = REPO_ROOT / "out"


def fail(msg: str, code: int = 1):
    print(f"\nОШИБКА: {msg}", file=sys.stderr)
    sys.exit(code)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--project", required=True)
    args = p.parse_args()

    try:
        project = load_project(args.project)
    except ProjectError as e:
        fail(str(e))
        return

    final_path = OUT_DIR / project.output_name
    if not final_path.exists():
        fail(f"Финальный файл не существует: {final_path}")

    size = final_path.stat().st_size
    if size <= 0:
        fail(f"Финальный файл пустой: {final_path}")

    r = subprocess.run(
        ["ffprobe", "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(final_path)],
        capture_output=True, text=True,
    )
    if r.returncode != 0:
        fail(f"ffprobe не смог прочитать финальный файл: {r.stderr.strip()}")
    info = json.loads(r.stdout)
    streams = info.get("streams", [])
    has_video = any(s.get("codec_type") == "video" for s in streams)
    has_audio = any(s.get("codec_type") == "audio" for s in streams)
    duration = float(info["format"].get("duration", 0))

    if not has_video:
        fail("В финальном файле нет видеопотока.")
    if not has_audio:
        fail("В финальном файле нет аудиопотока (музыка/голос) — Drive-мастер без музыки запрещён (п.18 ТЗ).")
    if duration <= 0:
        fail("Некорректная длительность финального файла.")

    print("== ffmpeg decode validation ==")
    decode = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(final_path), "-f", "null", "-"],
        capture_output=True, text=True,
    )
    if decode.returncode != 0 or decode.stderr.strip():
        fail(f"Ошибки декодирования финального файла:\n{decode.stderr.strip()[:2000]}")

    print(f"OK: {final_path} | {size / 1_048_576:.1f} MiB | {duration:.2f}s | video+audio present | decode clean")


if __name__ == "__main__":
    main()
