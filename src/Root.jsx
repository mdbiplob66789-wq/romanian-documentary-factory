import React from 'react';
import {AbsoluteFill, Composition, Img, interpolate, useCurrentFrame} from 'remotion';
import {Audio} from '@remotion/media';
import timeline from './aligned_timeline.json';

const FPS = 30;
const BASE = 'https://raw.githubusercontent.com/mdbiplob66789-wq/romanian-documentary-factory/main/';

// Claude's editorial choices for shots 1-40. Timing is NOT estimated here anymore:
// it is generated from the actual Romanian voiceover by scripts/align_audio.py.
const EDIT = [
 ['zoom_out','medium'],['zoom_in','medium'],['zoom_in','low'],['zoom_in','low'],['zoom_in','low'],
 ['zoom_in','low'],['zoom_out','medium'],['zoom_in','low'],['zoom_in','low'],['zoom_out','low'],
 ['zoom_in','low'],['zoom_in','medium'],['zoom_out','low'],['zoom_in','low'],['zoom_out','medium'],
 ['zoom_in','medium'],['zoom_in','low'],['zoom_in','low'],['zoom_out','low'],['zoom_in','low'],
 ['zoom_out','medium'],['zoom_out','low'],['pan_right','medium'],['pan_left','medium'],['pan_right','medium'],
 ['pan_left','medium'],['zoom_in','low'],['zoom_in','medium'],['zoom_out','medium'],['zoom_in','low'],
 ['zoom_out','low'],['zoom_in','low'],['zoom_in','low'],['zoom_in','medium'],['zoom_in','low'],
 ['zoom_in','medium'],['zoom_in','low'],['zoom_in','medium'],['zoom_in','low'],['static','low'],
];

const SHOTS = timeline.shots.slice(0,40).map((t,i) => ({
  ...t,
  file:`shot_${String(i+1).padStart(3,'0')}.jpg`,
  motion:EDIT[i][0],
  intensity:EDIT[i][1],
  startFrame:Math.max(0,Math.round(t.start*FPS)),
  endFrame:Math.max(1,Math.round(t.end*FPS)),
}));

const TOTAL_FRAMES = SHOTS.length ? SHOTS[SHOTS.length-1].endFrame : FPS;

const DocumentaryTest = () => {
  const frame = useCurrentFrame();
  let shotIndex = SHOTS.length - 1;
  for (let i=0;i<SHOTS.length;i++) {
    if (frame < SHOTS[i].endFrame) { shotIndex=i; break; }
  }
  const s=SHOTS[shotIndex];
  const duration=Math.max(2,s.endFrame-s.startFrame);
  const local=Math.max(0,frame-s.startFrame);
  const p=Math.min(1,local/(duration-1));

  // Claude's requested amplitudes: low=4%, medium=7%. Never exceed 8%.
  const amp=s.intensity==='medium'?0.07:0.04;
  let scale=1.025, x=0, y=0;
  if (s.motion==='zoom_in') scale=interpolate(p,[0,1],[1,1+amp]);
  if (s.motion==='zoom_out') scale=interpolate(p,[0,1],[1+amp,1]);
  if (s.motion==='pan_left') {
    scale=1.035;
    x=interpolate(p,[0,1],[0.85,-0.85]);
    y=interpolate(p,[0,1],[-0.10,0.10]);
  }
  if (s.motion==='pan_right') {
    scale=1.035;
    x=interpolate(p,[0,1],[-0.85,0.85]);
    y=interpolate(p,[0,1],[0.10,-0.10]);
  }
  if (s.motion==='static') { scale=1.01; x=0; y=0; }

  // Very small luminance dip only at the edit point: keeps cuts soft without
  // turning the documentary into a slideshow full of visible transitions.
  const edge=Math.min(4,Math.floor(duration/5));
  const opacity=interpolate(
    local,
    [0,edge,Math.max(edge+1,duration-edge-1),duration-1],
    [0.97,1,1,0.97],
    {extrapolateLeft:'clamp',extrapolateRight:'clamp'}
  );

  return <AbsoluteFill style={{backgroundColor:'black',overflow:'hidden'}}>
    <Img src={`${BASE}${s.file}`} style={{
      width:'100%',height:'100%',objectFit:'cover',
      transform:`translate(${x}%,${y}%) scale(${scale})`,opacity,
    }}/>
    <Audio src={`${BASE}ElevenLabs_Kuki_combined.mp3`} volume={1}/>
  </AbsoluteFill>;
};

export const RemotionRoot=()=> <Composition
  id="DocumentaryTest"
  component={DocumentaryTest}
  durationInFrames={TOTAL_FRAMES}
  fps={FPS}
  width={1920}
  height={1080}
/>;
