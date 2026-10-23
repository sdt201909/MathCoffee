import React from 'react';
import {AbsoluteFill, Html5Audio, OffthreadVideo, Sequence, staticFile, useCurrentFrame} from 'remotion';
import type {FrameSpan, ShortsTimeline} from './shorts-schema';

const C = {bg: '#080D16', panel: '#0C121D', line: '#294354', cyan: '#70E1E8', gold: '#FFD166', text: '#F4F7FB', muted: '#9CAABD'};
const FONT = 'Heiti SC, PingFang SC, Hiragino Sans GB, sans-serif';
const active = (span: FrameSpan | undefined, frame: number) => Boolean(span && frame >= span.start_frame && frame < span.end_frame);

/** Portrait packaging only. All mathematical geometry is in the imported native-size clips. */
export const Shorts: React.FC<ShortsTimeline> = props => {
  const frame = useCurrentFrame();
  const s = props.shorts;
  const header = s.scene_headers.find(h => active(h, frame));
  const caption = s.show_captions ? props.captions.find(c => active(c, frame)) : undefined;
  const footer = active(s.footer, frame) ? s.footer : undefined;
  const closing = active(s.closing, frame) ? s.closing : undefined;
  const black = s.black_from_frame !== undefined && frame >= s.black_from_frame;
  const flash = props.qa.anchor_frames.some(f => frame >= f && frame < f + 2);
  return <AbsoluteFill style={{backgroundColor: black ? '#000000' : C.bg}}>
    {props.audio && <Html5Audio src={staticFile(props.audio.file)} />}
    {!black && <>
      {props.clips.map(clip => <Sequence key={clip.id} from={clip.start_frame} durationInFrames={clip.duration_frames}>
        <OffthreadVideo src={staticFile(clip.file)} trimBefore={clip.source_in_frame} durationInFrames={clip.duration_frames} muted style={{width: '100%', height: '100%', objectFit: 'contain'}} />
      </Sequence>)}
      <div style={{position: 'absolute', width: 1080, height: 1920, transform: `scale(${props.height / 1920})`, transformOrigin: 'top left', fontFamily: FONT, color: C.text, overflow: 'hidden'}}>
        <div style={{position: 'absolute', left: 80, top: 88, width: 830, display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: 27, lineHeight: '38px'}}>
          <span style={{color: C.muted, letterSpacing: 2}}>{s.brand}</span>
          <span style={{color: C.cyan, letterSpacing: 1}}>{s.series} {s.episode}</span>
        </div>
        {header && <div style={{position: 'absolute', left: 80, top: 160, width: 830, height: 170}}>
          <div style={{fontSize: 49, lineHeight: '64px', fontWeight: 600, color: C.text, whiteSpace: 'nowrap'}}>{header.title}</div>
          {header.subtitle && <div style={{marginTop: 22, fontSize: 31, lineHeight: '43px', color: C.muted, whiteSpace: 'nowrap'}}>{header.subtitle}</div>}
          <div style={{position: 'absolute', left: 0, bottom: 0, width: 80, height: 3, background: C.cyan}} />
        </div>}
        {closing && <div style={{position: 'absolute', left: 80, top: 1220, width: 830, height: 220, boxSizing: 'border-box', textAlign: 'center', display: 'flex', flexDirection: 'column', justifyContent: 'flex-start'}}>
          <div style={{fontSize: 48, lineHeight: 1.3, color: C.gold, marginBottom: closing.lines.length ? 24 : 0}}>{closing.title}</div>
          {closing.lines.map((line, i) => <div key={i} style={{fontSize: 35, lineHeight: 1.35, marginTop: i ? 12 : 0, whiteSpace: 'nowrap'}}>{line}</div>)}
        </div>}
        {caption && <div style={{position: 'absolute', left: 80, top: 1514, width: 830, height: 160, boxSizing: 'border-box', display: 'flex', alignItems: 'center', justifyContent: 'center', background: C.bg}}>
          <div style={{width: '100%', fontSize: 45, lineHeight: 1.32, fontWeight: 500, textAlign: 'center', whiteSpace: 'pre', color: C.text}}>{caption.text}</div>
        </div>}
        {footer && <div style={{position: 'absolute', left: 80, top: 1340, width: 830, height: 54, fontSize: 38, lineHeight: '54px', color: C.text, textAlign: 'center', whiteSpace: 'nowrap'}}>{footer.text}</div>}
        {flash && <div style={{position: 'absolute', left: 960, top: 120, width: 24, height: 24, background: '#FFFFFF'}} />}
      </div>
    </>}
  </AbsoluteFill>;
};
