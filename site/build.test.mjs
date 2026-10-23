import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { readdir, readFile, stat } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import test, { before } from 'node:test';

const here = path.dirname(fileURLToPath(import.meta.url));
const output = path.resolve(here, '../out/site');
const basePath = '/MathCoffee';
const release = JSON.parse(await readFile(path.join(here, 'release.json'), 'utf8'));
let pages;

function attributes(tag) {
  return Object.fromEntries([...tag.matchAll(/([\w:-]+)\s*=\s*["']([^"']*)["']/g)].map((match) => [match[1], match[2]]));
}

async function filesUnder(directory, prefix = '') {
  const files = [];
  for (const entry of await readdir(directory, { withFileTypes: true })) {
    const name = path.posix.join(prefix, entry.name);
    if (entry.isDirectory()) files.push(...await filesUnder(path.join(directory, entry.name), name));
    else {
      assert.ok(entry.isFile(), `Site artifacts must be regular files: ${name}`);
      files.push(name);
    }
  }
  return files;
}

before(async () => {
  execFileSync(process.execPath, ['build.mjs'], { cwd: here, stdio: 'pipe' });
  pages = Object.fromEntries(await Promise.all(['en', 'zh'].map(async (locale) => [
    locale,
    await readFile(path.join(output, locale, 'index.html'), 'utf8'),
  ])));
});

test('both languages are complete static documents with language and sharing metadata', async () => {
  for (const [locale, html] of Object.entries(pages)) {
    assert.match(html, /<!doctype html>/i);
    const lang = attributes(html.match(/<html\b[^>]*>/i)?.[0] ?? '').lang;
    assert.equal(lang, locale === 'zh' ? 'zh-CN' : 'en');
    assert.match(html, /<main\b/);
    assert.match(html, /<h1\b/);
    const text = html.replace(/<script\b[^>]*>[\s\S]*?<\/script>/gi, '').replace(/<[^>]*>/g, ' ').replace(/\s+/g, ' ');
    assert.ok(text.length > 500, `${locale} has real pre-rendered page content`);
    assert.match(text, locale === 'zh' ? /数学应是大众的[，, ]+而非特权/ : /Mathematics belongs to everyone/);
    assert.match(text, /Alpha/i);
    assert.match(text, /Apple Silicon/);

    const links = [...html.matchAll(/<link\b[^>]*>/gi)].map((match) => attributes(match[0]));
    assert.ok(links.some((link) => link.rel === 'canonical' && link.href === `https://sdt201909.github.io${basePath}/${locale}/`));
    for (const [language, route] of [['en', 'en'], ['zh-CN', 'zh']]) {
      assert.ok(links.some((link) => link.rel === 'alternate' && link.hreflang === language && link.href.endsWith(`${basePath}/${route}/`)), `Missing ${language} alternate`);
    }
    const metadata = [...html.matchAll(/<meta\b[^>]*>/gi)].map((match) => attributes(match[0]));
    for (const name of ['og:title', 'og:description', 'og:url']) {
      assert.ok(metadata.some((meta) => meta.property === name && meta.content), `Missing ${name}`);
    }
    assert.ok(metadata.some((meta) => meta.name === 'description' && meta.content));
  }
});

test('release download links use the configured complete host bundles', () => {
  assert.equal(release.tag, `v${release.version}`);
  assert.match(release.repository, /^https:\/\/github\.com\/sdt201909\/MathCoffee$/);
  for (const host of ['codex', 'claude']) {
    const download = new URL(release.downloads[host]);
    assert.equal(download.origin, 'https://github.com');
    assert.ok(download.pathname.includes(`/releases/download/${release.tag}/`));
    assert.ok(download.pathname.endsWith('.zip'));
    for (const html of Object.values(pages)) assert.ok(html.includes(release.downloads[host]), `${host} bundle missing`);
  }
  for (const html of Object.values(pages)) {
    assert.ok(!html.includes('/releases/latest'), 'Prerelease downloads must not use the latest-release shortcut');
    assert.ok(html.includes(`/blob/${release.tag}/docs/installation`), 'Installation docs must match the offered release');
  }
});

test('project subpath links and local assets resolve inside the generated artifact', async () => {
  for (const [locale, html] of Object.entries(pages)) {
    for (const tag of html.matchAll(/<(?:a|script|link)\b[^>]*>/gi)) {
      const attrs = attributes(tag[0]);
      const address = attrs.src ?? attrs.href;
      if (!address || /^(?:https?:|mailto:|data:)/.test(address)) continue;
      if (address.startsWith('#')) {
        assert.ok(html.includes(`id="${address.slice(1)}"`) || html.includes(`id='${address.slice(1)}'`), `${locale}: missing anchor ${address}`);
        continue;
      }
      const url = new URL(address, `https://sdt201909.github.io${basePath}/${locale}/`);
      assert.ok(url.pathname.startsWith(`${basePath}/`), `Asset escaped project subpath: ${address}`);
      const relative = decodeURIComponent(url.pathname.slice(basePath.length + 1));
      const target = path.join(output, relative, url.pathname.endsWith('/') ? 'index.html' : '');
      assert.ok((await stat(target)).isFile(), `${address} did not resolve to a file`);
    }
  }
});

test('artifact is limited to the standalone website and has no third-party runtime requests', async () => {
  const files = await filesUnder(output);
  for (const expected of ['index.html', 'en/index.html', 'zh/index.html', 'assets/styles.css', 'assets/preferences.js', 'assets/app.js']) {
    assert.ok(files.includes(expected), `Missing ${expected}`);
  }
  for (const file of files) {
    assert.ok(!/(?:^|\/)(?:src|media|episodes|scenes|models|node_modules|\.git|\.venv)(?:\/|$)/.test(file), `Non-site artifact: ${file}`);
    assert.ok(!/\.(?:whl|zip|mp4|mov|wav|mp3|safetensors|onnx|py|pyc)$/.test(file), `Production dependency in website: ${file}`);
    const size = (await stat(path.join(output, file))).size;
    assert.ok(size < 512_000, `Unexpectedly large website artifact: ${file}`);
  }
  for (const html of Object.values(pages)) {
    const externalScripts = [...html.matchAll(/<script\b[^>]*>/gi)].map((match) => attributes(match[0]).src).filter((src) => /^https?:/.test(src ?? ''));
    assert.deepEqual(externalScripts, []);
    assert.ok(!/fonts\.googleapis|fonts\.gstatic|google-analytics|googletagmanager|plausible\.io|cdn\.jsdelivr/i.test(html));
  }
});
