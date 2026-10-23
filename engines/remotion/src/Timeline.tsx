import React from 'react';
import {AbsoluteFill, Html5Audio, OffthreadVideo, Sequence, staticFile, useCurrentFrame} from 'remotion';
import type {Timeline as TimelineData} from './schema';

/** Landscape compositor: every visible word comes from the supplied timeline. */
export const Timeline: React.FC<TimelineData> = props => {
  const frame = useCurrentFrame();
  const caption = props.captions.find(c => frame >= c.start_frame && frame < c.end_frame);
  const flash = props.qa.anchor_frames.some(f => frame >= f && frame < f + 2);
  return <AbsoluteFill style={{backgroundColor: '#080E19'}}>
    {props.audio && <Html5Audio src={staticFile(props.audio.file)} />}
    {props.clips.map(clip => <Sequence key={clip.id} from={clip.start_frame} durationInFrames={clip.duration_frames}>
      <OffthreadVideo src={staticFile(clip.file)} trimBefore={clip.source_in_frame} durationInFrames={clip.duration_frames} muted style={{width: '100%', height: '100%', objectFit: 'contain'}} />
    </Sequence>)}
    <div style={{position: 'absolute', width: 1920, height: 1080, transform: `scale(${props.width / 1920})`, transformOrigin: 'top left', fontFamily: 'PingFang SC, Hiragino Sans GB, sans-serif', color: '#F4F1E9'}}>
      {caption && <div style={{position: 'absolute', left: 64, top: 950, width: 1792, height: 110, display: 'flex', alignItems: 'center', justifyContent: 'center', background: '#080E19'}}>
        <div style={{fontSize: caption.text.length > 64 ? 35 : caption.text.length > 40 ? 40 : 45, fontWeight: 500, lineHeight: 1.23, textAlign: 'center', maxWidth: 1700, whiteSpace: 'pre-wrap', overflowWrap: 'break-word'}}>{caption.text}</div>
      </div>}
      {flash && <div style={{position: 'absolute', left: 1840, top: 80, width: 32, height: 32, background: '#FFFFFF'}} />}
    </div>
  </AbsoluteFill>;
};
