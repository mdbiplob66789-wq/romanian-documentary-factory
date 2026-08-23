#!/usr/bin/env python3
"""
scripts/qc_audio.py --project video_002  ->  projects/<id>/audio_qc.json  (п.19 ТЗ)

Измеряет громкость финального мастера, проверяет, что music body-участки разных
блоков (за вычетом intro/outro fade и crossfade-окон) остаются в пределах ~±1dB
друг от друга — то есть музыка реально ровный постоянный фон, без скачков.
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from asset_pipeline.project import (
    DEFAULT_CROSSFADE_SEC, DUCKING_ENABLED, INTRO_FADE_SEC, MUSIC_BELOW_VOICE_DB,
    OUTRO_FADE_SEC, ProjectError, VOICE_TARGET_LUFS, load_project,
)
from asset_pipeline.repo import REPO_ROOT

OUT_DIR = REPO_ROOT / "out"
BODY_TOLERANCE_DB = 1.0


def fail(msg: str, code: int = 1):
    print(f"\nОШИБКА: {msg}", file=sys.stderr)
    sys.exit(code)


def ffprobe_json(path: Path) -> dict:
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(path)],
        capture_output=True, text=True,
    )
    if r.returncode != 0:
        fail(f"ffprobe: {r.stderr.strip()}")
    return json.loads(r.stdout)


def measure_loudness(path: Path) -> dict:
    r = subprocess.run(
        ["ffmpeg", "-i", str(path), "-af", "loudnorm=print_format=json", "-f", "null", "-"],
        capture_output=True, text=True,
    )
    text = r.stderr
    start = text.rfind("{")
    if start == -1:
        fail("Не удалось измерить loudness (loudnorm не вернул JSON).")
    # Вырезаем ровно один сбалансированный JSON-объект — rfind("{") + голый slice
    # ловил "Extra data", если после JSON в stderr ещё что-то шло (реальный баг,
    # пойманный при self-test).
    depth = 0
    end = None
    for i, ch in enumerate(text[start:], start=start):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                end = i + 1
                break
    if end is None:
        fail("Не удалось распарсить JSON от loudnorm (незакрытые скобки).")
    data = json.loads(text[start:end])
    return {
        "integrated_lufs": float(data["input_i"]),
        "true_peak_dbtp": float(data["input_tp"]),
        "lra": float(data["input_lra"]),
    }


def mean_volume_window(path: Path, start: float, duration: float) -> float | None:
    if duration <= 0:
        return None
    r = subprocess.run(
        ["ffmpeg", "-ss", f"{start:.3f}", "-t", f"{duration:.3f}", "-i", str(path),
         "-af", "volumedetect", "-f", "null", "-"],
        capture_output=True, text=True,
    )
    for line in r.stderr.splitlines():
        if "mean_volume" in line:
            return float(line.split(":")[1].strip().split(" ")[0])
    return None


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
        fail(f"Нет финального файла: {final_path}")

    info = ffprobe_json(final_path)
    streams = info.get("streams", [])
    has_audio = any(s.get("codec_type") == "audio" for s in streams)
    has_video = any(s.get("codec_type") == "video" for s in streams)
    duration = float(info["format"].get("duration", 0))

    loud = measure_loudness(final_path)

    music_map = json.loads(project.music_map_path.read_text(encoding="utf-8")) if project.music_map_path.exists() else {}
    timeline = json.loads(project.aligned_timeline_path.read_text(encoding="utf-8")) if project.aligned_timeline_path.exists() else {}
    blocks = timeline.get("music_blocks", [])
    crossfade_sec = float(music_map.get("crossfade_sec", DEFAULT_CROSSFADE_SEC))
    intro_sec = float(music_map.get("intro_fade_sec", INTRO_FADE_SEC))
    outro_sec = float(music_map.get("outro_fade_sec", OUTRO_FADE_SEC))

    # Body-окна: середина каждого блока, подальше от intro/outro/crossfade границ.
    body_levels = []
    for i, b in enumerate(blocks):
        lo = b["start"] + (intro_sec if i == 0 else crossfade_sec)
        hi = b["end"] - (outro_sec if i == len(blocks) - 1 else crossfade_sec)
        if hi - lo < 2:
            continue
        mid = (lo + hi) / 2
        window = min(10.0, hi - lo)
        level = mean_volume_window(final_path, mid - window / 2, window)
        body_levels.append({"block": b["file"], "window_start": round(mid - window / 2, 2), "mean_db": level})

    numeric_levels = [x["mean_db"] for x in body_levels if x["mean_db"] is not None]
    jump_detected = False
    if len(numeric_levels) >= 2:
        jump_detected = (max(numeric_levels) - min(numeric_levels)) > BODY_TOLERANCE_DB

    qc = {
        "project_id": project.id,
        "voice_lufs": VOICE_TARGET_LUFS,
        "music_target_db": VOICE_TARGET_LUFS + MUSIC_BELOW_VOICE_DB,
        "ducking_enabled": DUCKING_ENABLED,
        "music_blocks": [b["file"] for b in blocks],
        "crossfade_sec": crossfade_sec,
        "peak": loud["true_peak_dbtp"],
        "true_peak": loud["true_peak_dbtp"],
        "integrated_lufs": loud["integrated_lufs"],
        "lra": loud["lra"],
        "duration": duration,
        "audio_stream_present": has_audio,
        "video_stream_present": has_video,
        "body_levels": body_levels,
        "body_tolerance_db": BODY_TOLERANCE_DB,
        "body_jump_detected": jump_detected,
        "status": "FAIL" if (jump_detected or not has_audio or not has_video) else "PASS",
    }

    out_path = project.root / "audio_qc.json"
    out_path.write_text(json.dumps(qc, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(qc, ensure_ascii=False, indent=2))

    if qc["status"] == "FAIL":
        fail(f"Audio QC FAIL (см. {out_path})")
    print(f"\nAudio QC PASS -> {out_path}")


if __name__ == "__main__":
    main()
