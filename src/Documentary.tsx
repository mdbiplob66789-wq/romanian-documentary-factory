import React from 'react';
import {
  AbsoluteFill,
  Img,
  Sequence,
  interpolate,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from 'remotion';
import {Audio} from '@remotion/media';
import type {EditPlan, Motion, Shot} from './types';

const ShotLayer: React.FC<{shot: Shot}> = ({shot}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const duration = Math.max(1, Math.round((shot.end - shot.start) * fps));

  const progress = interpolate(frame, [0, duration - 1], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });

  const motionStyle = (motion: Motion): React.CSSProperties => {
    switch (motion) {
      case 'slow_zoom_in':
        return {scale: 1 + progress * 0.045};
      case 'slow_zoom_out':
        return {scale: 1.045 - progress * 0.045};
      case 'slow_pan_left':
        return {scale: 1.04, translate: `${18 - progress * 36}px 0px`};
      case 'slow_pan_right':
        return {scale: 1.04, translate: `${-18 + progress * 36}px 0px`};
      default:
        return {scale: 1};
    }
  };

  const fadeFrames = Math.min(6, Math.floor(duration / 4));
  const opacity = shot.transition === 'soft_crossfade' && fadeFrames > 0
    ? interpolate(
        frame,
        [0, fadeFrames, duration - fadeFrames - 1, duration - 1],
        [0, 1, 1, 0],
        {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'},
      )
    : 1;

  return (
    <AbsoluteFill style={{backgroundColor: '#ffffff', overflow: 'hidden'}}>
      <Img
        src={staticFile(shot.image)}
        style={{
          width: '100%',
          height: '100%',
          objectFit: 'cover',
          opacity,
          ...motionStyle(shot.motion),
        }}
      />
    </AbsoluteFill>
  );
};

export const Documentary: React.FC<{plan: EditPlan}> = ({plan}) => {
  const {fps} = useVideoConfig();

  return (
    <AbsoluteFill style={{backgroundColor: '#ffffff'}}>
      {plan.shots.map((shot) => {
        const from = Math.round(shot.start * fps);
        const durationInFrames = Math.max(1, Math.round((shot.end - shot.start) * fps));
        return (
          <Sequence key={shot.id} from={from} durationInFrames={durationInFrames}>
            <ShotLayer shot={shot} />
          </Sequence>
        );
      })}

      <Audio src={staticFile(plan.voiceover)} />

      {plan.music.map((cue, index) => {
        const from = Math.round(cue.start * fps);
        const durationInFrames = Math.max(1, Math.round((cue.end - cue.start) * fps));
        const baseVolume = cue.volume ?? 0.12;
        const fadeInFrames = Math.round((cue.fadeIn ?? 1.5) * fps);
        const fadeOutFrames = Math.round((cue.fadeOut ?? 1.5) * fps);

        return (
          <Sequence key={`${cue.file}-${index}`} from={from} durationInFrames={durationInFrames}>
            <Audio
              src={staticFile(cue.file)}
              volume={(f) => {
                const inGain = fadeInFrames > 0
                  ? interpolate(f, [0, fadeInFrames], [0, 1], {
                      extrapolateLeft: 'clamp',
                      extrapolateRight: 'clamp',
                    })
                  : 1;
                const outGain = fadeOutFrames > 0
                  ? interpolate(
                      f,
                      [Math.max(0, durationInFrames - fadeOutFrames), durationInFrames],
                      [1, 0],
                      {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'},
                    )
                  : 1;
                return baseVolume * Math.min(inGain, outGain);
              }}
            />
          </Sequence>
        );
      })}
    </AbsoluteFill>
  );
};
