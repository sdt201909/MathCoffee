import {createHash} from 'node:crypto';
import {createReadStream} from 'node:fs';
import {lstat, mkdir, readFile, realpath, stat, writeFile} from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {spawnSync} from 'node:child_process';
import {createRequire} from 'node:module';
import {bundle} from '@remotion/bundler';
import {ensureBrowser, openBrowser, selectComposition, renderMedia} from '@remotion/renderer';
import {parseTimeline, styleFontStack} from './src/schema.ts';

const root = path.dirname(fileURLToPath(import.meta.url));
const require = createRequire(import.meta.url);
export async function sha256(file) {
  const h = createHash('sha256');
  for await (const bytes of createReadStream(file)) h.update(bytes);
  return h.digest('hex');
}
export async function resolveAsset(publicDir, relativePath) {
  const base = await realpath(publicDir);
  const file = await realpath(path.join(base, relativePath));
  if (!file.startsWith(base + path.sep) || !(await stat(file)).isFile()) {
    throw new Error(`Asset resolves outside dedicated public directory: ${relativePath}`);
  }
  return file;
}
export async function verifyAssets(timeline, publicDir) {
  const receipts = [];
  for (const item of [...timeline.clips, ...(timeline.audio ? [timeline.audio] : [])]) {
    const file = await resolveAsset(publicDir, item.file);
    const digest = await sha256(file);
    if (digest !== item.sha256) throw new Error(`Source hash mismatch: ${item.file}`);
    const probe = spawnSync('ffprobe', ['-v', 'error', '-show_streams', '-of', 'json', file], {encoding: 'utf8'});
    if (probe.status !== 0) throw new Error(`Cannot probe asset ${item.file}: ${probe.stderr}`);
    const streams = JSON.parse(probe.stdout).streams;
    if ('renderer' in item) {
      const videos = streams.filter((s) => s.codec_type === 'video');
      const video = videos[0];
      if (videos.length !== 1 || video.width !== timeline.width || video.height !== timeline.height ||
          video.avg_frame_rate !== `${timeline.fps}/1` ||
          !Number.isFinite(Number(video.nb_frames)) ||
          item.source_in_frame + item.duration_frames > Number(video.nb_frames)) {
        throw new Error(`Clip dimensions, FPS, or source frame span mismatch: ${item.file}`);
      }
    } else {
      const audios = streams.filter((s) => s.codec_type === 'audio');
      const audio = audios[0];
      const [num, den] = (audio?.time_base ?? '0/1').split('/').map(Number);
      if (audios.length !== 1 || streams.some((s) => s.codec_type === 'video') ||
          Number(audio.sample_rate) !== 48000 || audio.channels !== 2 ||
          Number(audio.duration_ts) * num * 48000 !== item.samples * den) {
        throw new Error(`Premix must be stereo 48 kHz with the declared sample count: ${item.file}`);
      }
    }
    receipts.push({file: item.file, bytes: (await stat(file)).size, sha256: digest});
  }
  return receipts;
}
export async function refuseExisting(file) {
  try { await lstat(file); }
  catch (err) { if (err.code === 'ENOENT') return; throw err; }
  throw new Error(`Refusing to overwrite existing output: ${file}`);
}

function videoBitstreamHash(file) {
  const command = ['-v', 'error', '-nostdin', '-i', file, '-map', '0:v:0', '-c:v', 'copy', '-f', 'hash', '-hash', 'sha256', 'pipe:1'];
  const result = spawnSync('ffmpeg', command, {encoding: 'utf8'});
  if (result.status !== 0 || !/^SHA256=[a-f0-9]{64}\s*$/u.test(result.stdout)) throw new Error(`Cannot fingerprint copied video packets: ${result.stderr}`);
  return result.stdout.trim();
}

