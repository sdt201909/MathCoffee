import assert from 'node:assert/strict';
import {test} from 'node:test';
import {mkdtemp, mkdir, writeFile, symlink, rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import path from 'node:path';
import {resolveAsset, sha256} from '../render.mjs';

test('checks realpath containment so a staged symlink cannot escape', async () => {
  const temp = await mkdtemp(path.join(tmpdir(), 'mathcoffee-remotion-test-'));
  try {
    const pub = path.join(temp, 'public'); await mkdir(pub);
    await writeFile(path.join(pub, 'clip.mp4'), 'abc');
    await writeFile(path.join(temp, 'outside.mp4'), 'external');
    await symlink(path.join(temp, 'outside.mp4'), path.join(pub, 'escape.mp4'));
    assert.ok((await resolveAsset(pub, 'clip.mp4')).endsWith('clip.mp4'));
    await assert.rejects(resolveAsset(pub, 'escape.mp4'), /outside/);
    assert.equal(await sha256(path.join(pub, 'clip.mp4')), 'ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad');
  } finally { await rm(temp, {recursive: true, force: true}); }
});
