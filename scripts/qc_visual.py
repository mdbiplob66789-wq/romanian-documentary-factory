#!/usr/bin/env python3
"""scripts/qc_visual.py --project video_002 -> projects/<id>/render_qc.json (п.20 ТЗ)"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from asset_pipeline import numbering
from asset_pipeline.project import ProjectError, load_project
from asset_pipeline.repo import REPO_ROOT

OUT_DIR = REPO_ROOT / "out"
DURATION_TOLERANCE_SEC = 0.5


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


def audio_duration(path: Path) -> float:
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(path)],
        capture_output=True, text=True,
    )
    return float(r.stdout.strip())


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--project", required=True)
    args = p.parse_args()

    try:
        project = load_project(args.project)
    except ProjectError as e:
        fail(str(e))
        return

    visual_master = OUT_DIR / project.visual_master_name
    if not visual_master.exists():
        fail(f"Нет visual master: {visual_master}")

    numbers = numbering.scan_shot_numbers(project.shots_dir, project.id)
    gaps = numbering.find_gaps(numbers)
    dup_check = {}
    for entry in project.shots_dir.iterdir() if project.shots_dir.is_dir() else []:
        m = numbering.shot_regex(project.id).match(entry.name)
        if m:
            dup_check.setdefault(int(m.group(1)), []).append(entry.name)
    duplicates = {k: v for k, v in dup_check.items() if len(v) > 1}

    alignment_report = {}
    if project.alignment_report_path.exists():
        alignment_report = json.loads(project.alignment_report_path.read_text(encoding="utf-8"))

    info = ffprobe_json(visual_master)
    v_streams = [s for s in info.get("streams", []) if s.get("codec_type") == "video"]
    video_duration = float(info["format"].get("duration", 0))
    voiceover_duration = audio_duration(project.voiceover_path) if project.voiceover_path.exists() else None

    duration_diff = None
    if voiceover_duration is not None:
        duration_diff = abs(video_duration - voiceover_duration)

    qc = {
        "project_id": project.id,
        "shot_count": len(numbers),
        "first_shot": min(numbers) if numbers else None,
        "last_shot": max(numbers) if numbers else None,
        "missing_shots": gaps,
        "duplicate_shots": duplicates,
        "alignment_min_confidence": alignment_report.get("min_shot_confidence"),
        "voiceover_duration": voiceover_duration,
        "video_duration": video_duration,
        "duration_diff_sec": duration_diff,
        "duration_tolerance_sec": DURATION_TOLERANCE_SEC,
        "resolution": f"{v_streams[0].get('width')}x{v_streams[0].get('height')}" if v_streams else None,
        "fps": eval(v_streams[0].get("r_frame_rate", "0/1")) if v_streams else None,
        "video_codec": v_streams[0].get("codec_name") if v_streams else None,
    }
    qc["status"] = "FAIL" if (
        gaps or duplicates or not v_streams
        or (duration_diff is not None and duration_diff > DURATION_TOLERANCE_SEC)
    ) else "PASS"

    out_path = project.root / "render_qc.json"
    out_path.write_text(json.dumps(qc, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(qc, ensure_ascii=False, indent=2))

    if qc["status"] == "FAIL":
        fail(f"Visual QC FAIL (см. {out_path})")
    print(f"\nVisual QC PASS -> {out_path}")


if __name__ == "__main__":
    main()
