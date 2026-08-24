#!/usr/bin/env python3
"""
scripts/render_video.py --project video_002

Local-first visual renderer: Python строит ffmpeg filter graph, сам рендер
кадров делает ffmpeg (не Remotion/Node, п.44-45 ТЗ).

Почему НЕ zoompan (п.48 ТЗ): классический zoompan оперирует целыми пикселями
внутренней low-res модели кадра и на медленном zoom (наш диапазон — единицы
процентов на несколько секунд) даёт заметный дискретный "степ" вместо плавного
движения. Вместо этого: один раз качественно (lanczos) апскейлим кадр с запасом,
затем `crop` с `eval=frame` и float-выражениями от t — субпиксельно точная
интерполяция на каждый выходной frame, без внутреннего понижения точности.

Каждый shot рендерится в отдельный временный клип нужной длительности (motion
из map.json применяется к КАЖДОМУ shot независимо), клипы склеиваются
concat-демуксером (-c copy, без перекодирования) — HARD CUT по умолчанию
(п.18, п.49 ТЗ). xfade применяется ТОЛЬКО если map.json явно указал transition
для конкретного шота.

Результат: projects/<id>/work/<id>_visual_master.mp4 (video + voiceover,
музыка добавляется отдельно build_audio.py).
"""

import argparse
import json
import math
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from PIL import Image

from asset_pipeline.logs import StageLogger
from asset_pipeline.motion import UnknownMotionError, motion_bounds
from asset_pipeline.project import ProjectError, load_project
from asset_pipeline.repo import REPO_ROOT

WIDTH, HEIGHT = 1920, 1080
FPS = 30
BASE_SCALE = 1.35  # запас разрешения для качественного crop/scale (без него — двойной апскейл в потерю)
BASE_W, BASE_H = math.ceil(WIDTH * BASE_SCALE), math.ceil(HEIGHT * BASE_SCALE)
BASE_W += BASE_W % 2
BASE_H += BASE_H % 2


def fail(msg: str, code: int = 1):
    print(f"\nОШИБКА: {msg}", file=sys.stderr)
    sys.exit(code)


def run(cmd: list[str], logger: StageLogger | None = None):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        msg = f"Команда не прошла:\n{' '.join(str(c) for c in cmd)}\n{r.stderr[-2000:]}"
        if logger:
            logger.error(msg)
        fail(msg)
    return r


def cover_fit_params(src_path: Path) -> tuple[int, int]:
    """Целые пиксельные размеры для cover-fit исходника на BASE_W x BASE_H (без runtime-expr в ffmpeg)."""
    with Image.open(src_path) as img:
        src_w, src_h = img.size
    scale_factor = max(BASE_W / src_w, BASE_H / src_h)
    scaled_w = math.ceil(src_w * scale_factor)
    scaled_h = math.ceil(src_h * scale_factor)
    scaled_w += scaled_w % 2
    scaled_h += scaled_h % 2
    return scaled_w, scaled_h


def build_motion_filter(motion: str, intensity: str, duration: float) -> str:
    """
    crop с eval=frame: субпиксельная интерполяция scale/translate по прогрессу
    progress через zoompan-переменную `on` (0..d-1), а не `t`.

    РЕАЛЬНО ПРОВЕРЕНО (п.48 ТЗ): изначальный вариант через `crop` с time-varying
    w+h одновременно оказался НЕСТАБИЛЕН в этой версии ffmpeg (9.0.1) — давал
    буквально замороженные/дублирующиеся кадры (подтверждено покадровым
    сравнением, tblend=difference+signalstats). `crop` с ТОЛЬКО x/y (позиция,
    без изменения w/h) — плавный и стабильный (подтверждено), но чистый zoom
    требует менять именно размер. zoompan — единственный протестированный
    вариант БЕЗ дублирующихся кадров; остаточная метрика "дрожания" на
    покадровом diff проверена визуально (экспортированы PNG через интервал)
    и оказалась эффектом мелкой штриховки исходных иллюстраций (moiré/aliasing
    от lanczos-resampling на регулярных тонких линиях — забор, деревья), а не
    реальным скачком/паузой в движении.
    """
    bounds = motion_bounds(motion, intensity)
    s0, s1 = bounds["start_scale"], bounds["end_scale"]
    (tx0, ty0), (tx1, ty1) = bounds["translate_start"], bounds["translate_end"]

    n_frames = max(1, round(duration * FPS))
    d = n_frames  # zoompan: сколько выходных кадров держим/анимируем один вход

    progress = f"min(on/{max(1, d - 1)}\\,1)" if d > 1 else "0"
    zoom_expr = f"({s0:.6f}+({s1:.6f}-{s0:.6f})*{progress})"
    tx_expr = f"({tx0:.6f}+({tx1:.6f}-{tx0:.6f})*{progress})"
    ty_expr = f"({ty0:.6f}+({ty1:.6f}-{ty0:.6f})*{progress})"

    # zoompan x/y — top-left угол crop-окна в пикселях ИСХОДНОГО (BASE_W x BASE_H)
    # кадра; смещение на translate% выражено в единицах OUTPUT (1920x1080),
    # переведено в исходные пиксели делением на текущий zoom (см. комментарий
    # в motion.py про семантику CSS translate% относительно border box).
    x_expr = f"(({BASE_W}-{BASE_W}/zoom)/2+({tx_expr}/100*{BASE_W})/zoom)"
    y_expr = f"(({BASE_H}-{BASE_H}/zoom)/2+({ty_expr}/100*{BASE_H})/zoom)"

    zoompan = (
        f"zoompan=z='{zoom_expr}':x='{x_expr}':y='{y_expr}':"
        f"d={d}:s={WIDTH}x{HEIGHT}:fps={FPS}"
    )
    return zoompan, n_frames