export async function muxExactPremix(picture, output, timeline, publicDir) {
  const premix = await resolveAsset(publicDir, timeline.audio.file);
  if (await sha256(premix) !== timeline.audio.sha256) throw new Error('Premix changed before final mux');
  const pictureHash = await sha256(picture);
  const bitstreamBefore = videoBitstreamHash(picture);
  const command = ['ffmpeg', '-v', 'error', '-nostdin', '-n', '-i', picture, '-i', premix,
    '-map', '0:v:0', '-map', '1:a:0', '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k',
    '-ar', '48000', '-ac', '2', '-movflags', '+faststart', output];
  const result = spawnSync(command[0], command.slice(1), {encoding: 'utf8'});
  if (result.status !== 0) throw new Error(`Exact premix mux failed: ${result.stderr}`);
  const bitstreamAfter = videoBitstreamHash(output);
  if (bitstreamBefore !== bitstreamAfter) throw new Error('Final mux changed video packets');
  if (pictureHash !== await sha256(picture) || timeline.audio.sha256 !== await sha256(premix)) throw new Error('Picture or premix changed during mux');
  const version = spawnSync('ffmpeg', ['-version'], {encoding: 'utf8'});
  if (version.status !== 0) throw new Error('Cannot identify native FFmpeg');
  return {command, policy: 'one native AAC encode from exact original premix; picture stream copied without re-encoding or retiming',
    ffmpeg_version: version.stdout.trim(), picture: {file: picture, sha256: pictureHash},
    premix: {file: premix, sha256: timeline.audio.sha256, samples: timeline.audio.samples},
    video_bitstream_sha256_before: bitstreamBefore, video_bitstream_sha256_after: bitstreamAfter};
}

