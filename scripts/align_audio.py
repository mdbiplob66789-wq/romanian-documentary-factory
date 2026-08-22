import json, re, unicodedata
from difflib import SequenceMatcher
from pathlib import Path
import whisper

AUDIO='ElevenLabs_Kuki_combined.mp3'
OUT=Path('src/aligned_timeline.json')
ANCHORS=[
'În septembrie 1991','un bărbat din judeţul Bacău a plecat de acasă pentru câteva zile.','Era negustor de vite.','Îşi cumpărase bilet de tren, plătit dinainte.','Nu s-a mai întors.','S-a întors în august 2021.','Treizeci de ani mai târziu.','Purta aceleaşi haine.','Buhoci este o comună din judeţul Bacău.','Un loc obişnuit, în estul României.','Case cu porţi de lemn, uliţe de ţară, oameni care se cunosc între ei de o viaţă.','oameni care se cunosc între ei de o viaţă.','Acolo trăia Vasile Gorgoş.','Era negustor de vite. O meserie veche, care cere drumuri.','care cere drumuri.','Pleca des de acasă, uneori pentru mai multe zile, alteori pentru mai mult.','Cumpăra, vindea, se întorcea.','se întorcea.','Aşa fusese ani la rând.','Nimeni nu se îngrijora','pentru că Vasile se întorcea întotdeauna.','În 1991 avea şaizeci şi trei de ani.','Şi în 1991, România se schimba.','Comunismul căzuse cu doar un an şi jumătate înainte.','Ţara era în mijlocul','pe care nimeni nu o înţelegea încă pe deplin.','un om care pleacă la drum cu vitele nu era ceva ieşit din comun.','Ce ştim sigur despre acea zi este puţin.','Dar ce ştim este important.','Vasile Gorgoş a plecat de acasă pentru o scurtă călătorie de afaceri.','pentru o scurtă călătorie de afaceri.','Şi-a cumpărat un bilet de tren dus-întors.','L-a plătit dinainte.','Opriţi-vă o clipă la detaliul ăsta.','Un om care îşi cumpără bilet de întoarcere este un om care are de gând să se întoarcă.','este un om care are de gând să se întoarcă.','Nu e gestul cuiva care fuge.','Nu e gestul cuiva care îşi părăseşte familia.','Este gestul unui om care ştie exact în ce zi va fi din nou acasă.','Doar că acea zi nu a venit.','Au trecut zilele în care ar fi trebuit să apară.'
]

def norm(s):
    s=''.join(c for c in unicodedata.normalize('NFKD',s.lower()) if not unicodedata.combining(c))
    s=s.replace('ş','s').replace('ș','s').replace('ţ','t').replace('ț','t')
    return re.findall(r'[a-z0-9]+',s)

def similarity(tokens,words,i,n):
    cand=[w['norm'] for w in words[i:i+n] if w['norm']]
    return SequenceMatcher(None,' '.join(tokens),' '.join(cand)).ratio()

def find_anchor(anchor,words,cursor):
    tokens=norm(anchor)[:12]
    # Critical rule: only search forward in a bounded sequential window.
    # Never fall back to the whole recording: repeated Romanian phrases caused
    # the previous 175s/192s jumps.
    lo=max(0,cursor-1)
    hi=min(len(words),cursor+90)
    best=(cursor,-1.0)
    for i in range(lo,hi):
        for d in (-2,-1,0,1,2):
            s=similarity(tokens,words,i,max(1,len(tokens)+d))
            # small distance penalty prefers the next occurrence, not a later repeat
            s_adj=s-0.0015*max(0,i-cursor)
            if s_adj>best[1]: best=(i,s_adj)
    idx=best[0]
    raw=max(0.0,best[1]+0.0015*max(0,idx-cursor))
    return idx,raw

print('Loading Whisper small (Romanian)...')
model=whisper.load_model('small')
print('Transcribing with word timestamps...')
r=model.transcribe(AUDIO,language='ro',task='transcribe',word_timestamps=True,fp16=False,verbose=False)
words=[]
for seg in r['segments']:
    for w in seg.get('words',[]):
        toks=norm(w['word'])
        words.append({'text':w['word'],'norm':toks[0] if toks else '','start':float(w['start']),'end':float(w['end'])})

matches=[]; cursor=0
for n,anchor in enumerate(ANCHORS,1):
    idx,conf=find_anchor(anchor,words,cursor)
    t=words[idx]['start']
    if matches and t<matches[-1]['time']: t=matches[-1]['time']
    # Hard sanity guard: storyboard anchors are consecutive; a single boundary
    # cannot jump tens/hundreds of seconds. Fail CI instead of rendering bad video.
    if matches and t-matches[-1]['time']>25:
        raise RuntimeError(f'Alignment jump at shot {n}: {t-matches[-1]["time"]:.2f}s')
    if conf<0.48:
        raise RuntimeError(f'Low-confidence anchor {n}: {conf:.3f} | {anchor}')
    matches.append({'shot':n,'anchor':anchor,'time':round(t,3),'confidence':round(conf,3),'matched_word':words[idx]['text']})
    cursor=max(cursor,idx+1)
    print(f'{n:03d} {t:8.3f}s conf={conf:.3f} | {anchor[:55]}')

shots=[]
for i in range(40):
    start=0.0 if i==0 else matches[i]['time']
    end=matches[i+1]['time']
    dur=end-start
    if dur<=0: end=start+0.35
    if end-start>25: raise RuntimeError(f'Invalid shot duration {i+1}: {end-start:.2f}s')
    shots.append({'shot':i+1,'start':round(start,3),'end':round(end,3),'confidence':matches[i]['confidence']})
payload={'source':'whisper-small-word-timestamps-sequential-v2','language':'ro','shots':shots,'matches':matches}
OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8')
Path('alignment_report.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8')
print('Wrote',OUT)
