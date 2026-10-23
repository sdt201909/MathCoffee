import assert from 'node:assert/strict';
import {test} from 'node:test';
import {mkdtemp, writeFile, symlink, rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import path from 'node:path';
import {argumentsFrom, refuseExisting} from '../render.mjs';

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
