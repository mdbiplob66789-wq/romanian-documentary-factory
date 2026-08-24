# Romanian Documentary Factory

Производство документальных видео: генерация кадров → выравнивание речи →
монтаж/motion → музыка → QC → Google Drive. Внешний сервис — NordRouter
(генерация изображений). Рендер/монтаж — GitHub Actions (Remotion), запускается
через `workflow_dispatch`.

## video_002 и далее (production pipeline)

```bash
# Новый проект
python scripts/new_project.py video_004

# Заполните projects/video_004/map.json, music_map.json, voiceover.mp3, music/

# Загрузка кадра/референса
python scripts/upload_asset.py image.png --project video_004 --next
python scripts/upload_asset.py ref.png --project video_004 --reference character --name main_character

# Проверка готовности
python scripts/check_project.py --project video_004

# Рендер — запускает GitHub Actions (render-project job), не рендерит локально
python scripts/render_project.py video_004

# Статус
python scripts/project_status.py video_004
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

### Visual render: Remotion (через GitHub Actions)
`render-project` job: align_project.py (openai-whisper) → stage_remotion.py
(снимает project_id-префикс во временный `public/shots/`) → Remotion render →
`projects/<id>/work/<id>_visual_master.mp4`. Motion (zoom/pan/static) — в
`src/Root.jsx`, читает aligned_timeline через `getInputProps()`.

В репозитории также лежит альтернативный local-first вариант на ffmpeg +
faster-whisper (`align_shots.py`, `render_video.py`, `generate_project.py`,
`build_project.py`, `run_project.py`) — рабочий и протестированный, но **не
используется по умолчанию** (см. `render.yml`), т.к. было решено вернуться на
Remotion. Ничего не удалено, доступно при необходимости.

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

Отдельный пайплайн: 160 кадров `shot_NNN.jpg/png` в корне репозитория,
`ElevenLabs_Kuki_combined.mp3`, карта шотов зашита в `scripts/align_final.py`, музыка —
3 блока из Drive, `build_audio_video001.py`. Рендер — тот же workflow **Render
documentary** с пустым `project_id`.

## GitHub Actions

`.github/workflows/render.yml`, `workflow_dispatch` с полем `project_id`:
- пусто → `render-legacy` (video_001, без изменений)
- `video_002` и т.п. → `render-project` (тот же стек, что и legacy: Remotion +
  openai-whisper), полностью через CI.
