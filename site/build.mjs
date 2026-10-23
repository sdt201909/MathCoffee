import { readFile, mkdir, writeFile, copyFile, readdir } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import { createHash } from 'node:crypto';
import { renderPage } from './page.mjs';

const directory = path.dirname(fileURLToPath(import.meta.url));
export const outputDirectory = path.resolve(directory, '../out/site');
export const siteUrl = 'https://sdt201909.github.io/MathCoffee';
export const basePath = '/MathCoffee';

export async function build() {
  const release = JSON.parse(await readFile(path.join(directory, 'release.json'), 'utf8'));
  if (release.repository !== 'https://github.com/sdt201909/MathCoffee' || release.tag !== `v${release.version}`) {
    throw new Error('Release configuration must name a consistent MathCoffee release.');
  }
  for (const host of ['codex', 'claude']) {
    if (!release.downloads[host]?.startsWith(`${release.repository}/releases/download/${release.tag}/`)) {
      throw new Error(`Missing versioned download for ${host}.`);
    }
  }
  await mkdir(path.join(outputDirectory, 'assets'), { recursive: true });
  const assets = ['styles.css', 'preferences.js', 'app.js'];
  const hashes = {};
  for (const filename of assets) {
    const bytes = await readFile(path.join(directory, filename));
    hashes[filename] = createHash('sha256').update(bytes).digest('hex').slice(0, 12);
    await copyFile(path.join(directory, filename), path.join(outputDirectory, 'assets', filename));
  }
  const versionAssets = (html) => assets.reduce((value, filename) => value.replaceAll(`/assets/${filename}"`, `/assets/${filename}?v=${hashes[filename]}"`), html);
  for (const locale of ['en', 'zh']) {
    const html = versionAssets(renderPage({ locale, release, siteUrl, basePath }));
    await mkdir(path.join(outputDirectory, locale), { recursive: true });
    await writeFile(path.join(outputDirectory, locale, 'index.html'), html);
    if (locale === 'en') {
      await writeFile(path.join(outputDirectory, 'index.html'), html.replace('<html ', '<html data-auto-language="true" '));
    }
  }
  await writeFile(path.join(outputDirectory, '.nojekyll'), '');
  await writeFile(path.join(outputDirectory, 'robots.txt'), `User-agent: *\nAllow: /\nSitemap: ${siteUrl}/sitemap.xml\n`);
  await writeFile(path.join(outputDirectory, 'sitemap.xml'), `<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">${['en', 'zh'].map((locale) => `<url><loc>${siteUrl}/${locale}/</loc></url>`).join('')}</urlset>\n`);
  await writeFile(path.join(outputDirectory, '404.html'), `<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><meta name="robots" content="noindex"><title>Page not found · MathCoffee</title><link rel="stylesheet" href="${basePath}/assets/styles.css?v=${hashes['styles.css']}"><body><main class="container" style="padding-block:6rem"><h1>Let’s find our way back.</h1><p>This page is not here. / 此页面不存在。</p><p><a href="${basePath}/en/">English homepage</a> · <a href="${basePath}/zh/" lang="zh-CN">中文主页</a></p></main></body></html>\n`);
  const allowed = new Set(['assets/styles.css', 'assets/preferences.js', 'assets/app.js', 'en/index.html', 'zh/index.html', 'index.html', '404.html', '.nojekyll', 'robots.txt', 'sitemap.xml']);
  const entries = await readdir(outputDirectory, { recursive: true, withFileTypes: true });
  for (const entry of entries) {
    const relative = path.relative(outputDirectory, path.join(entry.parentPath, entry.name)).split(path.sep).join('/');
    if (entry.isSymbolicLink() || (!entry.isDirectory() && !allowed.has(relative))) {
      throw new Error(`Unexpected website artifact: ${relative}. Build in a clean output directory.`);
    }
  }
  console.log(`Built English and Chinese pages in ${outputDirectory}`);
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) await build();
