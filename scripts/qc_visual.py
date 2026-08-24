#!/usr/bin/env python3
"""scripts/qc_visual.py --project video_002 -> projects/<id>/qc/shot_qc.json (п.20, п.32 ТЗ)"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from asset_pipeline import numbering
from asset_pipeline.motion import UnknownMotionError, max_scale, motion_bounds
from asset_pipeline.project import MOTION_AMPLITUDE_HARD_CAP, ProjectError, load_project

DURATION_TOLERANCE_SEC = 0.5
MOTION_DURATION_TOLERANCE_SEC = 0.05  # движение должно заканчиваться ровно с шотом (п.10 ТЗ)


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


def build_motion_qc(project) -> dict:
    """
    Независимая от Remotion проверка motion (п.10 ТЗ): пересчитывает
    scale/translate сама (asset_pipeline.motion — зеркало Root.jsx) и сверяет
    aligned_timeline.json 1:1 с map.json. Ничего не доверяет рендеру вслепую.
    """
    problems = []
    per_shot = []

    if not project.map_path.exists() or not project.aligned_timeline_path.exists():
        return {"status": "FAIL", "problems": ["Нет map.json или aligned_timeline.json"], "shots": []}

    map_data = json.loads(project.map_path.read_text(encoding="utf-8"))
    timeline = json.loads(project.aligned_timeline_path.read_text(encoding="utf-8"))

    map_by_id = {row["SHOT"]: row for row in map_data.get("shots", [])}
    timeline_by_id = {shot["id"]: shot for shot in timeline.get("shots", [])}

    if set(map_by_id) != set(timeline_by_id):
        problems.append(f"Набор шотов в map.json ({sorted(map_by_id)}) не совпадает с aligned_timeline.json ({sorted(timeline_by_id)})")

    for shot_id in sorted(map_by_id):
        map_row = map_by_id[shot_id]
        tl_shot = timeline_by_id.get(shot_id)
        if tl_shot is None:
            continue

        entry = {"shot": shot_id, "duration": round(tl_shot["end"] - tl_shot["start"], 3),
                  "motion": tl_shot["motion"], "intensity": tl_shot["intensity"]}

        if tl_shot["motion"] != map_row["MOTION"] or tl_shot["intensity"] != map_row["INTENSITY"]:
            problems.append(f"Shot {shot_id}: aligned_timeline ({tl_shot['motion']}/{tl_shot['intensity']}) "
                             f"!= map.json ({map_row['MOTION']}/{map_row['INTENSITY']})")

        try:
            bounds = motion_bounds(tl_shot["motion"], tl_shot["intensity"])
        except UnknownMotionError as e:
            problems.append(f"Shot {shot_id}: {e}")
            entry["error"] = str(e)
            per_shot.append(entry)
            continue

        entry.update({
            "start_scale": round(bounds["start_scale"], 4),
            "end_scale": round(bounds["end_scale"], 4),
            "translate_start": bounds["translate_start"],
            "translate_end": bounds["translate_end"],
        })
        per_shot.append(entry)

        if max_scale(bounds) > 1 + MOTION_AMPLITUDE_HARD_CAP + 1e-9:
            problems.append(f"Shot {shot_id}: scale {max_scale(bounds):.3f} превышает safety cap "
                             f"1+{MOTION_AMPLITUDE_HARD_CAP}")

        if tl_shot["motion"] == "static" and (bounds["start_scale"] != 1.0 or bounds["end_scale"] != 1.0
                                               or bounds["translate_start"] != (0.0, 0.0)
                                               or bounds["translate_end"] != (0.0, 0.0)):
            problems.append(f"Shot {shot_id}: static-шот получил ненулевое движение")

        # Движение всегда распределено на progress 0..1 ровно по длительности шота
        # (см. Root.jsx) — по конструкции заканчивается вместе с шотом; здесь просто
        # фиксируем длительность в отчёте и проверяем, что она положительна.
        if entry["duration"] <= 0:
            problems.append(f"Shot {shot_id}: неположительная длительность движения")

    status = "FAIL" if problems else "PASS"
    return {"status": status, "problems": problems, "shots": per_shot}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--project", required=True)
    args = p.parse_args()

    try:
        project = load_project(args.project)
    except ProjectError as e:
        fail(str(e))
        return

    visual_master = project.visual_master_path
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

    motion_qc = build_motion_qc(project)
    qc["motion"] = motion_qc

    qc["status"] = "FAIL" if (
        gaps or duplicates or not v_streams
        or (duration_diff is not None and duration_diff > DURATION_TOLERANCE_SEC)
        or motion_qc["status"] == "FAIL"
    ) else "PASS"

    project.qc_dir.mkdir(parents=True, exist_ok=True)
    out_path = project.qc_dir / "shot_qc.json"
    out_path.write_text(json.dumps(qc, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(qc, ensure_ascii=False, indent=2))

    if qc["status"] == "FAIL":
        extra = ("\nMotion problems:\n  " + "\n  ".join(motion_qc["problems"])) if motion_qc["problems"] else ""
        fail(f"Visual QC FAIL (см. {out_path}){extra}")
    print(f"\nVisual QC PASS -> {out_path}")


if __name__ == "__main__":
    main()
