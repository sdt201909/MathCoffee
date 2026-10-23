import {parseTimeline} from './schema.ts';
import type {Timeline} from './schema.ts';

export type FrameSpan = {start_frame: number; end_frame: number};
export type ShortsHeader = FrameSpan & {id: string; title: string; subtitle?: string};
export type ShortsTimeline = Timeline & {shorts: {
  episode: string;
  brand: string;
  series: string;
  show_captions: boolean;
  scene_headers: ShortsHeader[];
  footer?: FrameSpan & {text: string};
  closing?: FrameSpan & {scene_id: string; title: string; lines: string[]};
  black_from_frame?: number;
}};
export type DisplayEntry = {id: string; scene_id: string; kind: 'heading' | 'label' | 'brand'; text: string};

function object(value: unknown, name: string): Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw new Error(`${name} must be an object`);
  return value as Record<string, unknown>;
}
function text(value: unknown, name: string, max: number): string {
  if (typeof value !== 'string' || !value.trim() || /[\r\n\u0000-\u001f]/u.test(value) || [...value].length > max) {
    throw new Error(`${name} must be one nonempty line of at most ${max} characters`);
  }
  return value;
}
function span(raw: Record<string, unknown>, total: number, name: string): FrameSpan {
  const start = raw.start_frame, end = raw.end_frame;
  if (!Number.isSafeInteger(start) || !Number.isSafeInteger(end) || typeof start !== 'number' || typeof end !== 'number' || start < 0 || start >= end || end > total) {
    throw new Error(`${name} needs a positive integer [start_frame, end_frame) interval`);
  }
  return {start_frame: start, end_frame: end};
}

/** Portrait is explicitly opted into; existing landscape renderers remain strict. */
export function parseShortsTimeline(input: unknown, allowNoAudio = false): ShortsTimeline {
  const base = parseTimeline(input, allowNoAudio, 'portrait');
  const raw = object(input, 'timeline');
  const s = object(raw.shorts, 'shorts');
  const episode = text(s.episode, 'shorts.episode', 3);
  if (!/^\d{3}$/u.test(episode)) throw new Error('shorts.episode must be a three-digit issue number');
  const brand = text(s.brand, 'shorts.brand', 10);
  const series = text(s.series, 'shorts.series', 8);
  if (s.show_captions !== undefined && typeof s.show_captions !== 'boolean') throw new Error('shorts.show_captions must be boolean');
  if (!Array.isArray(s.scene_headers) || !s.scene_headers.length) throw new Error('shorts.scene_headers must be nonempty');
  const scene_headers: ShortsHeader[] = s.scene_headers.map((value: unknown) => {
    const h = object(value, 'scene header');
    const id = text(h.id, 'scene header.id', 80);
    if (!/^[a-z][a-z0-9_]*$/u.test(id)) throw new Error('scene header IDs must be safe lowercase names');
    return {id, ...span(h, base.duration_frames, 'scene header'), title: text(h.title, 'scene header.title', 16),
      ...(h.subtitle === undefined ? {} : {subtitle: text(h.subtitle, 'scene header.subtitle', 24)})};
  });
  const ids = new Set(scene_headers.map(h => h.id));
  if (ids.size !== scene_headers.length) throw new Error('scene header IDs must be unique');
  for (let i = 1; i < scene_headers.length; i++) {
    if (scene_headers[i].start_frame < scene_headers[i - 1].end_frame) throw new Error('scene headers must be ordered and nonoverlapping');
  }
  const shorts: ShortsTimeline['shorts'] = {episode, brand, series, scene_headers, show_captions: s.show_captions !== false};
  if (s.footer !== undefined) {
    const f = object(s.footer, 'shorts.footer');
    shorts.footer = {...span(f, base.duration_frames, 'shorts.footer'), text: text(f.text, 'shorts.footer.text', 21)};
  }
  if (s.closing !== undefined) {
    const c = object(s.closing, 'shorts.closing');
    const scene_id = text(c.scene_id, 'shorts.closing.scene_id', 80);
    const bounds = span(c, base.duration_frames, 'shorts.closing');
    const header = scene_headers.find(h => h.id === scene_id);
    if (!header || bounds.start_frame < header.start_frame || bounds.end_frame > header.end_frame) throw new Error('closing must lie inside its declared scene');
    if (!Array.isArray(c.lines) || c.lines.length > 2) throw new Error('closing permits zero to two lines');
    shorts.closing = {...bounds, scene_id, title: text(c.title, 'shorts.closing.title', 12), lines: c.lines.map((v: unknown) => text(v, 'closing line', 18))};
  }
  if (s.black_from_frame !== undefined) {
    const n = s.black_from_frame;
    if (typeof n !== 'number' || !Number.isSafeInteger(n) || n < 1 || n >= base.duration_frames) throw new Error('black_from_frame must leave both content and a final black frame');
    if (scene_headers.some(h => h.end_frame > n) || base.captions.some(c => c.end_frame > n) || base.qa.anchor_frames.some(f => f + 2 > n) ||
        (shorts.footer && shorts.footer.end_frame > n) || (shorts.closing && shorts.closing.end_frame > n)) {
      throw new Error('Displayed text must end before the black tail');
    }
    shorts.black_from_frame = n;
  }
  if (shorts.closing?.lines.length && shorts.footer && shorts.closing.start_frame < shorts.footer.end_frame && shorts.closing.end_frame > shorts.footer.start_frame) {
    throw new Error('Closing body lines and footer cannot occupy the same portrait area at the same time');
  }
  for (const caption of base.captions) {
    const lines = caption.text.split('\n');
    if (/[\r\u0000-\u0009\u000b-\u001f]/u.test(caption.text) || lines.length > 2 || lines.some(line => !line.trim() || [...line].length > 18)) {
      throw new Error(`Caption ${caption.id} exceeds the portrait budget: two nonempty lines, 18 characters each`);
    }
  }
  return {...base, shorts};
}

/** Uses exactly the same props strings as Shorts.tsx; captions remain in the base timeline. */
export function shortsDisplayEntries(timeline: ShortsTimeline): DisplayEntry[] {
  const s = timeline.shorts;
  const entries: DisplayEntry[] = [];
  for (const h of s.scene_headers) {
    const put = (suffix: string, kind: DisplayEntry['kind'], value: string) => entries.push({id: `shorts.${h.id}.${suffix}`, scene_id: h.id, kind, text: value});
    put('brand', 'brand', s.brand);
    put('series', 'brand', `${s.series} ${s.episode}`);
    put('title', 'heading', h.title);
    if (h.subtitle) put('subtitle', 'label', h.subtitle);
    if (s.footer && h.start_frame < s.footer.end_frame && h.end_frame > s.footer.start_frame) put('footer', 'brand', s.footer.text);
    if (s.closing?.scene_id === h.id) {
      put('closing_title', 'heading', s.closing.title);
      s.closing.lines.forEach((line, i) => put(`closing_${i + 1}`, 'label', line));
    }
  }
  return entries;
}
