#!/usr/bin/env python3
"""
scripts/align_project.py --project video_002

Generic-версия align_final.py (алгоритм анкоринга — тот же самый, проверенный на video_001:
SequenceMatcher + монотонный курсор по словам Whisper), но:
  - map.json и music_map.json — внешние файлы проекта, а не blob внутри скрипта;
  - один проход Whisper используется и для шотов, и для музыкальных блоков (п.11 ТЗ);
  - результат — projects/<id>/aligned_timeline.json + alignment_report.json
    (НЕ src/aligned_timeline.json — тот файл трогает только legacy video_001 пайплайн).

QC (жёстко, без || true): anchor не найден / confidence ниже порога / timeline
не монотонен / duration <= 0 / дубли anchor-текста -> RuntimeError, ненулевой exit,
render дальше не идёт.
"""

import argparse
import json
import re
import subprocess
import sys
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from asset_pipeline.project import ProjectError, load_project
from asset_pipeline.shot_validation import ShotValidationError, validate_shots

MIN_SHOT_CONFIDENCE = 0.48
MIN_MUSIC_CONFIDENCE = 0.42
VALID_MOTIONS = {"static", "zoom_in", "zoom_out", "pan_left", "pan_right"}
VALID_INTENSITIES = {"low", "medium"}


def fail(msg: str, code: int = 1):
    print(f"\nОШИБКА: {msg}", file=sys.stderr)
    sys.exit(code)


def norm_tokens(s: str) -> list[str]:
    s = "".join(c for c in unicodedata.normalize("NFKD", s.lower()) if not unicodedata.combining(c))
    s = s.replace("ş", "s").replace("ș", "s").replace("ţ", "t").replace("ț", "t")
    return re.findall(r"[a-z0-9]+", s)


def audio_duration(path: Path) -> float:
    p = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(path)],
        capture_output=True, text=True,
    )
    if p.returncode != 0:
        raise RuntimeError(f"ffprobe не смог прочитать {path}: {p.stderr.strip()}")
    return float(p.stdout.strip())


def transcribe(audio_path: Path, language: str) -> list[dict]:
    import whisper  # тяжёлый импорт — только когда реально нужен
    model = whisper.load_model("small")
    result = model.transcribe(str(audio_path), language=language, word_timestamps=True, fp16=False,
                               condition_on_previous_text=True)
    words = []
    for seg in result["segments"]:
        for w in seg.get("words", []):
            t = norm_tokens(w.get("word", ""))
            if t:
                words.append({"raw": w["word"], "norm": t[0], "start": float(w["start"]), "end": float(w["end"])})
    if len(words) < 20:
        raise RuntimeError(f"Whisper вернул подозрительно мало слов ({len(words)}) — проверьте voiceover/language.")
    return words


def score(anchor: str, words: list[dict], i: int, n: int) -> float:
    a = " ".join(norm_tokens(anchor))
    b = " ".join(w["norm"] for w in words[i:i + n])
    return SequenceMatcher(None, a, b).ratio()


def find_anchor(anchor: str, words: list[dict], cursor: int) -> tuple[int, float]:
    toks = norm_tokens(anchor)
    n = max(1, len(toks))
    lo = max(0, cursor - 2)
    hi = min(len(words), cursor + 220)
    best = None
    for i in range(lo, hi):
        for d in range(-3, 4):
            nn = max(1, n + d)
            s = score(anchor, words, i, nn) - 0.0007 * max(0, i - cursor)
            if best is None or s > best[0]:
                best = (s, i)
    raw = best[0] + 0.0007 * max(0, best[1] - cursor)
    return best[1], raw


def resolve_sequential_anchors(items: list[dict], words: list[dict], min_confidence: int, label: str) -> list[dict]:
    """
    Общий движок анкоринга для шотов И музыкальных блоков — курсор монотонно идёт
    вперёд по словам, что само по себе гарантирует uniqueness/monotonic (п.4, п.11 ТЗ).
    items: список dict с ключом 'start_text'.
    """
    seen_texts = set()
    results = []
    cursor = 0
    for item in items:
        text = item["start_text"]
        if text in seen_texts:
            raise RuntimeError(f"[{label}] Дублирующийся anchor-текст (не уникален): '{text[:60]}'")
        seen_texts.add(text)

        idx, conf = find_anchor(text, words, cursor)
        if conf < min_confidence:
            raise RuntimeError(f"[{label}] Anchor не найден с достаточной уверенностью ({conf:.3f} < {min_confidence}): '{text[:60]}'")

        t = words[idx]["start"]
        if results and t <= results[-1]["time"]:
            raise RuntimeError(f"[{label}] Timeline перескакивает назад на '{text[:60]}' ({t} <= {results[-1]['time']})")

        results.append({**item, "time": t, "confidence": round(conf, 4), "word_index": idx})
        cursor = max(cursor + 1, idx)
    return results


