# Romanian Documentary Factory

Automated Remotion renderer for the Romanian long-form documentary channel.

## Render pipeline

1. Put generated images in `public/assets/images/` as `shot_001.jpg`, `shot_002.jpg`, etc.
2. Put narration at `public/assets/audio/voiceover.mp3`.
3. Put background music in `public/assets/music/`.
4. Update `src/edit-plan.json` with shot timing, motion and music cues.
5. Run the GitHub Actions workflow **Render documentary**.
6. Download the `final-video` artifact.

The current renderer supports:
- shot-specific timing
- `static`, `slow_zoom_in`, `slow_zoom_out`, `slow_pan_left`, `slow_pan_right`
- soft per-shot fades
- narration
- multiple background-music beds with independent timing and volume
- 1920x1080, 30fps MP4 output

No subtitles are rendered.
