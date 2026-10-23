import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {test} from 'node:test';
import {parseTimeline, styleFontStack} from '../src/schema.ts';
import {parseShortsTimeline, shortsDisplayEntries} from '../src/shorts-schema.ts';

const presets = new URL('../../../src/mathcoffee/data/presets/', import.meta.url);
const preset = async name => JSON.parse(await readFile(new URL(`${name}-v1.json`, presets), 'utf8'));
const base = style => ({schema_version: 1, width: style.render.draft.width, height: style.render.draft.height,
  fps: style.render.draft.fps, duration_frames: 300, clips: [], captions: [], audio: null,
  qa: {anchor_frames: []}, style});
const portrait = style => ({...base(style), shorts: {episode: '000', brand: style.brand, series: '',
  scene_headers: [{id: 'opening', title: '比较两种读法', start_frame: 0, end_frame: 300}]}});

test('resolved styles survive parsing and preserve custom configuration provenance', async () => {
  const style = await preset('mathcoffee-longform');
  style.colors.object_a = '#FF8800'; style.font.family = 'Custom Font'; style.brand = '自己的频道';
  style.provenance = {style_sha256: 'a'.repeat(64), review_status: 'pending_author_confirmation'};
  const input = {...base(style), headers: [{id: 'opening', title: '长度怎样比较？', start_frame: 0, end_frame: 300}]};
  assert.deepEqual(parseTimeline(input, true), input);
  assert.equal(parseTimeline(input, true).style.layout.caption_enabled, true);
  assert.equal(styleFontStack(parseTimeline(input, true).style), '"Custom Font", "PingFang SC", "Hiragino Sans GB", sans-serif');
});

test('style geometry and FPS must agree with final or declared draft rendering', async () => {
  const style = await preset('mathcoffee-longform');
  const input = base(style);
  input.width = 1920; input.height = 1080; input.fps = 60;
  assert.equal(parseTimeline(input, true).width, 1920);
  input.fps = 30;
  assert.throws(() => parseTimeline(input, true), /Style render\/draft/);
  input.fps = 60; input.style.layout.title_rect = [0, 0, 3000, 100];
  assert.throws(() => parseTimeline(input, true), /canvas/);
});

test('style portrait uses its subtitle policy and does not require another creator brand', async () => {
  const style = await preset('mathcoffee-shorts');
  const input = portrait(style);
  input.captions = [{id: 'cue_one', text: '内部时间信息不等于烧录旁白字幕。'.repeat(5), start_frame: 0, end_frame: 200}];
  const parsed = parseShortsTimeline(input, true);
  assert.equal(parsed.shorts.show_captions, false);
  assert.equal(parsed.shorts.brand, '');
  assert.deepEqual(shortsDisplayEntries(parsed).map(e => e.text), ['比较两种读法']);
  input.shorts.show_captions = true;
  assert.throws(() => parseShortsTimeline(input, true), /caption policy/);
});

test('style titles keep full text and obey the configured rectangle rather than legacy character caps', async () => {
  const style = await preset('mathcoffee-shorts');
  const input = portrait(style);
  const full = '同一个点为什么会有两种不同的坐标读法';
  input.shorts.scene_headers[0].title = full;
  assert.equal(parseShortsTimeline(input, true).shorts.scene_headers[0].title, full);
  input.style.layout.title_rect[3] = 40;
  assert.throws(() => parseShortsTimeline(input, true), /title rectangle/);
});

test('style headers reject duplicates and conflicts and captions respect configured size', async () => {
  const style = await preset('mathcoffee-longform');
  const input = {...base(style), headers: [{id: 'opening', title: '比较长度', start_frame: 0, end_frame: 300}]};
  input.headers.push({...input.headers[0]});
  assert.throws(() => parseTimeline(input, true), /unique/);
  input.headers.pop(); input.scene_headers = [{...input.headers[0], title: '旧标题'}];
  assert.throws(() => parseTimeline(input, true), /Conflicting/);
  delete input.scene_headers;
  input.captions = [{id: 'cue_one', text: '字'.repeat(1000), start_frame: 0, end_frame: 300}];
  assert.throws(() => parseTimeline(input, true), /caption rectangle/);
});


test('style brand budget rejects overflow without truncating identity', async () => {
  const style = await preset('mathcoffee-longform');
  style.brand = '很长的频道名字'.repeat(20);
  assert.throws(() => parseTimeline(base(style), true), /brand rectangle/);
});
