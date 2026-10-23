import assert from 'node:assert/strict';
import {test} from 'node:test';
import {assetPath, parseTimeline} from '../src/schema.ts';

const hash = 'a'.repeat(64);
const timeline = () => ({schema_version: 1, width: 1920, height: 1080, fps: 60, duration_frames: 2160,
  clips: [{id: 'pilot', renderer: 'manim', file: 'video/pilot.mp4', start_frame: 240, source_in_frame: 0, duration_frames: 1680, sha256: hash}],
  captions: [{id: 'one', text: '数学与故事，one timeline。', start_frame: 60, end_frame: 180}],
  audio: {file: 'audio/mix.wav', sample_rate: 48000, samples: 1728000, sha256: hash}, qa: {anchor_frames: [120, 2040]}});
test('accepts frame timeline and exact premix duration', () => assert.deepEqual(parseTimeline(timeline()), timeline()));
test('rejects network and filesystem escape paths', () => {
  for (const s of ['https://host/a.mp4', '//host/a.mp4', '/tmp/a.mp4', '../a.mp4', 'a/../b.mp4', 'a\\b.mp4', 'C:/a.wav', 'a.mp4#x', 'a.mp4?x']) assert.throws(() => assetPath(s));
});
test('requires integer timing and non-overlapping, bounded spans', () => {
  let t = timeline(); t.clips[0].start_frame = .5; assert.throws(() => parseTimeline(t));
  t = timeline(); t.clips.push({...t.clips[0], id: 'other'}); assert.throws(() => parseTimeline(t));
  t = timeline(); t.captions[0].end_frame = 2161; assert.throws(() => parseTimeline(t));
  t = timeline(); t.captions.push({...t.captions[0], id: 'overlap'}); assert.throws(() => parseTimeline(t));
});
test('requires an exact full-length premix outside explicit smoke mode', () => {
  const t = timeline(); t.audio.samples -= 1000; assert.throws(() => parseTimeline(t));
  t.audio = null; assert.throws(() => parseTimeline(t)); assert.equal(parseTimeline(t, true).audio, null);
});
test('bounds both frames of each QA flash and keeps caption end exclusive', () => {
  const t = timeline(); t.qa.anchor_frames = [2159]; assert.throws(() => parseTimeline(t));
  t.qa.anchor_frames = [2158]; t.captions.push({id: 'two', text: '下一句', start_frame: 180, end_frame: 240});
  assert.equal(parseTimeline(t).captions.length, 2);
});
test('rejects unordered input rather than silently sorting it', () => {
  const t = timeline(); t.captions.unshift({id: 'late', text: '后一句', start_frame: 200, end_frame: 300});
  assert.throws(() => parseTimeline(t), /ordered/);
});
test('permits optional QA and a one-frame silent smoke without anchors', () => {
  const t = timeline(); t.duration_frames = 1; t.clips = []; t.captions = []; t.audio = null; delete t.qa;
  assert.deepEqual(parseTimeline(t, true).qa, {anchor_frames: []});
});
