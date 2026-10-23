import assert from 'node:assert/strict';
import {test} from 'node:test';
import {parseTimeline} from '../src/schema.ts';
import {parseShortsTimeline, shortsDisplayEntries} from '../src/shorts-schema.ts';
import {argumentsFrom} from '../render-shorts.mjs';

const hash = 'a'.repeat(64);
const timeline = () => ({schema_version: 1, width: 1080, height: 1920, fps: 60, duration_frames: 600,
  clips: [{id: 'scene01', renderer: 'manim', file: 'video/scene01.mp4', start_frame: 0, source_in_frame: 0, duration_frames: 600, sha256: hash}],
  captions: [{id: 'scene01_01', text: '这是第一行，\n这是第二行。', start_frame: 0, end_frame: 300}],
  audio: {file: 'audio/mix.wav', sample_rate: 48000, samples: 480000, sha256: hash}, qa: {anchor_frames: []},
  shorts: {episode: '000', brand: '知数咖啡厅', series: '一口知数', show_captions: true,
    scene_headers: [{id: 'scene01', start_frame: 0, end_frame: 590, title: '示例标题', subtitle: '示例说明'}],
    footer: {text: '一口数学，让概念看得见。', start_frame: 500, end_frame: 590},
    closing: {scene_id: 'scene01', start_frame: 500, end_frame: 590, title: '一口知数', lines: []}, black_from_frame: 590}});

test('portrait requires explicit mode and keeps existing landscape defaults', () => {
  const t = timeline();
  assert.throws(() => parseTimeline(t), /16:9/);
  assert.equal(parseTimeline(t, false, 'portrait').height, 1920);
  t.width = 1920; t.height = 1080;
  assert.equal(parseTimeline(t).width, 1920);
  assert.throws(() => parseShortsTimeline(t), /9:16/);
  assert.throws(() => parseTimeline(t, false, 'square'), /aspect/);
});
test('accepts native portrait delivery and half-size draft metadata', () => {
  assert.deepEqual(parseShortsTimeline(timeline()), timeline());
  const t = timeline(); t.width = 540; t.height = 960; t.fps = 30; t.audio.samples = 960000;
  assert.equal(parseShortsTimeline(t).width, 540);
  t.width = 541; assert.throws(() => parseShortsTimeline(t), /9:16/);
});
test('enforces unique ordered header identities and title bounds', () => {
  let t = timeline(); t.shorts.scene_headers.push({...t.shorts.scene_headers[0]});
  assert.throws(() => parseShortsTimeline(t), /unique/);
  t = timeline(); t.shorts.scene_headers.push({...t.shorts.scene_headers[0], id: 'scene02'});
  assert.throws(() => parseShortsTimeline(t), /nonoverlapping/);
  t = timeline(); t.shorts.scene_headers[0].title = '数'.repeat(17);
  assert.throws(() => parseShortsTimeline(t), /16 characters/);
  t = timeline(); t.shorts.scene_headers[0].id = 'SCENE01';
  assert.throws(() => parseShortsTimeline(t), /lowercase/);
});
test('caption mode hides only captions and does not remove diagram/header data', () => {
  const t = timeline(); t.shorts.show_captions = false;
  const parsed = parseShortsTimeline(t);
  assert.deepEqual(parsed.captions, t.captions);
  assert.deepEqual(parsed.clips, t.clips);
  assert.deepEqual(shortsDisplayEntries(parsed), shortsDisplayEntries(parseShortsTimeline(timeline())));
  t.shorts.show_captions = 'false'; assert.throws(() => parseShortsTimeline(t), /boolean/);
});
test('requires explicit readable subtitle wrapping rather than shrinking the type', () => {
  let t = timeline(); t.captions[0].text = '数'.repeat(19); assert.throws(() => parseShortsTimeline(t), /portrait budget/);
  t = timeline(); t.captions[0].text = '一\n二\n三'; assert.throws(() => parseShortsTimeline(t), /portrait budget/);
  t = timeline(); t.captions[0].text = '一\n'; assert.throws(() => parseShortsTimeline(t), /portrait budget/);
  t = timeline(); t.captions[0].text = '一\r二'; assert.throws(() => parseShortsTimeline(t), /portrait budget/);
});
test('closing fits its declared scene and black tail contains no authored text', () => {
  let t = timeline(); t.shorts.closing.scene_id = 'scene08'; assert.throws(() => parseShortsTimeline(t), /declared scene/);
  t = timeline(); t.shorts.closing.lines = ['一', '二', '三']; assert.throws(() => parseShortsTimeline(t), /zero to two/);
  t = timeline(); t.captions[0].end_frame = 595; assert.throws(() => parseShortsTimeline(t), /black tail/);
  t = timeline(); t.shorts.black_from_frame = 600; assert.throws(() => parseShortsTimeline(t), /final black frame/);
  t = timeline(); t.qa.anchor_frames = [589]; assert.throws(() => parseShortsTimeline(t), /black tail/);
  t = timeline(); t.shorts.closing.lines = ['结论']; assert.throws(() => parseShortsTimeline(t), /same portrait area/);
});
test('audience display entries use actual data, stable scene IDs and include ending copy', () => {
  const t = parseShortsTimeline(timeline());
  const entries = shortsDisplayEntries(t);
  assert.equal(new Set(entries.map(e => e.id)).size, entries.length);
  assert.ok(entries.every(e => e.scene_id === 'scene01'));
  for (const expected of ['知数咖啡厅', '一口知数 000', '示例标题', '示例说明', '一口数学，让概念看得见。', '一口知数']) {
    assert.ok(entries.some(e => e.text === expected), expected);
  }
  assert.ok(entries.every(e => !/Remotion|Manim|生成|验收|调试/u.test(e.text)));
});
test('render CLI validates absolute paths, still frame, caption switch and extensions', () => {
  const base = ['--props', '/tmp/timeline.json', '--public-dir', '/tmp/public', '--output'];
  assert.equal(argumentsFrom([...base, '/tmp/out.mp4', '--no-captions']).noCaptions, true);
  assert.equal(argumentsFrom([...base, '/tmp/frame.png', '--still-frame', '12'])['still-frame'], '12');
  assert.throws(() => argumentsFrom([...base, 'out.mp4']), /absolute/);
  assert.throws(() => argumentsFrom([...base, '/tmp/frame.png', '--still-frame', '-1']), /nonnegative/);
  assert.throws(() => argumentsFrom([...base, '/tmp/out.mp4', '--still-frame', '0']), /extension/);
});
