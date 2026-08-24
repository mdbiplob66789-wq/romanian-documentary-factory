#!/usr/bin/env python3
"""
scripts/build_audio.py --project video_002

Generic audio-мастеринг (п.10-18 ТЗ). Читает music_map.json + aligned_timeline.json
(таймкоды музыкальных блоков уже разрешены по тексту диктора в align_project.py) —
никаких хардкоженых секунд, никакого "shot 1-40" и т.п.

Правила (п.12, неизменны, не читаются из music_map, чтобы их нельзя было переопределить):
  voice_target_lufs   = -14
  music_below_voice_db = -23  (т.е. музыка нормализуется к voice_target + music_below = -37 LUFS)
  ducking_enabled     = False
  Единственные разрешённые изменения уровня музыки целиком — intro fade-in (6s) и
  outro fade-out (10s). Никаких events/ducking/boost/hard cut.

Кроссфейд между блоками — equal-power (qsin/qsin), длина по умолчанию из music_map
(60s по regulation), реализован через построение каждого сегмента длиннее номинала
на crossfade_sec и цепочку acrossfade — итоговая длина музыкальной подложки точно
равна сумме номинальных длительностей блоков (= общей длительности voiceover).

Видео не перекодируется (-c:v copy). Аудио на выходе — AAC 256k.
"""

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from asset_pipeline.project import (
    DUCKING_ENABLED, INTRO_FADE_SEC, MUSIC_BELOW_VOICE_DB, OUTRO_FADE_SEC,
    ProjectError, VOICE_TARGET_LUFS, load_project,
)
MIN_BLOCK_DURATION_SEC = 240  # п.15: min_duration_sec для трека, до зацикливания


def fail(msg: str, code: int = 1):
    print(f"\nОШИБКА: {msg}", file=sys.stderr)
    sys.exit(code)


def run(cmd: list[str]) -> subprocess.CompletedProcess:
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        fail(f"Команда не прошла:\n{' '.join(cmd)}\n{r.stderr[-2000:]}")
    return r


def ffprobe_json(path: Path) -> dict:
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(path)],
        capture_output=True, text=True,
    )
    if r.returncode != 0:
        fail(f"ffprobe не смог прочитать {path}: {r.stderr.strip()}")
    return json.loads(r.stdout)


def validate_music_file(path: Path):
    """п.15: file exists / audio readable / duration / sample rate / channels."""
    if not path.exists():
        fail(f"Музыкальный файл отсутствует: {path}")
    info = ffprobe_json(path)
    audio_streams = [s for s in info.get("streams", []) if s.get("codec_type") == "audio"]
    if not audio_streams:
        fail(f"В файле нет аудиопотока: {path}")
    duration = float(info["format"].get("duration", 0))
    if duration <= 0:
        fail(f"Некорректная длительность аудио: {path}")
    return {
        "duration": duration,
        "sample_rate": int(audio_streams[0].get("sample_rate", 0)),
        "channels": int(audio_streams[0].get("channels", 0)),
    }


def loop_to_length(src: Path, target_seconds: float, dst: Path):
    """Бесшовный сшив трека до нужной длины (loopable=true, п.15) — без щелчка/паузы."""
    run([
        "ffmpeg", "-y", "-stream_loop", "-1", "-i", str(src),
        "-t", f"{target_seconds:.3f}",
        "-vn", "-ar", "48000", "-ac", "2",
        str(dst),
    ])


def loudnorm_to(src: Path, target_lufs: float, dst: Path):
    """Однопроходный loudnorm — музыка/голос всегда приводятся к фиксированному уровню
    относительно друг друга (voice=-14, music=-37), а не к громкости исходного файла."""
    run([
        "ffmpeg", "-y", "-i", str(src),
        "-af", f"loudnorm=I={target_lufs}:TP=-1.5:LRA=11",
        "-ar", "48000", "-ac", "2",
        str(dst),
    ])


