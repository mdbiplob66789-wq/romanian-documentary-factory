import json
import math
import subprocess
from pathlib import Path

ROOT = Path('.')
REPORT = ROOT / 'alignment_report.json'
VIDEO = ROOT / 'out' / 'final_video.mp4'
MUSIC_DIR = ROOT / 'music_assets'
OUT = ROOT / 'out' / 'final_video_with_music.mp4'

# Approved video_001 Claude music map.
# IMPORTANT: constant background level only. No ducking and no dramatic gain boosts.
BLOCKS = [
    (1, 1, 8, 'atlasaudio-drone-ambient-518685.mp3', 0),
    (2, 9, 27, 'mixkit-relax-658.mp3', 10),
    (3, 28, 40, 'mixkit-echoes-188.mp3', 8),
    (4, 41, 51, 'tunetank-dark-ambient-soundscape-music-409350.mp3', 10),
    (5, 52, 75, 'the_mountain-dark-documentary-165604.mp3', 12),
    (6, 76, 84, 'arpmedia-dark-tension-569513.mp3', 8),
    (7, 85, 94, 'atlasaudio-drone-ambient-518685.mp3', 28),
    (8, 95, 102, 'mixkit-relax-beat-292.mp3', 12),
    (9, 103, 127, 'mixkit-discover-587.mp3', 8),
    (10, 128, 149, 'the_mountain-dark-documentary-165604.mp3', 18),
    (11, 150, 158, 'mixkit-relax-658.mp3', 35),
    (12, 159, 160, 'atlasaudio-drone-ambient-518685.mp3', 0),
]

GAIN = 10 ** (-18 / 20)  # exactly -18 dB


def main():
    if not REPORT.exists():
        raise RuntimeError('Missing alignment_report.json')
    if not VIDEO.exists():
        raise RuntimeError('Missing out/final_video.mp4')

    rep = json.loads(REPORT.read_text(encoding='utf-8'))
    anchors = {int(a['shot']): float(a['time']) for a in rep['anchors']}
    audio_duration = float(rep['audio_duration'])

    required = sorted({filename for _, _, _, filename, _ in BLOCKS})
    missing = [name for name in required if not (MUSIC_DIR / name).exists()]
    if missing:
        raise RuntimeError('Missing music files: ' + ', '.join(missing))

    cmd = ['ffmpeg', '-y', '-hide_banner', '-loglevel', 'error', '-i', str(VIDEO)]
    for _, _, _, filename, _ in BLOCKS:
        cmd += ['-i', str(MUSIC_DIR / filename)]

    filters = []
    labels = []
    for idx, (block_no, start_shot, end_shot, filename, offset) in enumerate(BLOCKS, start=1):
        start = anchors[start_shot]
        end = anchors[end_shot + 1] if end_shot < 160 else audio_duration
        duration = end - start
        if duration <= 0:
            raise RuntimeError(f'Invalid music block duration: {block_no}')

        # Short fades are only for click-free transitions. The body of every block is fixed at -18 dB.
        fade = min(0.65, max(0.20, duration / 10))
        fade_out_start = max(0, duration - fade)
        delay_ms = int(round(start * 1000))
        label = f'm{block_no}'
        filters.append(
            f'[{idx}:a]atrim=start={offset:.3f}:duration={duration:.3f},'
            f'asetpts=PTS-STARTPTS,'
            f'afade=t=in:st=0:d={fade:.3f},'
            f'afade=t=out:st={fade_out_start:.3f}:d={fade:.3f},'
            f'volume={GAIN:.9f},'
            f'adelay={delay_ms}|{delay_ms}[{label}]'
        )
        labels.append(f'[{label}]')

    filters.append(''.join(labels) + f'amix=inputs={len(labels)}:normalize=0:duration=longest[music]')
    filters.append('[0:a][music]amix=inputs=2:normalize=0:duration=first,alimiter=limit=0.97[aout]')

    cmd += [
        '-filter_complex', ';'.join(filters),
        '-map', '0:v:0', '-map', '[aout]',
        '-c:v', 'copy',
        '-c:a', 'aac', '-b:a', '256k',
        '-movflags', '+faststart',
        '-shortest', str(OUT),
    ]
    subprocess.run(cmd, check=True)

    probe = subprocess.run([
        'ffprobe', '-v', 'error',
        '-show_entries', 'format=duration,size',
        '-of', 'json', str(OUT)
    ], capture_output=True, text=True, check=True)
    print(probe.stdout)
    print(f'MUSIC MIX OK: 12 blocks, fixed gain {GAIN:.9f} (-18 dB), ducking OFF')


if __name__ == '__main__':
    main()
