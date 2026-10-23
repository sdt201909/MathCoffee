import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import net from 'node:net';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { chromium, firefox, webkit } from 'playwright';

const here = path.dirname(fileURLToPath(import.meta.url));
const review = path.resolve(here, '../out/site-review');
const release = JSON.parse(await readFile(path.join(here, 'release.json'), 'utf8'));
const requested = (process.env.BROWSER_PROJECTS ?? 'chromium,webkit,firefox').split(',').map((name) => name.trim()).filter(Boolean);
const engines = { chromium, webkit, firefox };
const results = [];
const screenshots = [];
const delay = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
let server;
let serverLog = '';

async function availablePort() {
  const probe = net.createServer();
  await new Promise((resolve, reject) => probe.once('error', reject).listen(0, '127.0.0.1', resolve));
  const port = probe.address().port;
  await new Promise((resolve) => probe.close(resolve));
  return port;
}

async function startPreview() {
  if (process.env.SITE_TEST_URL) return process.env.SITE_TEST_URL.replace(/\/$/, '');
  const port = await availablePort();
  const origin = `http://127.0.0.1:${port}`;
  server = spawn(process.execPath, ['preview.mjs', '--port', String(port)], { cwd: here, stdio: ['ignore', 'pipe', 'pipe'] });
  server.stdout.on('data', (chunk) => { serverLog += chunk; });
  server.stderr.on('data', (chunk) => { serverLog += chunk; });
  for (let attempt = 0; attempt < 100; attempt++) {
    if (server.exitCode !== null) throw new Error(`Preview server exited: ${serverLog}`);
    try {
      if ((await fetch(`${origin}/MathCoffee/en/`)).ok) return `${origin}/MathCoffee`;
    } catch {}
    await delay(100);
  }
  throw new Error(`Preview server did not start: ${serverLog}`);
}

async function eventually(probe, message) {
  let last;
  for (let attempt = 0; attempt < 40; attempt++) {
    try {
      if (await probe()) return;
    } catch (error) { last = error; }
    await delay(50);
  }
  throw new Error(`${message}${last ? `: ${last.message}` : ''}`);
}

async function check(browser, engine, name, options, operation) {
  const context = await browser.newContext({ viewport: { width: 1280, height: 900 }, colorScheme: 'light', reducedMotion: 'reduce', ...options });
  const errors = [];
  context.on('page', (page) => {
    page.on('pageerror', (error) => errors.push(error.message));
    page.on('console', (message) => { if (message.type() === 'error') errors.push(message.text()); });
  });
  const started = Date.now();
  try {
    await operation(context);
    assert.deepEqual(errors, [], 'Browser console/page errors');
    results.push({ engine, name, status: 'passed', durationMs: Date.now() - started });
    console.log(`PASS ${engine}: ${name}`);
  } catch (error) {
    results.push({ engine, name, status: 'failed', durationMs: Date.now() - started, error: error.stack });
    console.error(`FAIL ${engine}: ${name}\n${error.stack}`);
  } finally {
    await context.close();
  }
}

async function language(context, values) {
  await context.addInitScript((languages) => {
    Object.defineProperty(navigator, 'languages', { configurable: true, get: () => languages });
    Object.defineProperty(navigator, 'language', { configurable: true, get: () => languages[0] ?? 'en' });
  }, values);
}

async function expectLanguage(page, expected) {
  await eventually(async () => new URL(page.url()).pathname.endsWith(`/${expected}/`), `Expected ${expected} route, got ${page.url()}`);
  assert.equal(await page.locator('html').getAttribute('lang'), expected === 'zh' ? 'zh-CN' : 'en');
  assert.ok((await page.locator('h1').innerText()).trim());
}

async function expectTheme(page, theme) {
  await eventually(async () => await page.locator('html').getAttribute('data-theme') === theme, `Expected ${theme} theme`);
  // A media-query event can update the attribute before Chromium invalidates
  // the corresponding style rules. Observe a painted state before sampling it.
  await page.evaluate(() => new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve))));
}

