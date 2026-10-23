import React from 'react';
import {Composition, registerRoot} from 'remotion';
import {Shorts} from './Shorts';
import {parseShortsTimeline} from './shorts-schema';
import type {ShortsTimeline} from './shorts-schema';

const defaults: ShortsTimeline = {schema_version: 1, width: 540, height: 960, fps: 30, duration_frames: 90, clips: [], captions: [], audio: null, qa: {anchor_frames: []}, shorts: {episode: '000', brand: '知数咖啡厅', series: '一口知数', show_captions: false, scene_headers: [{id: 'example', start_frame: 0, end_frame: 90, title: '示例标题'}]}};
const Root: React.FC = () => <Composition id="MathCoffeeShorts" component={Shorts} width={defaults.width} height={defaults.height} fps={defaults.fps} durationInFrames={defaults.duration_frames} defaultProps={defaults} calculateMetadata={({props}) => {
  const timeline = parseShortsTimeline(props, true);
  return {width: timeline.width, height: timeline.height, fps: timeline.fps, durationInFrames: timeline.duration_frames, props: timeline};
}} />;
registerRoot(Root);
