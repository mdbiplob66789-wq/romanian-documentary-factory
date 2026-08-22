import base64,json,re,subprocess,unicodedata,zlib
from difflib import SequenceMatcher
from pathlib import Path
import whisper
AUDIO=Path('ElevenLabs_Kuki_combined.mp3'); OUT=Path('src/aligned_timeline.json'); REPORT=Path('alignment_report.json'); EXPECTED=160
PLAN=json.loads(zlib.decompress(base64.b64decode('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')).decode('utf-8'))
def norm_tokens(s):
 s=''.join(c for c in unicodedata.normalize('NFKD',s.lower()) if not unicodedata.combining(c)); s=s.replace('ş','s').replace('ș','s').replace('ţ','t').replace('ț','t'); return re.findall(r'[a-z0-9]+',s)
def dur(path): return float(subprocess.run(['ffprobe','-v','error','-show_entries','format=duration','-of','default=nw=1:nk=1',str(path)],capture_output=True,text=True,check=True).stdout.strip())
def manifest():
 out={}
 for n in range(1,EXPECTED+1):
  found=[p for p in (Path(f'shot_{n:03d}.jpg'),Path(f'shot_{n:03d}.png')) if p.exists()]
  if not found: raise RuntimeError(f'Missing shot_{n:03d}')
  out[n]=found[0].name
 return out
def score(anchor,words,i,n):
 a=' '.join(norm_tokens(anchor)); b=' '.join(w['norm'] for w in words[i:i+n]); return SequenceMatcher(None,a,b).ratio()
def find_anchor(anchor,words,cursor):
 toks=norm_tokens(anchor); n=max(1,len(toks)); lo=max(0,cursor-2); hi=min(len(words),cursor+180); best=None
 for i in range(lo,hi):
  for d in range(-3,4):
   nn=max(1,n+d); s=score(anchor,words,i,nn)-0.0007*max(0,i-cursor)
   if best is None or s>best[0]: best=(s,i,nn)
 raw=best[0]+0.0007*max(0,best[1]-cursor); return best[1],best[2],raw
def main():
 if len(PLAN)!=EXPECTED: raise RuntimeError(f'Plan {len(PLAN)} != {EXPECTED}')
 imgs=manifest(); ad=dur(AUDIO); print(f'voiceover={ad:.3f}s images={len(imgs)}')
 model=whisper.load_model('small')
 result=model.transcribe(str(AUDIO),language='ro',word_timestamps=True,fp16=False,condition_on_previous_text=True)
 words=[]
 for seg in result['segments']:
  for w in seg.get('words',[]):
   t=norm_tokens(w.get('word',''))
   if t: words.append({'raw':w['word'],'norm':t[0],'start':float(w['start']),'end':float(w['end'])})
 if len(words)<200: raise RuntimeError('Whisper returned too few words')
 starts=[]; diagnostics=[]; cursor=0
 for row in PLAN:
  idx,nn,conf=find_anchor(row['START_TEXT'],words,cursor)
  starts.append(words[idx]['start']); diagnostics.append({'shot':row['SHOT'],'anchor':row['START_TEXT'],'time':words[idx]['start'],'confidence':round(conf,4),'word_index':idx})
  cursor=max(cursor+1,idx)
 for i in range(1,len(starts)):
  if starts[i] <= starts[i-1]: starts[i]=min(ad-0.05,max(starts[i-1]+0.04,words[min(len(words)-1,diagnostics[i]['word_index'])]['start']))
 bad=[d for d in diagnostics if d['confidence']<0.48]
 if bad: raise RuntimeError('Low-confidence anchors: '+', '.join(f"S{x['shot']}={x['confidence']}" for x in bad[:12]))
 shots=[]
 for i,row in enumerate(PLAN):
  st=max(0.0,starts[i]); en=starts[i+1] if i+1<len(starts) else ad
  if en<=st: raise RuntimeError(f'Non-positive shot S{row["SHOT"]}')
  shots.append({'id':row['SHOT'],'image':imgs[int(row['SHOT'])],'start':round(st,3),'end':round(en,3),'motion':row['MOTION'],'intensity':row['INTENSITY']})
 if any(shots[i]['start']>=shots[i+1]['start'] for i in range(159)): raise RuntimeError('Timeline not monotonic')
 payload={'audio_duration':round(ad,3),'shots':shots}; OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8')
 REPORT.write_text(json.dumps({'audio_duration':ad,'word_count':len(words),'shot_count':len(shots),'min_confidence':min(d['confidence'] for d in diagnostics),'anchors':diagnostics},ensure_ascii=False,indent=2),encoding='utf-8')
 print('QC PASS: 160 shots, monotonic timeline, min confidence',min(d['confidence'] for d in diagnostics))
if __name__=='__main__': main()
