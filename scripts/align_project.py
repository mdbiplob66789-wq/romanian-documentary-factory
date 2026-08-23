import json, re, subprocess, sys, unicodedata
from difflib import SequenceMatcher
from pathlib import Path
import whisper


def norm_tokens(text: str):
    text = ''.join(c for c in unicodedata.normalize('NFKD', text.lower()) if not unicodedata.combining(c))
    text = text.replace('ş', 's').replace('ș', 's').replace('ţ', 't').replace('ț', 't')
    return re.findall(r'[a-z0-9]+', text)


def duration(path: Path) -> float:
    p = subprocess.run([
        'ffprobe', '-v', 'error', '-show_entries', 'format=duration',
        '-of', 'default=nw=1:nk=1', str(path)
    ], capture_output=True, text=True, check=True)
    return float(p.stdout.strip())


def score(anchor, words, i, n):
    a = ' '.join(norm_tokens(anchor))
    b = ' '.join(w['norm'] for w in words[i:i+n])
    return SequenceMatcher(None, a, b).ratio()


def find_anchor(anchor, words, cursor):
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
                best = (s, i, nn)
    raw = best[0] + 0.0007 * max(0, best[1] - cursor)
    return best[1], best[2], raw


def main():
    if len(sys.argv) != 2:
        raise SystemExit('Usage: python scripts/align_project.py projects/video_002')

    project = Path(sys.argv[1])
    config_path = project / 'project.json'
    if not config_path.exists():
        raise RuntimeError(f'Missing {config_path}')

    cfg = json.loads(config_path.read_text(encoding='utf-8'))
    if cfg.get('mode') != 'isolated':
        raise RuntimeError('align_project.py is only for isolated projects')

    map_path = project / cfg.get('map', 'map.json')
    audio = project / cfg.get('voiceover', 'voiceover.mp3')
    shots_dir = project / cfg.get('shots_dir', 'shots')

    for p in (map_path, audio, shots_dir):
        if not p.exists():
            raise RuntimeError(f'Missing project asset: {p}')

    raw_map = json.loads(map_path.read_text(encoding='utf-8'))
    plan = raw_map['shots'] if isinstance(raw_map, dict) and 'shots' in raw_map else raw_map
    expected = int(cfg.get('shots', len(plan)))
    if len(plan) != expected:
        raise RuntimeError(f'Map contains {len(plan)} shots, expected {expected}')

    images = {}
    for n in range(1, expected + 1):
        found = [p for p in (shots_dir / f'shot_{n:03d}.jpg', shots_dir / f'shot_{n:03d}.png') if p.exists()]
        if len(found) != 1:
            raise RuntimeError(f'Expected exactly one image for shot_{n:03d}, found {len(found)}')
        images[n] = found[0].name

    ad = duration(audio)
    model = whisper.load_model('small')
    result = model.transcribe(str(audio), language=cfg.get('language', 'ro'), word_timestamps=True, fp16=False, condition_on_previous_text=True)

    words = []
    for seg in result['segments']:
        for w in seg.get('words', []):
            tok = norm_tokens(w.get('word', ''))
            if tok:
                words.append({'norm': tok[0], 'start': float(w['start']), 'end': float(w['end'])})
    if len(words) < 100:
        raise RuntimeError('Whisper returned too few words')

    starts, diagnostics, cursor = [], [], 0
    for row in plan:
        idx, nn, conf = find_anchor(row['START_TEXT'], words, cursor)
        starts.append(words[idx]['start'])
        diagnostics.append({'shot': row['SHOT'], 'anchor': row['START_TEXT'], 'time': words[idx]['start'], 'confidence': round(conf, 4), 'word_index': idx})
        cursor = max(cursor + 1, idx)

    for i in range(1, len(starts)):
        if starts[i] <= starts[i - 1]:
            starts[i] = min(ad - 0.05, max(starts[i - 1] + 0.04, words[min(len(words) - 1, diagnostics[i]['word_index'])]['start']))

    bad = [d for d in diagnostics if d['confidence'] < 0.48]
    if bad:
        raise RuntimeError('Low-confidence anchors: ' + ', '.join(f"S{x['shot']}={x['confidence']}" for x in bad[:12]))

    shots = []
    for i, row in enumerate(plan):
        st = max(0.0, starts[i])
        en = starts[i + 1] if i + 1 < len(starts) else ad
        if en <= st:
            raise RuntimeError(f"Non-positive shot S{row['SHOT']}")
        shots.append({
            'id': int(row['SHOT']),
            'image': images[int(row['SHOT'])],
            'start': round(st, 3),
            'end': round(en, 3),
            'motion': row.get('MOTION', 'static'),
            'intensity': row.get('INTENSITY', 'low')
        })

    Path('src/aligned_timeline.json').write_text(json.dumps({'audio_duration': round(ad, 3), 'shots': shots}, ensure_ascii=False, indent=2), encoding='utf-8')
    Path('alignment_report.json').write_text(json.dumps({'project_id': cfg['id'], 'audio_duration': ad, 'word_count': len(words), 'shot_count': len(shots), 'min_confidence': min(d['confidence'] for d in diagnostics), 'anchors': diagnostics}, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f"QC PASS: {cfg['id']} — {len(shots)} shots, min confidence {min(d['confidence'] for d in diagnostics):.4f}")


if __name__ == '__main__':
    main()
