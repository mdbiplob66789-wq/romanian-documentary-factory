# Project layout

Each documentary lives in its own project folder so shot numbers can restart at `shot_001` without collisions.

```text
projects/
  video_001/
    project.json
  _template/
    project.json
    shots/
    music/
```

`video_001` is the existing production preserved in legacy-root mode to avoid moving or breaking the already rendered 160-shot documentary.

All new productions should use folders such as `projects/video_002/`, `projects/video_003/`, etc. A new project owns its own `shots/`, `voiceover.mp3`, `map.json`, and optional `music/` directory.

The render workflow receives a `project_id`. For `video_001`, legacy root assets remain supported. Future project assets never share names or paths with older projects.