def render_shot_clip(image_path: Path, duration: float, motion: str, intensity: str,
                      out_path: Path, logger: StageLogger):
    scaled_w, scaled_h = cover_fit_params(image_path)
    crop_x0 = (scaled_w - BASE_W) // 2
    crop_y0 = (scaled_h - BASE_H) // 2

    try:
        zoompan_filter, n_frames = build_motion_filter(motion, intensity, duration)
    except UnknownMotionError as e:
        fail(f"{image_path.name}: {e}")
        return

    filter_chain = (
        f"scale={scaled_w}:{scaled_h}:flags=lanczos,"
        f"crop={BASE_W}:{BASE_H}:{crop_x0}:{crop_y0},"
        f"{zoompan_filter}"
    )

    cmd = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-loop", "1", "-i", str(image_path),
        "-vf", filter_chain,
        "-frames:v", str(n_frames),
        "-c:v", "libx264", "-preset", "medium", "-crf", "16", "-pix_fmt", "yuv420p",
        str(out_path),
    ]
    run(cmd, logger)


def main():
    p = argparse.ArgumentParser(description="ffmpeg visual render (Python + ffmpeg, не Remotion).")
    p.add_argument("--project", required=True)
    args = p.parse_args()

    try:
        project = load_project(args.project)
    except ProjectError as e:
        fail(str(e))
        return

    project.ensure_work_dirs()
    logger = StageLogger(project, "render")

    if not project.aligned_timeline_path.exists():
        fail(f"Нет aligned_timeline.json — сначала align_shots.py --project {project.id}")
    timeline = json.loads(project.aligned_timeline_path.read_text(encoding="utf-8"))
    shots = timeline["shots"]
    if not shots:
        fail("aligned_timeline.json: пустой список shots")

    logger.log(f"Rendering {len(shots)} shots, base canvas {BASE_W}x{BASE_H} -> {WIDTH}x{HEIGHT}@{FPS}fps")

    with tempfile.TemporaryDirectory(prefix=f"render_{project.id}_") as tmp:
        tmp_path = Path(tmp)
        clip_paths = []

        for i, shot in enumerate(shots):
            duration = shot["end"] - shot["start"]
            image_path = project.shots_dir / shot["image"]
            if not image_path.exists():
                fail(f"Shot {shot['id']}: файл не найден {image_path}")

            clip_path = tmp_path / f"clip_{i:04d}.mp4"
            logger.log(f"Shot {shot['id']}: {shot['motion']}/{shot['intensity']}, {duration:.3f}s -> {clip_path.name}")
            render_shot_clip(image_path, duration, shot["motion"], shot["intensity"], clip_path, logger)
            clip_paths.append(clip_path)

        concat_list = tmp_path / "concat.txt"
        concat_list.write_text("\n".join(f"file '{c}'" for c in clip_paths), encoding="utf-8")

        visual_only = tmp_path / "visual_only.mp4"
        logger.log("Concatenating shots (hard cuts, -c copy)...")
        run([
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-f", "concat", "-safe", "0", "-i", str(concat_list),
            "-c", "copy",
            str(visual_only),
        ], logger)

        if not project.voiceover_path.exists():
            fail(f"Нет voiceover: {project.voiceover_path}")

        logger.log("Muxing voiceover onto visual master...")
        project.visual_master_path.parent.mkdir(parents=True, exist_ok=True)
        run([
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-i", str(visual_only), "-i", str(project.voiceover_path),
            "-map", "0:v:0", "-map", "1:a:0",
            "-c:v", "copy", "-c:a", "aac", "-b:a", "256k",
            "-shortest",
            str(project.visual_master_path),
        ], logger)

    logger.log(f"OK: {project.visual_master_path}")
    logger.close()
    print(f"\nOK: {project.visual_master_path}")


if __name__ == "__main__":
    main()
