import React from 'react';
import {Composition, registerRoot} from 'remotion';
import {Timeline} from './Timeline';
import {parseTimeline} from './schema';
import type {Timeline as TimelineData} from './schema';

const defaults: TimelineData = {schema_version: 1, width: 960, height: 540, fps: 30, duration_frames: 90, clips: [], captions: [], audio: null, qa: {anchor_frames: []}};
const Root: React.FC = () => <Composition id="MathCoffeeTimeline" component={Timeline} width={defaults.width} height={defaults.height} fps={defaults.fps} durationInFrames={defaults.duration_frames} defaultProps={defaults} calculateMetadata={({props}) => {
  const timeline = parseTimeline(props, true);
  return {width: timeline.width, height: timeline.height, fps: timeline.fps, durationInFrames: timeline.duration_frames, props: timeline};
}} />;
registerRoot(Root);
