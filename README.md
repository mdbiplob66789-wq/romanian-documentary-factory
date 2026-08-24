# Romanian Documentary Factory

Local-first производство документальных видео: генерация кадров → выравнивание
речи (faster-whisper) → монтаж и motion (ffmpeg) → музыка → QC → Google Drive.
Единственный внешний сервис — NordRouter (генерация изображений). Всё
остальное — офлайн, на вашем Mac.

## video_002 и далее (production pipeline, Python + ffmpeg + faster-whisper)

```bash
# Новый проект
python scripts/new_project.py video_004

# Заполните projects/video_004/map.json, music_map.json, voiceover.mp3, music/

# Генерация кадров через NordRouter прямо в canonical destination
python scripts/generate_project.py video_004 --commit
python scripts/generate_project.py video_004 --resume   # если сорвалось на середине

# Проверка готовности
python scripts/check_project.py --project video_004

# Полная локальная сборка одной командой (align -> render -> QC -> audio -> QC)
python scripts/build_project.py video_004

# Или полный цикл разом: генерация + сборка + загрузка на Drive
python scripts/run_project.py video_004 --generate-images --render --upload

# Статус
python scripts/project_status.py video_004
```

Ручная загрузка одного кадра/референса (если не через generate_project.py):
```bash
python scripts/upload_asset.py image.png --project video_004 --next
python scripts/upload_asset.py ref.png --project video_004 --reference character --name main_character
```

Watch-режим (опциональный fallback, авто-загрузка новых файлов из `~/UrmeReci/inbox/<project>/`):
```bash
python scripts/watch_assets.py --project video_004
```

### Canonical naming (обязателен для video_002+)
```
projects/<id>/shots/<id>_shot_017.jpg
projects/<id>/references/character/<id>_ref_character_main_character.png
```
Нумерация и references всегда локальны внутри `project_id`.

### Структура проекта
```
projects/<id>/
  project.json, map.json, music_map.json, voiceover.mp3, upload_state.json
  shots/ references/ music/     — ассеты (в git; music/*.mp3 — нет, см. storage strategy)
  work/    — aligned_timeline.json, visual_master.mp4 (не в git), state_hashes.json
  qc/      — shot_qc.json, audio_qc.json, final_qc.json (в git)
  output/  — <id>_FINAL_YOUTUBE.mp4 (не в git — доставляется на Drive)
  logs/    — generation/alignment/render/audio.log (не в git)
```

### Motion engine (ffmpeg, НЕ Remotion)
`render_video.py` строит per-shot `zoompan` (протестировано на нестабильность —
вариант через `crop` с одновременно меняющимися w+h в этой сборке ffmpeg давал
дублирующиеся кадры, zoompan — нет). Амплитуда: low 4%, medium 7%, hard cap 8%,
распределена на всю фактическую длительность шота. `static` — буквально без
движения. Pan — тот же движок, только x/y без изменения zoom. HARD CUT между
шотами по умолчанию (concat demuxer, `-c copy`), xfade — только если явно в map.json.

### Правила музыки (фиксированы, не переопределяются)
- голос: -14 LUFS, музыка: -23 dB относительно голоса (≈ -37 LUFS)
- ducking выключен, sidechain запрещён, резких подъёмов/провалов нет
- переход между блоками — 60 сек equal-power crossfade (по умолчанию)
- intro fade-in 6 сек, outro fade-out 10 сек — единственные разрешённые изменения общего уровня

### Storage strategy
В git: код, project.json/map.json/music_map.json, shots/, references/, qc/*.json,
work/*.json (hashes/state), upload_state.json. НЕ в git: music/*.mp3,
work/*.mp4 (промежуточный рендер), output/*.mp4 (финал — уходит на Drive), logs/.

### Итог: `projects/<id>/output/<id>_FINAL_YOUTUBE.mp4` → `gdrive:URME_RECI/<id>/<id>_FINAL_YOUTUBE.mp4`

## video_001 (legacy, не менялся)

Отдельный пайплайн на Remotion: 160 кадров `shot_NNN.jpg/png` в корне репозитория,
`ElevenLabs_Kuki_combined.mp3`, карта шотов зашита в `scripts/align_final.py`, музыка —
3 блока из Drive, `build_audio_video001.py`. Рендер — тот же workflow **Render
documentary** с пустым `project_id`.

## GitHub Actions

`.github/workflows/render.yml`, `workflow_dispatch` с полем `project_id`:
- пусто → `render-legacy` (video_001, Remotion, без изменений)
- `video_002` и т.п. → `render-project` (тот же local-first стек — ffmpeg +
  faster-whisper, БЕЗ Node/Remotion). Основной путь — локальный запуск на
  вашем Mac через `run_project.py`; CI — опциональный delivery/trigger layer.
