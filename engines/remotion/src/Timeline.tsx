import React from 'react';
import {AbsoluteFill, Html5Audio, OffthreadVideo, Sequence, staticFile, useCurrentFrame} from 'remotion';
import {styleFontStack} from './schema';
import type {Timeline as TimelineData} from './schema';

/** Landscape compositor: every visible word comes from the supplied timeline. */
export const Timeline: React.FC<TimelineData> = props => {
  const frame = useCurrentFrame();
  const style = props.style;
  const caption = (!style || style.layout.caption_enabled) ? props.captions.find(c => frame >= c.start_frame && frame < c.end_frame) : undefined;
  const header = props.headers?.find(h => frame >= h.start_frame && frame < h.end_frame);
  const flash = props.qa.anchor_frames.some(f => frame >= f && frame < f + 2);
  const background = style?.colors.background ?? '#080E19';
  const text = style?.colors.text ?? '#F4F1E9';
  const canvas = style?.render ?? {width: 1920, height: 1080};
  const captionRect = style?.layout.caption_rect ?? [64, 950, 1792, 110];
  const titleRect = style?.layout.title_rect;
  const brandRect = style?.layout.brand_rect ?? (style ? [style.layout.safe_rect[0], 0, style.layout.safe_rect[2], style.layout.font_sizes.brand * 1.5] : undefined);
  return <AbsoluteFill style={{backgroundColor: background}}>
    {props.audio && <Html5Audio src={staticFile(props.audio.file)} />}
    {props.clips.map(clip => <Sequence key={clip.id} from={clip.start_frame} durationInFrames={clip.duration_frames}>
      <OffthreadVideo src={staticFile(clip.file)} trimBefore={clip.source_in_frame} durationInFrames={clip.duration_frames} muted style={{width: '100%', height: '100%', objectFit: 'contain'}} />
    </Sequence>)}
    <div style={{position: 'absolute', width: canvas.width, height: canvas.height, transform: `scale(${props.width / canvas.width})`, transformOrigin: 'top left', fontFamily: style ? styleFontStack(style) : 'PingFang SC, Hiragino Sans GB, sans-serif', color: text}}>
      {style && style.brand && brandRect && header && <div style={{position: 'absolute', left: brandRect[0], top: brandRect[1], width: brandRect[2], height: brandRect[3], color: style.colors.muted, fontSize: style.layout.font_sizes.brand, lineHeight: 1.4, whiteSpace: 'pre-wrap', overflowWrap: 'anywhere', textAlign: 'right'}}>{style.brand}</div>}
      {style && header && titleRect && <div style={{position: 'absolute', left: titleRect[0], top: titleRect[1], width: titleRect[2], height: titleRect[3]}}>
        <div style={{fontSize: style.layout.font_sizes.title, lineHeight: 1.25, fontWeight: 600, whiteSpace: 'pre-wrap', overflowWrap: 'anywhere'}}>{header.title}</div>
        {header.subtitle && <div style={{fontSize: style.layout.font_sizes.body, marginTop: 12, lineHeight: 1.25, color: style.colors.muted, whiteSpace: 'pre-wrap', overflowWrap: 'anywhere'}}>{header.subtitle}</div>}
      </div>}
      {caption && <div style={{position: 'absolute', left: captionRect[0], top: captionRect[1], width: captionRect[2], height: captionRect[3], display: 'flex', alignItems: 'center', justifyContent: 'center', background}}>
        <div style={{fontSize: style?.layout.font_sizes.caption ?? (caption.text.length > 64 ? 35 : caption.text.length > 40 ? 40 : 45), fontWeight: 500, lineHeight: 1.25, textAlign: 'center', maxWidth: '100%', whiteSpace: 'pre-wrap', overflowWrap: 'anywhere'}}>{caption.text}</div>
      </div>}
      {flash && <div style={{position: 'absolute', left: canvas.width - 80, top: 80, width: 32, height: 32, background: '#FFFFFF'}} />}
    </div>
  </AbsoluteFill>;
};
