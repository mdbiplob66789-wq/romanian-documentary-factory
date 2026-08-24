#!/usr/bin/env python3
"""scripts/qc_final.py --project video_002 -> projects/<id>/qc/final_qc.json (п.21, п.32-33 ТЗ)."""

import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from asset_pipeline.project import ProjectError, load_project


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

    final_path = project.final_master_path
    qc = {"project_id": project.id, "path": str(final_path)}

    if not final_path.exists():
        fail(f"Финальный файл не существует: {final_path}")

    size = final_path.stat().st_size
    qc["file_size_bytes"] = size
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
    v_streams = [s for s in streams if s.get("codec_type") == "video"]
    a_streams = [s for s in streams if s.get("codec_type") == "audio"]
    duration = float(info["format"].get("duration", 0))

    qc.update({
        "video_stream_present": bool(v_streams),
        "audio_stream_present": bool(a_streams),
        "duration": duration,
        "resolution": f"{v_streams[0].get('width')}x{v_streams[0].get('height')}" if v_streams else None,
        "video_codec": v_streams[0].get("codec_name") if v_streams else None,
        "audio_codec": a_streams[0].get("codec_name") if a_streams else None,
    })

    if not v_streams:
        fail("В финальном файле нет видеопотока.")
    if not a_streams:
        fail("В финальном файле нет аудиопотока (музыка/голос) — Drive-мастер без музыки запрещён (п.18/29 ТЗ).")
    if duration <= 0:
        fail("Некорректная длительность финального файла.")

    print("== ffmpeg decode validation (п.33 ТЗ) ==")
    decode = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(final_path), "-f", "null", "-"],
        capture_output=True, text=True,
    )
    qc["decode_clean"] = decode.returncode == 0 and not decode.stderr.strip()
    if not qc["decode_clean"]:
        qc["status"] = "FAIL"
        project.qc_dir.mkdir(parents=True, exist_ok=True)
        (project.qc_dir / "final_qc.json").write_text(json.dumps(qc, ensure_ascii=False, indent=2), encoding="utf-8")
        fail(f"Ошибки декодирования финального файла:\n{decode.stderr.strip()[:2000]}")

    qc["status"] = "PASS"
    project.qc_dir.mkdir(parents=True, exist_ok=True)
    out_path = project.qc_dir / "final_qc.json"
    out_path.write_text(json.dumps(qc, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"OK: {final_path} | {size / 1_048_576:.1f} MiB | {duration:.2f}s | video+audio present | decode clean")
    print(f"Final QC PASS -> {out_path}")


if __name__ == "__main__":
    main()