function rgb(value) {
  const hex = value.trim().match(/^#([\da-f]{6})$/i)?.[1];
  if (hex) return [0, 2, 4].map((index) => Number.parseInt(hex.slice(index, index + 2), 16));
  const parts = value.match(/[\d.]+/g)?.map(Number);
  assert.ok(parts?.length >= 3, `Expected a CSS rgb color, received ${value}`);
  return parts.slice(0, 3);
}

function contrast(first, second) {
  const luminance = (values) => values.map((value) => {
    const channel = value / 255;
    return channel <= 0.04045 ? channel / 12.92 : ((channel + 0.055) / 1.055) ** 2.4;
  }).reduce((total, channel, index) => total + channel * [0.2126, 0.7152, 0.0722][index], 0);
  const a = luminance(first);
  const b = luminance(second);
  return (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05);
}

await mkdir(review, { recursive: true });
let baseURL;
try {
  baseURL = await startPreview();
  for (const engine of requested) {
    assert.ok(engines[engine], `Unknown browser ${engine}`);
    let browser;
    try {
      browser = await engines[engine].launch();
    } catch (error) {
      results.push({ engine, name: 'launch', status: 'failed', error: error.stack });
      console.error(`FAIL ${engine}: launch\n${error.message}`);
      continue;
    }
    try {
      for (const [languages, expected] of [
        [['zh-Hant-TW', 'en-US'], 'zh'],
        [['en-GB', 'zh-CN'], 'en'],
        [['de-DE', 'zh-Hant'], 'zh'],
        [['fr-FR', 'de-DE'], 'en'],
      ]) {
        await check(browser, engine, `root language preference ${languages.join(',')}`, {}, async (context) => {
          await language(context, languages);
          const page = await context.newPage();
          await page.goto(`${baseURL}/`);
          await expectLanguage(page, expected);
        });
      }

      await check(browser, engine, 'explicit language routes, manual choice and remembered root', {}, async (context) => {
        await language(context, ['zh-CN']);
        const page = await context.newPage();
        await page.goto(`${baseURL}/en/`);
        await expectLanguage(page, 'en');
        await page.locator('[data-language-link="zh"]').first().click();
        await expectLanguage(page, 'zh');
        assert.equal(await page.evaluate(() => localStorage.getItem('mathcoffee.language')), 'zh');
        await page.goto(`${baseURL}/en/`);
        await expectLanguage(page, 'en');
        await page.goto(`${baseURL}/`);
        await expectLanguage(page, 'zh');
        await page.locator('[data-language-link="en"]').first().click();
        await expectLanguage(page, 'en');
        await page.goto(`${baseURL}/`);
        await expectLanguage(page, 'en');
      });

      await check(browser, engine, 'unavailable browser storage preserves navigation and theme controls', {}, async (context) => {
        await language(context, ['en-US']);
        await context.addInitScript(() => {
          Storage.prototype.getItem = () => { throw new DOMException('Blocked for test', 'SecurityError'); };
          Storage.prototype.setItem = () => { throw new DOMException('Blocked for test', 'SecurityError'); };
        });
        const page = await context.newPage();
        await page.goto(`${baseURL}/`);
        await expectLanguage(page, 'en');
        await page.locator('#theme-select').selectOption('dark');
        await expectTheme(page, 'dark');
        await page.locator('[data-language-link="zh"]').first().click();
        await expectLanguage(page, 'zh');
      });

      await check(browser, engine, 'system theme changes, manual override and reload persistence', { colorScheme: 'dark' }, async (context) => {
        const page = await context.newPage();
        await page.goto(`${baseURL}/en/`);
        await expectTheme(page, 'dark');
        assert.equal(await page.locator('#theme-select').inputValue(), 'system');
        await page.emulateMedia({ colorScheme: 'light' });
        await expectTheme(page, 'light');
        const light = await page.locator('body').evaluate((body) => getComputedStyle(body).backgroundColor);
        await page.locator('#theme-select').selectOption('dark');
        await expectTheme(page, 'dark');
        const dark = await page.locator('body').evaluate((body) => getComputedStyle(body).backgroundColor);
        assert.notEqual(light, dark, 'Theme changes must change the rendered colors');
        await page.emulateMedia({ colorScheme: 'dark' });
        await page.emulateMedia({ colorScheme: 'light' });
        await expectTheme(page, 'dark');
        await page.reload();
        await expectTheme(page, 'dark');
        assert.equal(await page.locator('#theme-select').inputValue(), 'dark');
        await page.locator('#theme-select').selectOption('system');
        await expectTheme(page, 'light');
      });

      await check(browser, engine, 'shared mathematical state, keyboard control and motion preference', { reducedMotion: 'no-preference' }, async (context) => {
        const page = await context.newPage();
        await page.goto(`${baseURL}/en/`);
        const angle = page.locator('#angle');
        const play = page.locator('#play-toggle');
        assert.equal(await play.getAttribute('aria-pressed'), 'false');
        await angle.evaluate((input) => { input.value = '90'; input.dispatchEvent(new Event('input', { bubbles: true })); });
        assert.match(await page.locator('#angle-value').innerText(), /90/);
        assert.equal(Number.parseFloat(await page.locator('#sine-value').innerText()), 1);
        const coordinates = await page.evaluate(() => Object.fromEntries(['circle-point', 'wave-point'].map((id) => {
          const point = document.getElementById(id);
          return [id, [Number(point.getAttribute('cx')), Number(point.getAttribute('cy'))]];
        })));
        for (const [id, expected] of [['circle-point', [150, 54]], ['wave-point', [440, 54]]]) {
          coordinates[id].forEach((value, index) => assert.ok(Math.abs(value - expected[index]) < 0.1, `${id} coordinate ${index}`));
        }
        const progressAtNinety = await page.locator('#wave-progress').getAttribute('points');
        const endpoint = progressAtNinety.trim().split(/\s+/).at(-1).split(',').map(Number);
        endpoint.forEach((value, index) => assert.ok(Math.abs(value - [440, 54][index]) < 0.1, `Progress curve endpoint ${index}`));
        await angle.focus();
        await page.keyboard.press('ArrowRight');
        assert.ok(Number(await angle.inputValue()) > 90, 'Native range keyboard interaction works');
        assert.notEqual(await page.locator('#wave-progress').getAttribute('points'), progressAtNinety, 'Progress curve follows the changed angle');
        const initial = await angle.inputValue();
        await play.focus();
        await page.keyboard.press('Enter');
        await eventually(async () => await play.getAttribute('aria-pressed') === 'true', 'Play keyboard activation');
        await eventually(async () => await angle.inputValue() !== initial, 'Playback advances the shared angle');
        await page.emulateMedia({ reducedMotion: 'reduce' });
        await eventually(async () => await play.getAttribute('aria-pressed') === 'false', 'Enabling reduced motion pauses animation');
        const paused = await angle.inputValue();
        await delay(200);
        assert.equal(await angle.inputValue(), paused);
        await page.reload();
        assert.equal(await play.getAttribute('aria-pressed'), 'false', 'Reduced motion begins paused');
      });

      for (const locale of ['en', 'zh']) {
        await check(browser, engine, `${locale} remains useful without JavaScript`, { javaScriptEnabled: false }, async (context) => {
          const page = await context.newPage();
          await page.goto(`${baseURL}/${locale}/`);
          await expectLanguage(page, locale);
          assert.ok((await page.locator('main').innerText()).length > 500);
          const other = locale === 'en' ? 'zh' : 'en';
          await page.locator(`[data-language-link="${other}"]`).first().click();
          await expectLanguage(page, other);
        });
      }

      for (const locale of ['en', 'zh']) {
        for (const colorScheme of ['light', 'dark']) {
          for (const width of [360, 768, 1440]) {
            await check(browser, engine, `${locale} ${colorScheme} layout at ${width}px`, { colorScheme, viewport: { width, height: width === 360 ? 800 : 1000 } }, async (context) => {
              const requests = [];
              context.on('request', (request) => requests.push(request.url()));
              const page = await context.newPage();
              await page.goto(`${baseURL}/${locale}/`);
              await expectTheme(page, colorScheme);
              await page.evaluate(() => document.fonts.ready);
              const dimensions = await page.evaluate(() => ({ width: innerWidth, document: document.documentElement.scrollWidth, body: document.body.scrollWidth }));
              assert.ok(dimensions.document <= dimensions.width + 1 && dimensions.body <= dimensions.width + 1, `Horizontal overflow: ${JSON.stringify(dimensions)}`);
              const heading = await page.locator('h1').boundingBox();
              assert.ok(heading && heading.x >= -1 && heading.x + heading.width <= width + 1, 'Hero headline fits viewport');
              const colors = await page.locator('h1').evaluate((element) => {
                let background;
                for (let ancestor = element; ancestor; ancestor = ancestor.parentElement) {
                  const color = getComputedStyle(ancestor).backgroundColor;
                  if (color !== 'transparent' && color !== 'rgba(0, 0, 0, 0)') { background = color; break; }
                }
                if (!background) {
                  // If all ancestors are transparent (including WebKit's
                  // canvas-propagated body), resolve the browser's actual
                  // Canvas system color under the current color scheme.
                  const probe = document.createElement('span');
                  probe.style.cssText = 'position:absolute;visibility:hidden;color:Canvas';
                  document.documentElement.append(probe);
                  background = getComputedStyle(probe).color;
                  probe.remove();
                }
                return { foreground: getComputedStyle(element).color, background };
              });
              assert.ok(contrast(rgb(colors.foreground), rgb(colors.background)) >= 4.5, 'Hero text has adequate contrast');
              assert.equal(await page.locator('link[rel="canonical"]').getAttribute('href'), `https://sdt201909.github.io/MathCoffee/${locale}/`);
              assert.ok(await page.locator(`a[href="${release.downloads.codex}"]`).count());
              assert.ok(await page.locator(`a[href="${release.downloads.claude}"]`).count());
              const brokenAnchors = await page.locator('a[href^="#"]').evaluateAll((links) => links.map((link) => link.getAttribute('href')).filter((href) => href.length > 1 && !document.getElementById(decodeURIComponent(href.slice(1)))));
              assert.deepEqual(brokenAnchors, []);
              assert.deepEqual(requests.filter((url) => /^https?:/.test(url) && new URL(url).origin !== new URL(baseURL).origin), [], 'Page must not request external fonts, scripts or analytics');
              if (engine === requested[0] && width !== 768) {
                const filename = `${engine}-${locale}-${colorScheme}-${width}.png`;
                await page.screenshot({ path: path.join(review, filename), fullPage: true, animations: 'disabled' });
                screenshots.push(filename);
              }
            });
          }
        }
      }
    } finally {
      await browser.close();
    }
  }
} catch (error) {
  results.push({ engine: 'setup', name: 'browser test setup', status: 'failed', error: error.stack });
  console.error(error.stack);
} finally {
  server?.kill('SIGTERM');
  const report = {
    generatedAt: new Date().toISOString(),
    baseURL,
    requestedBrowsers: requested,
    passed: results.filter((result) => result.status === 'passed').length,
    failed: results.filter((result) => result.status === 'failed').length,
    screenshots,
    results,
    note: 'Playwright Chromium, WebKit and Firefox engine checks are automated. WebKit does not establish manual Safari acceptance.',
  };
  await writeFile(path.join(review, 'browser-report.json'), `${JSON.stringify(report, null, 2)}\n`);
  console.log(`Browser report: ${report.passed} passed, ${report.failed} failed; ${screenshots.length} screenshots in ${review}`);
  if (report.failed) process.exitCode = 1;
}