def main():
    p = argparse.ArgumentParser(description="Выравнивание озвучки проекта по map.json/music_map.json.")
    p.add_argument("--project", required=True)
    args = p.parse_args()

    try:
        project = load_project(args.project)
    except ProjectError as e:
        fail(str(e))
        return

    if not project.map_path.exists():
        fail(f"Нет map.json: {project.map_path}")
    if not project.voiceover_path.exists():
        fail(f"Нет voiceover: {project.voiceover_path}")

    try:
        map_data = json.loads(project.map_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        fail(f"map.json невалиден: {e}")
        return

    shots_plan = map_data.get("shots", [])
    if not shots_plan:
        fail("map.json не содержит shots[]")

    for row in shots_plan:
        if row.get("MOTION") not in VALID_MOTIONS:
            fail(f"Shot {row.get('SHOT')}: недопустимый MOTION={row.get('MOTION')!r}. Допустимо: {sorted(VALID_MOTIONS)}")
        if row.get("INTENSITY") not in VALID_INTENSITIES:
            fail(f"Shot {row.get('SHOT')}: недопустимый INTENSITY={row.get('INTENSITY')!r}. Допустимо: {sorted(VALID_INTENSITIES)}")

    # 1. Валидация реальных файлов шотов ДО alignment (п.5 ТЗ) — только этот project_id.
    try:
        manifest = validate_shots(project, expected_count=len(shots_plan))
    except ShotValidationError as e:
        fail(str(e))
        return

    music_map = {}
    if project.music_map_path.exists():
        try:
            music_map = json.loads(project.music_map_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            fail(f"music_map.json невалиден: {e}")
            return

    ad = audio_duration(project.voiceover_path)
    print(f"voiceover={ad:.3f}s shots={len(shots_plan)} language={project.language}")

    words = transcribe(project.voiceover_path, project.language)
    print(f"Whisper: {len(words)} слов распознано")

    # 2. Anchors для шотов
    shot_items = [{"start_text": row["START_TEXT"], "row": row} for row in shots_plan]
    try:
        shot_matches = resolve_sequential_anchors(shot_items, words, MIN_SHOT_CONFIDENCE, "shots")
    except RuntimeError as e:
        fail(str(e))
        return

    # END_TEXT (если задан) — необязательная сверочная проверка (п.4 ТЗ, "при необходимости").
    for i, row in enumerate(shots_plan):
        end_text = row.get("END_TEXT")
        if not end_text:
            continue
        idx, conf = find_anchor(end_text, words, shot_matches[i]["word_index"])
        if conf < MIN_SHOT_CONFIDENCE:
            fail(f"Shot {row['SHOT']}: END_TEXT не подтверждается транскриптом (conf={conf:.3f}): '{end_text[:60]}'")
        end_time = words[idx]["start"]
        next_start = shot_matches[i + 1]["time"] if i + 1 < len(shot_matches) else ad
        if end_time > next_start + 0.75:
            fail(f"Shot {row['SHOT']}: END_TEXT ({end_time:.2f}s) находится ПОСЛЕ начала следующего шота ({next_start:.2f}s) — карта противоречива.")

    shots_out = []
    for i, row in enumerate(shots_plan):
        st = max(0.0, shot_matches[i]["time"])
        en = shot_matches[i + 1]["time"] if i + 1 < len(shot_matches) else ad
        if en <= st:
            fail(f"Shot {row['SHOT']}: неположительная длительность ({en - st:.3f}s)")
        shots_out.append({
            "id": row["SHOT"],
            "image": manifest[int(row["SHOT"])],
            "start": round(st, 3),
            "end": round(en, 3),
            "motion": row["MOTION"],
            "intensity": row["INTENSITY"],
        })

    # 3. Anchors для музыкальных блоков — тот же transcript, без повторного Whisper (п.11 ТЗ).
    music_blocks_out = []
    if music_map.get("blocks"):
        music_items = [{"start_text": b["start_text"], "block": b} for b in music_map["blocks"]]
        try:
            music_matches = resolve_sequential_anchors(music_items, words, MIN_MUSIC_CONFIDENCE, "music")
        except RuntimeError as e:
            fail(str(e))
            return

        for i, b in enumerate(music_map["blocks"]):
            st = music_matches[i]["time"]
            en = music_matches[i + 1]["time"] if i + 1 < len(music_matches) else ad
            if en <= st:
                fail(f"Music block '{b['file']}': неположительная длительность")
            music_blocks_out.append({
                "file": b["file"],
                "start": round(st, 3),
                "end": round(en, 3),
                "mood": b.get("mood"),
                "intensity": b.get("intensity"),
                "action": b.get("action"),
                "crossfade_sec": b.get("crossfade_sec", music_map.get("crossfade_sec", 60)),
            })

    payload = {
        "project_id": project.id,
        "audio_duration": round(ad, 3),
        "shots": shots_out,
        "music_blocks": music_blocks_out,
    }
    project.aligned_timeline_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    report = {
        "project_id": project.id,
        "audio_duration": ad,
        "word_count": len(words),
        "shot_count": len(shots_out),
        "min_shot_confidence": min(m["confidence"] for m in shot_matches),
        "shot_anchors": [{"shot": m["row"]["SHOT"], "anchor": m["start_text"], "time": m["time"], "confidence": m["confidence"]} for m in shot_matches],
        "music_block_count": len(music_blocks_out),
    }
    project.alignment_report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"QC PASS: {len(shots_out)} shots, {len(music_blocks_out)} music blocks, "
          f"min shot confidence {report['min_shot_confidence']:.3f}")


if __name__ == "__main__":
    main()