def build_music_bed(project, timeline: dict, music_map: dict, work: Path) -> Path:
    blocks = timeline.get("music_blocks", [])
    if not blocks:
        fail("aligned_timeline.json не содержит music_blocks — запустите align_project.py с music_map.json.")

    crossfade_default = float(music_map.get("crossfade_sec", 60))
    music_target_lufs = VOICE_TARGET_LUFS + MUSIC_BELOW_VOICE_DB  # -14 + (-23) = -37

    segments = []
    for i, block in enumerate(blocks):
        src = project.music_dir / block["file"]
        info = validate_music_file(src)
        if info["duration"] < MIN_BLOCK_DURATION_SEC:
            print(f"  {block['file']}: {info['duration']:.1f}s < {MIN_BLOCK_DURATION_SEC}s min — будет зациклен бесшовно.")

        nominal = block["end"] - block["start"]
        cf = float(block.get("crossfade_sec", crossfade_default)) if i < len(blocks) - 1 else 0.0
        segment_len = nominal + cf

        looped = work / f"block_{i:02d}_looped.wav"
        loop_to_length(src, segment_len, looped)

        normed = work / f"block_{i:02d}_normed.wav"
        loudnorm_to(looped, music_target_lufs, normed)
        segments.append((normed, cf))

    # Цепочка equal-power crossfade: результат сохраняет постоянную воспринимаемую громкость
    # на стыках (qsin/qsin), суммарная длина = сумма номинальных длительностей блоков.
    current = segments[0][0]
    for i in range(1, len(segments)):
        cf = segments[i - 1][1]
        nxt = segments[i][0]
        merged = work / f"music_merge_{i:02d}.wav"
        run([
            "ffmpeg", "-y", "-i", str(current), "-i", str(nxt),
            "-filter_complex", f"[0:a][1:a]acrossfade=d={cf:.3f}:curve1=qsin:curve2=qsin",
            str(merged),
        ])
        current = merged

    intro_sec = float(music_map.get("intro_fade_sec", INTRO_FADE_SEC))
    outro_sec = float(music_map.get("outro_fade_sec", OUTRO_FADE_SEC))
    total_duration = sum(b["end"] - b["start"] for b in blocks)

    bed = work / "music_bed_final.wav"
    # Единственные допустимые изменения уровня музыки целиком: intro/outro fade (п.14).
    run([
        "ffmpeg", "-y", "-i", str(current),
        "-af", f"afade=t=in:st=0:d={intro_sec},afade=t=out:st={max(0, total_duration - outro_sec):.3f}:d={outro_sec}",
        str(bed),
    ])
    return bed


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
        fail(f"Нет visual master: {visual_master}. Сначала render_video.py --project {project.id}")

    if not project.aligned_timeline_path.exists():
        fail(f"Нет aligned_timeline.json — сначала align_shots.py --project {project.id}")
    timeline = json.loads(project.aligned_timeline_path.read_text(encoding="utf-8"))

    if not project.music_map_path.exists():
        fail(f"Нет music_map.json: {project.music_map_path}")
    music_map = json.loads(project.music_map_path.read_text(encoding="utf-8"))

    assert DUCKING_ENABLED is False, "ducking must stay OFF по регламенту (п.12 ТЗ)"

    with tempfile.TemporaryDirectory(prefix=f"build_audio_{project.id}_") as tmp:
        work = Path(tmp)

        print(f"== Музыкальная подложка ({len(timeline.get('music_blocks', []))} блока(ов)) ==")
        music_bed = build_music_bed(project, timeline, music_map, work)

        print("== Голос: извлечение и нормализация к", VOICE_TARGET_LUFS, "LUFS ==")
        voice_raw = work / "voice_raw.wav"
        run(["ffmpeg", "-y", "-i", str(visual_master), "-vn", "-ar", "48000", "-ac", "2", str(voice_raw)])
        voice_normed = work / "voice_normed.wav"
        loudnorm_to(voice_raw, VOICE_TARGET_LUFS, voice_normed)

        print("== Микс voice + music (без ducking, без sidechaincompress) ==")
        mixed = work / "mixed.wav"
        run([
            "ffmpeg", "-y", "-i", str(voice_normed), "-i", str(music_bed),
            "-filter_complex", "[0:a][1:a]amix=inputs=2:duration=first:normalize=0,alimiter=limit=0.97:attack=5:release=50",
            str(mixed),
        ])

        project.output_dir.mkdir(parents=True, exist_ok=True)
        final_path = project.final_master_path
        print(f"== Финальная сборка: video (copy) + AAC 256k -> {final_path.name} ==")
        run([
            "ffmpeg", "-y", "-i", str(visual_master), "-i", str(mixed),
            "-map", "0:v:0", "-map", "1:a:0",
            "-c:v", "copy", "-c:a", "aac", "-b:a", "256k",
            str(final_path),
        ])

    print(f"\nOK: {final_path}")


if __name__ == "__main__":
    main()
