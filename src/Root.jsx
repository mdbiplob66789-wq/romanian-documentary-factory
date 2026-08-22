import React from 'react';
import {AbsoluteFill, Composition, Img, interpolate, useCurrentFrame} from 'remotion';
import {Audio} from '@remotion/media';

const FPS = 30;
const BASE = 'https://raw.githubusercontent.com/mdbiplob66789-wq/romanian-documentary-factory/main/';

// First 40 storyboard shots. Durations are editorial estimates based on the supplied
// narrative anchors. Claude timing data can replace these values later without
// changing the rendering logic.
const SHOTS = [
  ['shot_001.jpg',4.2,'medium'], ['shot_002.jpg',4.0,'medium'], ['shot_003.jpg',3.2,'light'],
  ['shot_004.jpg',3.1,'light'],  ['shot_005.jpg',3.8,'heavy'],  ['shot_006.jpg',3.5,'heavy'],
  ['shot_007.jpg',4.0,'medium'], ['shot_008.jpg',3.8,'heavy'],  ['shot_009.jpg',4.2,'light'],
  ['shot_010.jpg',3.2,'light'],  ['shot_011.jpg',3.4,'light'],  ['shot_012.jpg',3.8,'medium'],
  ['shot_013.jpg',3.6,'light'],  ['shot_014.jpg',4.2,'light'],  ['shot_015.jpg',4.0,'medium'],
  ['shot_016.jpg',3.6,'medium'], ['shot_017.jpg',3.2,'light'],  ['shot_018.jpg',3.5,'light'],
  ['shot_019.jpg',3.6,'light'],  ['shot_020.jpg',3.4,'light'],  ['shot_021.jpg',3.6,'medium'],
  ['shot_022.jpg',3.2,'light'],  ['shot_023.jpg',4.0,'medium'], ['shot_024.jpg',3.6,'medium'],
  ['shot_025.jpg',3.8,'medium'], ['shot_026.jpg',3.4,'light'],  ['shot_027.jpg',3.8,'light'],
  ['shot_028.jpg',4.0,'medium'], ['shot_029.jpg',3.5,'medium'], ['shot_030.jpg',4.1,'light'],
  ['shot_031.jpg',3.4,'light'],  ['shot_032.jpg',3.5,'light'],  ['shot_033.jpg',3.4,'light'],
  ['shot_034.jpg',3.1,'medium'], ['shot_035.jpg',3.8,'light'],  ['shot_036.jpg',3.6,'medium'],
  ['shot_037.jpg',3.8,'heavy'],  ['shot_038.jpg',4.4,'medium'], ['shot_039.jpg',3.5,'light'],
  ['shot_040.jpg',4.2,'heavy'],
];

const framesPerShot = SHOTS.map(([,seconds]) => Math.round(seconds * FPS));
const starts = framesPerShot.reduce((arr, frames, i) => {
  arr.push(i === 0 ? 0 : arr[i - 1] + framesPerShot[i - 1]);
  return arr;
}, []);
const TOTAL_FRAMES = framesPerShot.reduce((a,b) => a + b, 0);

const DocumentaryTest = () => {
  const frame = useCurrentFrame();
  let shotIndex = SHOTS.length - 1;
  for (let i = 0; i < SHOTS.length; i++) {
    if (frame < starts[i] + framesPerShot[i]) {
      shotIndex = i;
      break;
    }
  }

  const [file,,mood] = SHOTS[shotIndex];
  const local = frame - starts[shotIndex];
  const duration = framesPerShot[shotIndex];
  const progress = duration <= 1 ? 1 : local / (duration - 1);

  // Restrained Ken Burns movement, slightly stronger than the first test.
  const zoomAmount = mood === 'heavy' ? 0.060 : mood === 'medium' ? 0.052 : 0.045;
  const reverse = shotIndex % 4 === 1 || shotIndex % 4 === 2;
  const zoom = reverse
    ? interpolate(progress, [0, 1], [1 + zoomAmount, 1.0])
    : interpolate(progress, [0, 1], [1.0, 1 + zoomAmount]);

  const panX = interpolate(progress, [0,1], shotIndex % 2 === 0 ? [-0.45,0.45] : [0.45,-0.45]);
  const panY = interpolate(progress, [0,1], shotIndex % 3 === 0 ? [0.25,-0.25] : [-0.15,0.15]);

  const edge = Math.min(7, Math.floor(duration / 4));
  const opacity = interpolate(
    local,
    [0, edge, Math.max(edge + 1, duration - edge - 1), duration - 1],
    [0.94, 1, 1, 0.94],
    {extrapolateLeft:'clamp', extrapolateRight:'clamp'}
  );

  return (
    <AbsoluteFill style={{backgroundColor:'black',overflow:'hidden'}}>
      <Img
        src={`${BASE}${file}`}
        style={{
          width:'100%',
          height:'100%',
          objectFit:'cover',
          transform:`translate(${panX}%, ${panY}%) scale(${zoom})`,
          opacity,
        }}
      />
      <Audio src={`${BASE}ElevenLabs_Kuki_combined.mp3`} volume={1} />
    </AbsoluteFill>
  );
};

export const RemotionRoot = () => (
  <Composition
    id="DocumentaryTest"
    component={DocumentaryTest}
    durationInFrames={TOTAL_FRAMES}
    fps={FPS}
    width={1920}
    height={1080}
  />
);
