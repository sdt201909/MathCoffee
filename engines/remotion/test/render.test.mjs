import assert from 'node:assert/strict';
import {test} from 'node:test';
import {mkdtemp, writeFile, symlink, rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import path from 'node:path';
import {spawnSync} from 'node:child_process';
import {argumentsFrom, refuseExisting, muxExactPremix, sha256} from '../render.mjs';

test('landscape CLI requires explicit absolute asset, props and output paths', () => {
  const args = ['--props', '/tmp/timeline.json', '--public-dir', '/tmp/public', '--output', '/tmp/output.mp4'];
  assert.equal(argumentsFrom([...args, '--no-audio']).noAudio, true);
  assert.throws(() => argumentsFrom(args.slice(0, -1).concat('output.mp4')), /absolute/);
  assert.throws(() => argumentsFrom(args.slice(0, -1).concat('/tmp/output.png')), /mp4/);
  assert.throws(() => argumentsFrom([...args, '--unknown']), /Unknown/);
});

test('output protection preserves existing output or sidecar bytes', async () => {
  const temp = await mkdtemp(path.join(tmpdir(), 'mathcoffee-output-test-'));
  try {
    for (const name of ['output.mp4', 'output.mp4.render.json']) {
      const file = path.join(temp, name);
      await writeFile(file, 'existing');
      await assert.rejects(refuseExisting(file), /overwrite/);
    }
    await refuseExisting(path.join(temp, 'new.mp4'));
    const dangling = path.join(temp, 'dangling.mp4');
    await symlink(path.join(temp, 'missing.mp4'), dangling);
    await assert.rejects(refuseExisting(dangling), /overwrite/);
  } finally { await rm(temp, {recursive: true, force: true}); }
});

test('shared AAC mux preserves a fractional frame clock and copied video packets', async (t) => {
  if (spawnSync('ffmpeg', ['-version']).status !== 0 || spawnSync('ffprobe', ['-version']).status !== 0) {
    t.skip('native FFmpeg/FFprobe unavailable'); return;
  }
  const temp = await mkdtemp(path.join(tmpdir(), 'mathcoffee-mux-test-'));
  try {
    const picture = path.join(temp, 'picture.mp4');
    const premix = path.join(temp, 'premix.wav');
    const output = path.join(temp, 'film.mp4');
    const execute = args => {
      const result = spawnSync('ffmpeg', ['-v', 'error', '-nostdin', '-n', ...args], {encoding: 'utf8'});
      assert.equal(result.status, 0, result.stderr);
    };
    execute(['-f', 'lavfi', '-i', 'color=c=black:s=32x32:r=30', '-frames:v', '7', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', picture]);
    execute(['-f', 'lavfi', '-i', 'sine=frequency=440:sample_rate=48000', '-t', '0.233333333333', '-ac', '2', '-c:a', 'pcm_s24le', premix]);
    const timeline = {audio: {file: 'premix.wav', samples: 11200, sha256: await sha256(premix)}};
    const receipt = await muxExactPremix(picture, output, timeline, temp);
    assert.equal(receipt.video_bitstream_sha256_before, receipt.video_bitstream_sha256_after);
    const probe = spawnSync('ffprobe', ['-v', 'error', '-show_streams', '-of', 'json', output], {encoding: 'utf8'});
    assert.equal(probe.status, 0, probe.stderr);
    const audio = JSON.parse(probe.stdout).streams.find(s => s.codec_type === 'audio');
    const [num, den] = audio.time_base.split('/').map(Number);
    assert.equal(Number(audio.duration_ts) * num * 48000, timeline.audio.samples * den);
    assert.equal(Number(audio.start_pts), 0);
    timeline.audio.sha256 = '0'.repeat(64);
    await assert.rejects(muxExactPremix(picture, path.join(temp, 'bad.mp4'), timeline, temp), /Premix changed/);
  } finally { await rm(temp, {recursive: true, force: true}); }
});
