export type Motion =
  | 'static'
  | 'slow_zoom_in'
  | 'slow_zoom_out'
  | 'slow_pan_left'
  | 'slow_pan_right';

export type Transition = 'cut' | 'soft_crossfade';

export type Shot = {
  id: number;
  image: string;
  start: number;
  end: number;
  motion: Motion;
  transition?: Transition;
};

export type MusicCue = {
  file: string;
  start: number;
  end: number;
  volume?: number;
  fadeIn?: number;
  fadeOut?: number;
};

export type EditPlan = {
  fps: number;
  width: number;
  height: number;
  voiceover: string;
  shots: Shot[];
  music: MusicCue[];
};
