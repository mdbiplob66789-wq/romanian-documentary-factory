import React from 'react';
import {AbsoluteFill, Audio, Composition, Img, interpolate, staticFile, useCurrentFrame} from 'remotion';

const FPS = 30;
const SHOT_SECONDS = 3;
const SHOT_FRAMES = FPS * SHOT_SECONDS;
const SHOTS = ['shot_001.jpg','shot_002.jpg','shot_003.jpg','shot_004.jpg','shot_005.jpg'];

const DocumentaryTest = () => {
  const frame = useCurrentFrame();
  const shotIndex = Math.min(SHOTS.length - 1, Math.floor(frame / SHOT_FRAMES));
  const local = frame % SHOT_FRAMES;
  const zoom = interpolate(local, [0, SHOT_FRAMES - 1], [1.0, 1.035], {extrapolateLeft:'clamp', extrapolateRight:'clamp'});
  const opacity = interpolate(local, [0, 8, SHOT_FRAMES - 8, SHOT_FRAMES - 1], [0.88, 1, 1, 0.88], {extrapolateLeft:'clamp', extrapolateRight:'clamp'});
  return (
    <AbsoluteFill style={{backgroundColor:'black', overflow:'hidden'}}>
      <Img src={staticFile(SHOTS[shotIndex])} style={{width:'100%',height:'100%',objectFit:'cover',transform:`scale(${zoom})`,opacity}} />
      <Audio src={staticFile('ElevenLabs_Kuki_combined.mp3')} volume={1} />
    </AbsoluteFill>
  );
};

export const RemotionRoot = () => (
  <Composition id="DocumentaryTest" component={DocumentaryTest} durationInFrames={SHOT_FRAMES * SHOTS.length} fps={FPS} width={1920} height={1080} />
);