export function argumentsFrom(argv) {
  const values = {};
  for (let i = 0; i < argv.length; i++) {
    const flag = argv[i];
    if (flag === '--no-audio') values.noAudio = true;
    else if (['--props', '--public-dir', '--output', '--browser-executable'].includes(flag)) {
      if (!argv[i + 1] || argv[i + 1].startsWith('--')) throw new Error(`Missing value for ${flag}`);
      values[flag.slice(2)] = argv[++i];
    } else throw new Error(`Unknown argument: ${flag}`);
  }
  for (const name of ['props', 'public-dir', 'output']) {
    if (!values[name] || !path.isAbsolute(values[name])) throw new Error(`--${name} requires an absolute path`);
  }
  if (!values.output.endsWith('.mp4')) throw new Error('Output must be an .mp4 file');
  return values;
}
async function fingerprintSources() {
  const files = ['package.json', 'package-lock.json', 'tsconfig.json', 'render.mjs', 'src/schema.ts', 'src/index.tsx', 'src/Timeline.tsx'];
  return Object.fromEntries(await Promise.all(files.map(async (file) => [file, await sha256(path.join(root, file))])));
}
async function main() {
  const invocationCwd = process.cwd();
  // Keep browser lookup, npm dependencies and bundler config isolated even when
  // called from the Python project root through an orchestration script.
  process.chdir(root);
  const args = argumentsFrom(process.argv.slice(2));
  for (const file of [args.output, `${args.output}.render.json`]) await refuseExisting(file);
  const startedAt = new Date();
  const propsBytes = await readFile(args.props);
  const timeline = parseTimeline(JSON.parse(propsBytes), Boolean(args.noAudio));
  if (args.noAudio && timeline.audio) throw new Error('--no-audio requires audio:null; it never silently discards an authored mix');
  const propsSha256 = createHash('sha256').update(propsBytes).digest('hex');
  const assets = await verifyAssets(timeline, args['public-dir']);
  const sourceHashes = await fingerprintSources();
  const outputDir = path.dirname(args.output);
  await mkdir(outputDir, {recursive: true});
  const cacheDir = path.join(outputDir, '.remotion-cache', path.basename(args.output, '.mp4'));
  const pictureOutput = timeline.audio ? path.join(cacheDir, 'picture.mp4') : args.output;
  if (pictureOutput !== args.output) await refuseExisting(pictureOutput);
  const browserOptions = {logLevel: 'info', ...(args['browser-executable'] ? {browserExecutable: args['browser-executable']} : {})};
  const browserStatus = await ensureBrowser(browserOptions);
  if (!('path' in browserStatus)) throw new Error(`Browser unavailable: ${browserStatus.type}`);
  browserOptions.browserExecutable = browserStatus.path;
  const chromeVersion = spawnSync(browserStatus.path, ['--version'], {encoding: 'utf8'});
  if (chromeVersion.status !== 0) throw new Error('Cannot identify installed Chrome version');
  const browserVersion = chromeVersion.stdout.trim();
  const serveUrl = await bundle({entryPoint: path.join(root, 'src/index.tsx'), publicDir: args['public-dir'], outDir: path.join(cacheDir, 'bundle'), onProgress: (p) => {if (p === 100) console.log('Bundle ready');}});
  const browser = await openBrowser('chrome', browserOptions);
  try {
    const composition = await selectComposition({serveUrl, id: 'MathCoffeeTimeline', inputProps: timeline, puppeteerInstance: browser, logLevel: 'warn'});
    let lastProgress = -1;
    await renderMedia({composition, serveUrl, inputProps: timeline, outputLocation: pictureOutput, muted: true, codec: 'h264', pixelFormat: 'yuv420p', crf: 18, x264Preset: 'medium', concurrency: 2, offthreadVideoCacheSizeInBytes: 256 * 1024 * 1024, puppeteerInstance: browser, overwrite: false, logLevel: 'warn', onProgress: ({progress}) => {
      const mark = Math.floor(progress * 10);
      if (mark !== lastProgress) {lastProgress = mark; console.log(`Rendering ${mark * 10}%`);}
    }});
  } finally { await browser.close({silent: true}); }
  const audioMux = timeline.audio ? await muxExactPremix(pictureOutput, args.output, timeline, args['public-dir']) : null;
  if (propsSha256 !== await sha256(args.props)) throw new Error('Props changed during render');
  if (JSON.stringify(sourceHashes) !== JSON.stringify(await fingerprintSources())) throw new Error('Renderer sources changed during render');
  await verifyAssets(timeline, args['public-dir']);
  const probe = spawnSync('ffprobe', ['-v', 'error', '-show_streams', '-show_format', '-of', 'json', args.output], {encoding: 'utf8'});
  if (probe.status !== 0) throw new Error(`ffprobe failed: ${probe.stderr}`);
  const media = JSON.parse(probe.stdout);
  const videos = media.streams.filter((s) => s.codec_type === 'video');
  const audios = media.streams.filter((s) => s.codec_type === 'audio');
  const v = videos[0];
  const a = audios[0];
  if (videos.length !== 1 || v.width !== timeline.width || v.height !== timeline.height ||
      v.avg_frame_rate !== `${timeline.fps}/1` || Number(v.nb_frames) !== timeline.duration_frames) {
    throw new Error('Rendered video metadata does not match the timeline');
  }
  if (timeline.audio ? audios.length !== 1 || Number(a?.sample_rate) !== 48000 || a?.channels !== 2 : audios.length !== 0) throw new Error('Missing or unexpected output audio track');
  if (timeline.audio) {
    const [num, den] = a.time_base.split('/').map(Number);
    if (a.codec_name !== 'aac' || Number(a.start_pts) !== 0 || Number(a.duration_ts) * num * 48000 !== timeline.audio.samples * den) throw new Error('Final native AAC container clock differs from exact original premix');
  }
  const receipt = {
    schema_version: 1, success: true, composition: 'MathCoffeeTimeline', started_at: startedAt.toISOString(), finished_at: new Date().toISOString(),
    elapsed_seconds: (Date.now() - startedAt.getTime()) / 1000,
    command: [process.execPath, ...process.argv.slice(1)],
    invocation_cwd: invocationCwd, renderer_cwd: root,
    remotion_version: require('remotion/package.json').version,
    node_version: process.version, platform: process.platform, arch: process.arch,
    browser_version: browserVersion, browser_executable: browserStatus.path, browser_sha256: await sha256(browserStatus.path), browser_executable_override: args['browser-executable'] ?? null,
    font_stack: timeline.style ? styleFontStack(timeline.style) : 'PingFang SC, Hiragino Sans GB, sans-serif',
    props: {file: args.props, sha256: propsSha256}, renderer_sources: sourceHashes, assets, audio_mux: audioMux,
    parameters: {concurrency: 2, offthread_video_cache_bytes: 268435456, codec: 'h264', pixel_format: 'yuv420p', crf: 18, preset: 'medium', audio_codec: 'aac', sample_rate: 48000, license_key_set: false},
    expected: {width: timeline.width, height: timeline.height, fps: timeline.fps, frames: timeline.duration_frames, duration_seconds: timeline.duration_frames / timeline.fps, has_audio: Boolean(timeline.audio)},
    qa_anchor_roi_at_1920x1080: {x: 1840, y: 80, width: 32, height: 32, duration_frames: 2},
    output: {file: args.output, bytes: (await stat(args.output)).size, sha256: await sha256(args.output)}, media,
    validation_scope: 'Metadata and source integrity; full decode, captions and audio sync require the project verifier.',
  };
  await writeFile(`${args.output}.render.json`, JSON.stringify(receipt, null, 2) + '\n', {flag: 'wx'});
  console.log(JSON.stringify(receipt.output));
}
if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  main().catch((err) => {console.error(err.stack ?? String(err)); process.exitCode = 1;});
}
