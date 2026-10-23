English | [简体中文](website.zh-CN.md)

# Website maintenance

The [MathCoffee website](https://sdt201909.github.io/MathCoffee/) introduces the
project to mathematics creators. Its main invitation is to start creating, with
community contribution alongside it. “Mathematics belongs to everyone” is the
English statement of the project's purpose.

The website is independent of the video production runtime. Work on it from a
repository checkout using Node.js 24; Manim, Remotion, Python environments, TeX,
models, recordings, and episode workspaces are not needed.

## Work locally

From the repository root:

```sh
cd site
npm ci --ignore-scripts --no-audit --no-fund
npm run build
npm test
npm run preview
```

Open the address printed by the preview command, retaining the `/MathCoffee/`
project prefix. The build writes only the generated website to `out/site/` at
the repository root. Test reports and screenshots belong in `out/site-review/`,
outside the production website.

The shared page template is in `site/page.mjs`, English and Chinese copy in
`site/content.mjs`, and visual styling in `site/styles.css`. Keep both languages
complete when changing a section or a control. The circle-to-sine illustration
is original website code, not a sample exported by the production plugin.

For browser checks, install the test browsers once:

```sh
npx playwright install chromium firefox webkit
npm run test:browser
```

To run a focused Chromium check locally:

```sh
BROWSER_PROJECTS=chromium npm run test:browser
```

Playwright's WebKit checks exercise a browser engine; they do not establish that
the page was manually reviewed in the installed Safari application. Review the
actual desktop and mobile layouts separately from automated checks. Check both
languages, both color schemes, keyboard focus, readable labels, reduced motion,
and installation links.

GitHub Actions checks Chromium, Firefox, and WebKit on Linux before publishing.
On macOS 27, bundled Firefox can fail before loading a page because of an
[upstream application-data access issue](https://github.com/microsoft/playwright/issues/42768).
Keep that launch failure distinct from a page failure. Do not change privacy
permissions or a user's Firefox profile to work around a website test; use the
Linux checks for Firefox coverage. For the other local engines, use
`BROWSER_PROJECTS=chromium,webkit npm run test:browser`.

## Language, theme, and release links

The root entry chooses a remembered explicit language preference, then the first
supported language in the browser's ordered preferences, then English. Chinese
variants use Simplified Chinese. Direct `/en/` and `/zh/` addresses retain their
language so that shared links are predictable. The language control remembers an
explicit choice for a future visit to the root entry.

Theme choices are System, Light, and Dark. System is the default and responds to
system changes. The site remains readable when preference storage is unavailable;
both static language pages are usable without JavaScript. The website adds no
analytics, external fonts, account system, model calls, or paid services.

Update `site/release.json` when promoting a release. Keep the visible version,
Codex and Claude Code package URLs, and versioned installation documentation in
agreement. The initial target is `v0.2.0-alpha.2`; do not replace its explicit
download links with an assumed “latest” prerelease URL. Check that both complete
plugin ZIPs exist before changing the configuration. GitHub's automatic source
archives are not installed plugin packages.

Keep the Community Alpha label and link the published validation status.
Availability of an adapter is distinct from completed host loading, a clean-Mac
trial, or human style and listening approval. See the
[implementation status](implementation_status.md).

## Publish and preserve the repository boundary

The `Website` workflow checks pull requests without publishing them. Changes to
the website on `main`, or a manual run of the workflow on `main`, build and check
the site before deployment. It uses pinned official GitHub Actions. Only the
deployment job receives Pages write and OpenID Connect permissions; no custom
deployment secret is needed. See GitHub's
[custom Pages workflow documentation](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages).

The repository's Pages source must be **GitHub Actions**. Use the `github-pages`
environment, restrict production deployment to `main`, and keep HTTPS enabled.
The public project address is `https://sdt201909.github.io/MathCoffee/`; no custom
domain or separate server is required. After deployment, check that address and
the two language pages over HTTPS, including the actual package download links.

Add each new source file to `repository-files.txt`. Preserve the guard's existing
restrictions on media and episode content. Use inline SVG and system fonts for
original graphics; do not commit historical scenes, videos, audio, models, font
binaries, screenshots, or build output. Only `out/site/` may be uploaded as the
Pages artifact. Never upload the repository root or a production workspace.

Check the repository guard and real distribution contents before merging:
website source, browser dependencies, generated pages, and review artifacts must
not enter the wheel or either host's plugin ZIP. Website documentation may be
included with other framework documentation. See the
[repository scope](repository_scope.md) for the allowlist and history checks.

The source distribution retains reviewed website source so it can rebuild the
package from its complete file manifest. It includes neither `node_modules` nor
generated website or browser-review artifacts. The wheel and host ZIPs carry
only relevant documentation, with no website runtime or test dependencies.
