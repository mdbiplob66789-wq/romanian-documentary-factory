import React from 'react';
import {Composition} from 'remotion';
import {Documentary} from './Documentary';
import rawPlan from './edit-plan.json';
import type {EditPlan} from './types';

const plan = rawPlan as EditPlan;
const durationSeconds = Math.max(
  ...plan.shots.map((shot) => shot.end),
  ...plan.music.map((cue) => cue.end),
  1,
);

export const Root: React.FC = () => {
  return (
    <Composition
      id="RomanianDocumentary"
      component={Documentary}
      width={plan.width}
      height={plan.height}
      fps={plan.fps}
      durationInFrames={Math.ceil(durationSeconds * plan.fps)}
      defaultProps={{plan}}
    />
  );
};
