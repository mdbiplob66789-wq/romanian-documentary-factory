import React from 'react';
import {
  AbsoluteFill,
  Composition,
  Img,
  interpolate,
  staticFile,
  useCurrentFrame,
} from 'remotion';
import {Audio} from '@remotion/media';
import timeline from './aligned_timeline.json';

const FPS = 30;
const SHOTS = timeline.shots.map((shot) => ({
  ...shot,
  startFrame: Math.max(0, Math.round(Number(shot.start) * FPS)),
  endFrame: Math.max(1, Math.round(Number(shot.end) * FPS)),
}));
const TOTAL_FRAMES = Math.max(1, Math.ceil(Number(timeline.audio_duration) * FPS));

const DocumentaryFull = () => {
  const frame = useCurrentFrame();
  let shotIndex = SHOTS.length - 1;
  for (let i = 0; i < SHOTS.length; i++) {
    if (frame < SHOTS[i].endFrame) {
      shotIndex = i;
      break;
    }
  }
  const shot = SHOTS[shotIndex];
  const duration = Math.max(2, shot.endFrame - shot.startFrame);
  const localFrame = Math.max(0, frame - shot.startFrame);
  const progress = Math.min(1, localFrame / Math.max(1, duration - 1));

  // Approved documentary motion language, slightly strengthened after the 40-shot test.
  // low = 4.5%, medium = 7.5%; never crosses the 8% moire-risk ceiling.
  const amplitude = shot.intensity === 'medium' ? 0.075 : 0.045;
  let scale = 1;
  let x = 0;
  let y = 0;
  if (shot.motion === 'zoom_in') scale = interpolate(progress, [0, 1], [1, 1 + amplitude]);
  if (shot.motion === 'zoom_out') scale = interpolate(progress, [0, 1], [1 + amplitude, 1]);
  if (shot.motion === 'pan_left') {
    scale = 1.05;
    const travel = shot.intensity === 'medium' ? 1.8 : 1.25;
    x = interpolate(progress, [0, 1], [travel, -travel]);
    y = interpolate(progress, [0, 1], [-0.12, 0.12]);
  }
  if (shot.motion === 'pan_right') {
    scale = 1.05;
    const travel = shot.intensity === 'medium' ? 1.8 : 1.25;
    x = interpolate(progress, [0, 1], [-travel, travel]);
    y = interpolate(progress, [0, 1], [0.12, -0.12]);
  }
  if (shot.motion === 'static') {
    scale = 1.005;
    x = 0;
    y = 0;
  }

  return (
    <AbsoluteFill style={{backgroundColor: '#e8e0cf', overflow: 'hidden'}}>
      <Img
        src={staticFile(`shots/${shot.image}`)}
        style={{
          width: '100%',
          height: '100%',
          objectFit: 'cover',
          transform: `translate(${x}%, ${y}%) scale(${scale})`,
        }}
      />
      <Audio src={staticFile('voiceover.mp3')} volume={1} />
    </AbsoluteFill>
  );
};

export const RemotionRoot = () => (
  <Composition
    id="DocumentaryFull"
    component={DocumentaryFull}
    durationInFrames={TOTAL_FRAMES}
    fps={FPS}
    width={1920}
    height={1080}
  />
);
