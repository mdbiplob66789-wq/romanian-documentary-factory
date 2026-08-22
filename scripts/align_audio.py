import base64, json, re, subprocess, unicodedata, zlib
from difflib import SequenceMatcher
from pathlib import Path
import whisper

AUDIO=Path("ElevenLabs_Kuki_combined.mp3")
OUT=Path("src/aligned_timeline.json")
REPORT=Path("alignment_report.json")
EXPECTED=160
PLAN_B64="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"
PLAN=json.loads(zlib.decompress(base64.b64decode(PLAN_B64)).decode("utf-8"))

def norm(s):
    s=''.join(c for c in unicodedata.normalize('NFKD',s.lower()) if not unicodedata.combining(c))
    s=s.replace('ş','s').replace('ș','s').replace('ţ','t').replace('ț','t')
    return re.findall(r'[a-z0-9]+',s)

def sim(tokens,words,i,n):
    cand=[w['norm'] for w in words[i:i+n] if w['norm']]
    return SequenceMatcher(None,' '.join(tokens),' '.join(cand)).ratio()

def find_anchor(anchor,words,cursor):
    tokens=norm(anchor)[:14]
    lo=max(0,cursor-1); hi=min(len(words),cursor+110)
    best=(cursor,-1.0)
    for i in range(lo,hi):
        for d in (-3,-2,-1,0,1,2,3):
            score=sim(tokens,words,i,max(1,len(tokens)+d))-0.0012*max(0,i-cursor)
            if score>best[1]: best=(i,score)
    idx=best[0]
    raw=max(0.0,best[1]+0.0012*max(0,idx-cursor))
    return idx,raw

def duration(path):
    p=subprocess.run(['ffprobe','-v','error','-show_entries','format=duration','-of','default=nw=1:nk=1',str(path)],capture_output=True,text=True,check=True)
    return float(p.stdout.strip())

def image_manifest():
    manifest={}
    for n in range(1,EXPECTED+1):
        stem=f'shot_{n:03d}'
        candidates=[Path(stem+'.jpg'),Path(stem+'.png')]
        existing=[p for p in candidates if p.exists()]
        if not existing: raise RuntimeError(f'Missing image {stem} (.jpg or .png)')
        manifest[n]=existing[0].name
    return manifest

def main():
    if len(PLAN)!=EXPECTED: raise RuntimeError(f'Plan has {len(PLAN)} rows, expected {EXPECTED}')
    manifest=image_manifest()
    audio_dur=duration(AUDIO)
    print(f'Audio duration: {audio_dur:.3f}s; images: {len(manifest)}')
    model=whisper.load_model('small')
    r=model.transcribe(str(AUDIO),language='ro',task='transcribe',word_timestamps=True,fp16=False,verbose=False)
    words=[]
    for seg in r['segments']:
        for w in seg.get('words',[]):
            t=norm(w['word'])
            words.append({'text':w['word'],'norm':t[0] if t else '', 'start':round(float(w['start']),3),'end':round(float(w['end']),3)})
    if not words: raise RuntimeError('Whisper returned no words')
    matches=[]; cursor=0; warnings=[]
    for row in PLAN:
        idx,conf=find_anchor(row['a'],words,cursor)
        t=float(words[idx]['start'])
        if matches and t < matches[-1]['time']: raise RuntimeError(f'Non-monotonic shot {row["id"]}')
        if matches and t-matches[-1]['time']>20: raise RuntimeError(f'Alignment jump before shot {row["id"]}: {t-matches[-1]["time"]:.2f}s')
        if conf<0.42: raise RuntimeError(f'Low confidence shot {row["id"]}: {conf:.3f} | {row["a"]}')
        if conf<0.55: warnings.append(f'shot {row["id"]} confidence={conf:.3f}')
        matches.append({'shot':row['id'],'anchor':row['a'],'time':round(t,3),'confidence':round(conf,3),'matched_word':words[idx]['text'],'word_index':idx})
        cursor=max(cursor,idx+1)
        print(f'{row["id"]:03d} {t:8.3f}s conf={conf:.3f} | {row["a"][:64]}')
    starts=[0.0]+[float(x['time']) for x in matches[1:]]
    shots=[]
    for j,row in enumerate(PLAN):
        start=starts[j]; end=starts[j+1] if j+1<EXPECTED else audio_dur
        d=end-start
        if d<=0.12: raise RuntimeError(f'Shot {j+1} too short: {d:.3f}s')
        if d>20: raise RuntimeError(f'Shot {j+1} too long: {d:.2f}s')
        shots.append({'shot':j+1,'start':round(start,3),'end':round(end,3),'duration':round(d,3),'confidence':matches[j]['confidence'],'image':manifest[j+1],'motion':row['m'],'intensity':row['i']})
    payload={'source':'whisper-small-sequential-v4-160','language':'ro','audio_duration':round(audio_dur,3),'shots':shots,'matches':matches,'words':words,'warnings':warnings,'qc':{'aligned_shots':len(shots),'image_count':len(manifest),'min_confidence':min(x['confidence'] for x in matches),'average_confidence':round(sum(x['confidence'] for x in matches)/len(matches),3),'min_shot_duration':min(x['duration'] for x in shots),'max_shot_duration':max(x['duration'] for x in shots)}}
    OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8')
    REPORT.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8')
    print('QC',json.dumps(payload['qc'],ensure_ascii=False))
    for w in warnings: print('WARN',w)

if __name__=='__main__': main()
