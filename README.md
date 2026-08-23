# Romanian Documentary Factory

Автоматизированное производство документальных видео: ассеты → выравнивание по
голосу → Remotion → музыка → QC → Google Drive.

## video_002 и далее (production pipeline)

```bash
# Новый проект
python scripts/new_project.py video_004

# Загрузка шота (автонумерация)
python scripts/upload_asset.py image.png --project video_004 --next

# Reference
python scripts/upload_asset.py ref.png \
  --project video_004 \
  --reference character \
  --name main_character

# Проверка готовности
python scripts/check_project.py --project video_004

# Рендер (запускает GitHub Actions, не рендерит локально)
python scripts/render_project.py video_004

# Статус
python scripts/project_status.py video_004
```

После `new_project.py` заполните в `projects/<id>/`:
`map.json` (шоты: SHOT/START_TEXT/END_TEXT/MOTION/INTENSITY),
`music_map.json` (блоки музыки: start_text/file/mood/...),
`voiceover.mp3`, и файлы в `music/` (`block_01.mp3`, `block_02.mp3`, ...).

Watch-режим (авто-загрузка новых файлов из `~/UrmeReci/inbox/<project>/`):
```bash
python scripts/watch_assets.py --project video_004
```

### Canonical naming (обязателен для video_002+)
```
projects/<id>/shots/<id>_shot_017.jpg
projects/<id>/references/character/<id>_ref_character_main_character.png
```
Нумерация и references всегда локальны внутри `project_id` — video_002 и video_003
никогда не пересекаются.

### Правила музыки (фиксированы, не переопределяются)
- голос: -14 LUFS, музыка: -20 dB относительно голоса
- ducking выключен, sidechain запрещён, резких подъёмов/провалов нет
- переход между блоками — 60 сек equal-power crossfade
- intro fade-in 6 сек, outro fade-out 10 сек — единственные разрешённые изменения общего уровня

### Итог: `out/<id>_FINAL_YOUTUBE.mp4` → `gdrive:URME_RECI/<id>/<id>_FINAL_YOUTUBE.mp4`

## video_001 (legacy)

Отдельный, не изменяемый пайплайн: 160 кадров `shot_NNN.jpg/png` в корне репозитория,
`ElevenLabs_Kuki_combined.mp3`, карта шотов зашита в `scripts/align_final.py`, музыка —
3 блока, загружаемые из Drive и собираемые `build_audio_video001.py`. Рендер запускается
через тот же workflow **Render documentary** с пустым `project_id`.

## Workflow

`.github/workflows/render.yml`, `workflow_dispatch` с полем `project_id`:
- пусто → `render-legacy` (video_001, без изменений)
- `video_002` и т.п. → `render-project` (полный generic пайплайн, п.23)
