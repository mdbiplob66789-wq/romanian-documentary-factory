import React from 'react';
import {AbsoluteFill,Composition,Img,interpolate,staticFile,useCurrentFrame} from 'remotion';
import {Audio} from '@remotion/media';
import timeline from './aligned_timeline.json';

const FPS=30;
const SHOTS=timeline.shots.map((shot)=>({...shot,startFrame:Math.max(0,Math.round(Number(shot.start)*FPS)),endFrame:Math.max(1,Math.round(Number(shot.end)*FPS))}));
const TOTAL_FRAMES=Math.max(1,Math.ceil(Number(timeline.audio_duration)*FPS));

const DocumentaryFull=()=>{
 const frame=useCurrentFrame();
 let shotIndex=SHOTS.length-1;
 for(let i=0;i<SHOTS.length;i++){if(frame<SHOTS[i].endFrame){shotIndex=i;break;}}
 const shot=SHOTS[shotIndex];
 const duration=Math.max(2,shot.endFrame-shot.startFrame);
 const localFrame=Math.max(0,frame-shot.startFrame);
 const progress=Math.min(1,localFrame/Math.max(1,duration-1));
 // Approved final motion lock: low 4%, medium 7%, never above 8%.
 const amplitude=shot.intensity==='medium'?0.07:0.04;
 let scale=1,x=0,y=0;
 if(shot.motion==='zoom_in') scale=interpolate(progress,[0,1],[1,1+amplitude]);
 if(shot.motion==='zoom_out') scale=interpolate(progress,[0,1],[1+amplitude,1]);
 if(shot.motion==='pan_left'){scale=1.04;const travel=shot.intensity==='medium'?1.7:1.2;x=interpolate(progress,[0,1],[travel,-travel]);y=interpolate(progress,[0,1],[-0.1,0.1]);}
 if(shot.motion==='pan_right'){scale=1.04;const travel=shot.intensity==='medium'?1.7:1.2;x=interpolate(progress,[0,1],[-travel,travel]);y=interpolate(progress,[0,1],[0.1,-0.1]);}
 if(shot.motion==='static'){scale=1;x=0;y=0;}
 return <AbsoluteFill style={{backgroundColor:'#e8e0cf',overflow:'hidden'}}><Img src={staticFile(`shots/${shot.image}`)} style={{width:'100%',height:'100%',objectFit:'cover',transform:`translate(${x}%, ${y}%) scale(${scale})`}}/><Audio src={staticFile('voiceover.mp3')} volume={1}/></AbsoluteFill>;
};
export const RemotionRoot=()=> <Composition id="DocumentaryFull" component={DocumentaryFull} durationInFrames={TOTAL_FRAMES} fps={FPS} width={1920} height={1080}/>;
