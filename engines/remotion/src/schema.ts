export type Clip = {
  id: string;
  renderer: 'manim' | 'remotion';
  file: string;
  start_frame: number;
  source_in_frame: number;
  duration_frames: number;
  sha256: string;
};
export type Caption = {
  id: string;
  text: string;
  start_frame: number;
  end_frame: number;
};
export type Timeline = {
  schema_version: 1;
  width: number;
  height: number;
  fps: number;
  duration_frames: number;
  clips: Clip[];
  captions: Caption[];
  audio: {file: string; sample_rate: number; samples: number; sha256: string} | null;
  qa: {anchor_frames: number[]};
};

function object(value: unknown, name: string): Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    throw new Error(`${name} must be an object`);
  }
  return value as Record<string, unknown>;
}
function integer(value: unknown, name: string, minimum = 0): number {
  if (typeof value !== 'number' || !Number.isSafeInteger(value) || value < minimum) {
    throw new Error(`${name} must be an integer >= ${minimum}`);
  }
  return value;
}
function string(value: unknown, name: string): string {
  if (typeof value !== 'string' || !value.trim()) throw new Error(`${name} must be nonempty text`);
  return value;
}
export function assetPath(value: unknown): string {
  const path = string(value, 'asset path');
  if (/[\\:#?\u0000-\u001f]/u.test(path) || path.startsWith('/') ||
      path.split('/').some((part) => ['', '.', '..'].includes(part))) {
    throw new Error(`Asset must be a public-relative path, without a URL or traversal: ${path}`);
  }
  return path;
}
function hash(value: unknown): string {
  if (typeof value !== 'string' || !/^[a-f0-9]{64}$/u.test(value)) {
    throw new Error('sha256 must be a lowercase 64-character hex digest');
  }
  return value;
}
function array(value: unknown, name: string): unknown[] {
  if (!Array.isArray(value)) throw new Error(`${name} must be an array`);
  return value;
}
function unique(ids: string[], name: string) {
  if (new Set(ids).size !== ids.length) throw new Error(`${name} IDs must be unique`);
}

export type AspectMode = 'landscape' | 'portrait';

export function parseTimeline(input: unknown, allowNoAudio = false, aspect: AspectMode = 'landscape'): Timeline {
  const raw = object(input, 'timeline');
  if (raw.schema_version !== 1) throw new Error('Unsupported schema_version');
  if (aspect !== 'landscape' && aspect !== 'portrait') throw new Error('Unknown aspect mode');
  const width = integer(raw.width, 'width', aspect === 'portrait' ? 180 : 320);
  const height = integer(raw.height, 'height', aspect === 'portrait' ? 320 : 180);
  const ratioMatches = aspect === 'portrait' ? width * 16 === height * 9 : width * 9 === height * 16;
  if (!ratioMatches || width % 2 || height % 2) {
    throw new Error(`Only even ${aspect === 'portrait' ? '9:16' : '16:9'} dimensions are supported`);
  }
  const fps = integer(raw.fps, 'fps', 1);
  if (fps > 120) throw new Error('fps must not exceed 120');
  const duration_frames = integer(raw.duration_frames, 'duration_frames', 1);
  const clips: Clip[] = array(raw.clips, 'clips').map((value) => {
    const c = object(value, 'clip');
    if (c.renderer !== 'manim' && c.renderer !== 'remotion') throw new Error('Unknown imported renderer');
    const clip: Clip = {
      id: string(c.id, 'clip.id'), renderer: c.renderer, file: assetPath(c.file),
      start_frame: integer(c.start_frame, 'clip.start_frame'),
      source_in_frame: integer(c.source_in_frame, 'clip.source_in_frame'),
      duration_frames: integer(c.duration_frames, 'clip.duration_frames', 1),
      sha256: hash(c.sha256),
    };
    if (clip.start_frame + clip.duration_frames > duration_frames) throw new Error('Clip exceeds timeline');
    return clip;
  });
  unique(clips.map((c) => c.id), 'Clip');
  for (let i = 1; i < clips.length; i++) {
    if (clips[i].start_frame < clips[i - 1].start_frame + clips[i - 1].duration_frames) {
      throw new Error('Imported clips must be ordered and must not overlap in this composition');
    }
  }
  const captions: Caption[] = array(raw.captions, 'captions').map((value) => {
    const c = object(value, 'caption');
    const caption = {id: string(c.id, 'caption.id'), text: string(c.text, 'caption.text'),
      start_frame: integer(c.start_frame, 'caption.start_frame'),
      end_frame: integer(c.end_frame, 'caption.end_frame', 1)};
    if (caption.start_frame >= caption.end_frame || caption.end_frame > duration_frames) {
      throw new Error('Caption must have a positive interval within the timeline');
    }
    return caption;
  });
  unique(captions.map((c) => c.id), 'Caption');
  for (let i = 1; i < captions.length; i++) {
    if (captions[i].start_frame < captions[i - 1].end_frame) {
      throw new Error('Captions must be ordered and must not overlap');
    }
  }
  let audio: Timeline['audio'] = null;
  if (raw.audio !== null && raw.audio !== undefined) {
    const a = object(raw.audio, 'audio');
    audio = {file: assetPath(a.file), sample_rate: integer(a.sample_rate, 'audio.sample_rate', 1),
      samples: integer(a.samples, 'audio.samples', 1), sha256: hash(a.sha256)};
    if (audio.sample_rate !== 48000 || audio.samples !== duration_frames * 48000 / fps) {
      throw new Error('Premixed audio must be 48 kHz and match the whole timeline exactly');
    }
  } else if (!allowNoAudio) throw new Error('Production rendering requires a premixed audio file');
  const qa = object(raw.qa ?? {anchor_frames: []}, 'qa');
  const anchor_frames = array(qa.anchor_frames ?? [], 'qa.anchor_frames').map((f) => integer(f, 'anchor frame'));
  if (new Set(anchor_frames).size !== anchor_frames.length ||
      anchor_frames.some((f) => f + 2 > duration_frames)) {
    throw new Error('QA anchors must be unique and leave room for their two-frame flash');
  }
  return {schema_version: 1, width, height, fps, duration_frames, clips, captions, audio, qa: {anchor_frames}};
}
