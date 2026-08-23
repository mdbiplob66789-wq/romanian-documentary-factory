import json, math, subprocess
from pathlib import Path

ROOT = Path('.')
VIDEO = ROOT / 'out' / 'final_video.mp4'
REPORT = ROOT / 'alignment_report.json'
MUSIC = ROOT / 'music'
OUT = ROOT / 'out' / 'video_001_FINAL_YOUTUBE.mp4'
TMP = ROOT / 'out' / 'music_tmp'
TMP.mkdir(parents=True, exist_ok=True)

VOICE_TARGET = -14.0
MUSIC_TARGET = -34.0  # exactly 20 dB below target voice
XFADE = 60.0
INTRO = 6.0
OUTRO = 10.0
LOOP_XFADE = 8.0

TRACKS = [MUSIC/'block_01.mp3', MUSIC/'block_02.mp3', MUSIC/'block_03.mp3']


def run(cmd):
    subprocess.run([str(x) for x in cmd], check=True)


def duration(p):
    r = subprocess.run(['ffprobe','-v','error','-show_entries','format=duration','-of','default=nw=1:nk=1',str(p)], capture_output=True, text=True, check=True)
    return float(r.stdout.strip())


def extend_track(src, need, out, fade_in=False, fade_out=False):
    d = duration(src)
    n = max(1, math.ceil((need-LOOP_XFADE) / max(1.0, d-LOOP_XFADE)))
    inputs=[]
    for _ in range(n): inputs += ['-i', src]
    if n == 1:
        chain='[0:a]anull[x0]'; label='x0'
    else:
        chain=f'[0:a][1:a]acrossfade=d={LOOP_XFADE}:c1=qsin:c2=qsin[x1]'; label='x1'
        for i in range(2,n):
            chain += f';[{label}][{i}:a]acrossfade=d={LOOP_XFADE}:c1=qsin:c2=qsin[x{i}]'
            label=f'x{i}'
    post=f'[{label}]atrim=0:{need:.6f},asetpts=PTS-STARTPTS,loudnorm=I={MUSIC_TARGET}:TP=-6:LRA=4'
    if fade_in: post += f',afade=t=in:st=0:d={INTRO}'
    if fade_out: post += f',afade=t=out:st={max(0,need-OUTRO):.6f}:d={OUTRO}'
    post += '[a]'
    run(['ffmpeg','-y','-hide_banner','-loglevel','error',*inputs,'-filter_complex',chain+';'+post,'-map','[a]','-ar','48000','-ac','2','-c:a','pcm_s24le',out])


def main():
    for p in [VIDEO, REPORT, *TRACKS]:
        if not p.exists(): raise RuntimeError(f'Missing required file: {p}')

    rep=json.loads(REPORT.read_text(encoding='utf-8'))
    anchors={int(a['shot']):float(a['time']) for a in rep['anchors']}
    total=float(rep['audio_duration'])

    # Final Claude music_map/v1 text boundaries resolve to these aligned shot anchors:
    # MB02 start "Şi apoi, într-o seară..." = shot 076
    # MB03 start "Există explicaţii." = shot 128
    b1=anchors[76]
    b2=anchors[128]
    if not (0 < b1 < b2 < total): raise RuntimeError('Music anchors are not monotonic')

    # 60s crossfades end exactly at the text boundary, so coverage is continuous and gapless.
    lengths=[b1, b2-(b1-XFADE), total-(b2-XFADE)]
    blocks=[]
    for i,(src,need) in enumerate(zip(TRACKS,lengths),1):
        out=TMP/f'block_{i:02d}.wav'
        extend_track(src, need, out, fade_in=(i==1), fade_out=(i==3))
        blocks.append(out)

    bed=TMP/'music_bed.wav'
    run(['ffmpeg','-y','-hide_banner','-loglevel','error','-i',blocks[0],'-i',blocks[1],'-i',blocks[2],'-filter_complex',
         f'[0:a][1:a]acrossfade=d={XFADE}:c1=qsin:c2=qsin[x1];[x1][2:a]acrossfade=d={XFADE}:c1=qsin:c2=qsin[m]',
         '-map','[m]','-ar','48000','-ac','2','-c:a','pcm_s24le',bed])

    voice=TMP/'voice_norm.wav'
    run(['ffmpeg','-y','-hide_banner','-loglevel','error','-i',VIDEO,'-vn','-af',f'loudnorm=I={VOICE_TARGET}:TP=-1.5:LRA=7','-ar','48000','-ac','2','-c:a','pcm_s24le',voice])

    # No ducking, no sidechain compression, no event-based music automation.
    run(['ffmpeg','-y','-hide_banner','-loglevel','error','-i',VIDEO,'-i',voice,'-i',bed,
         '-filter_complex','[1:a][2:a]amix=inputs=2:normalize=0:duration=first,alimiter=limit=0.891251[aout]',
         '-map','0:v:0','-map','[aout]','-c:v','copy','-c:a','aac','-b:a','256k','-movflags','+faststart',OUT])

    run(['ffmpeg','-v','error','-i',OUT,'-f','null','-'])
    run(['ffprobe','-v','error','-show_entries','format=duration,size:stream=index,codec_name,codec_type,width,height,sample_rate,channels','-of','json',OUT])
    print(f'FINAL OK: {OUT} | 3 blocks | music -20 dB vs voice target | ducking OFF | crossfade 60s')

if __name__ == '__main__':
    main()
