import { content } from './content.mjs';

const escape = (value) => String(value).replace(/[&<>"']/g, (character) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[character]));
const arrow = '<svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M5 12h14m-6-6 6 6-6 6" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>';
const arrowUp = '<svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M6 18 18 6M6 6h12v12" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>';
const brandSymbol = '<svg class="brand-symbol" viewBox="0 0 40 40" fill="none" aria-hidden="true"><circle cx="20" cy="20" r="16" stroke="currentColor" stroke-width="1.5"/><path d="M5 21c5 0 7-9 12-9s6 16 12 16c3 0 5-4 7-7" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"/></svg>';
const favicon = 'data:image/svg+xml,' + encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 40 40"><rect width="40" height="40" rx="8" fill="#fafaf7"/><g fill="none" stroke="#1767c5" stroke-width="1.8"><circle cx="20" cy="20" r="16"/><path d="M5 21c5 0 7-9 12-9s6 16 12 16c3 0 5-4 7-7"/></g></svg>');

function valueIcon(kind) {
  const paths = {
    understand: '<circle cx="24" cy="24" r="16"/><path d="m13 28 8-9 7 8 8-12"/><circle cx="21" cy="19" r="2" fill="currentColor" stroke="none"/>',
    reuse: '<rect x="8" y="8" width="22" height="22" rx="2"/><rect x="18" y="18" width="22" height="22" rx="2"/><path d="M8 19h10m12 11h10"/>',
    open: '<path d="M9 36V12l15-4v32L9 36Zm15-28 15 4v24l-15 4"/><path d="M15 17h3m-3 7h3m12-7h3m-3 7h3"/>',
  };
  return `<svg class="value-icon" viewBox="0 0 48 48" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${paths[kind]}</svg>`;
}

function mathFigure(c) {
  const points = Array.from({ length: 181 }, (_, i) => {
    const degrees = i * 2;
    return `${350 + degrees},${(150 - 96 * Math.sin(degrees * Math.PI / 180)).toFixed(3)}`;
  }).join(' ');
  const progress = Array.from({ length: 46 }, (_, degrees) => `${350 + degrees},${(150 - 96 * Math.sin(degrees * Math.PI / 180)).toFixed(3)}`).join(' ');
  return `<figure class="math-figure" aria-labelledby="figure-heading">
    <div class="figure-heading"><h2 id="figure-heading">${c.figureTitle}</h2><span class="js-only">${c.figureHint}</span></div>
    <div class="diagram-wrap">
      <svg class="math-diagram" viewBox="0 0 760 300" role="img" aria-labelledby="diagram-title diagram-description">
        <title id="diagram-title">${c.diagramTitle}</title><desc id="diagram-description">${c.diagramDescription}</desc>
        <defs><pattern id="diagram-grid" x="6" y="6" width="24" height="24" patternUnits="userSpaceOnUse"><circle cx="1" cy="1" r="0.7" fill="currentColor"/></pattern></defs>
        <rect width="760" height="300" fill="url(#diagram-grid)" class="diagram-grid"/>
        <g class="diagram-axis" fill="none" stroke-width="1"><path d="M30 150H270M150 30V270M330 150H730M350 35V265"/><path d="m265 147 5 3-5 3m-118-115 3-5 3 5m572 112 5 3-5 3"/></g>
        <circle cx="150" cy="150" r="96" class="unit-circle" fill="none" stroke-width="1.5"/>
        <polyline points="${points}" class="sine-background" fill="none" stroke-width="1.5"/>
        <polyline id="wave-progress" points="${progress}" class="sine-wave" fill="none" stroke-width="2.5" stroke-linecap="round"/>
        <line id="projection-line" x1="217.882" y1="82.118" x2="395" y2="82.118" class="projection-line" stroke-width="1.3" stroke-dasharray="4 5"/>
        <line id="radius" x1="150" y1="150" x2="217.882" y2="82.118" class="radius-line" stroke-width="2"/>
        <path id="angle-arc" d="M176 150A26 26 0 0 0 168.385 131.615" class="angle-arc" fill="none" stroke-width="1.5"/>
        <circle cx="150" cy="150" r="3" class="origin-point"/><circle id="circle-point" cx="217.882" cy="82.118" r="6" class="circle-point"/><circle id="wave-point" cx="395" cy="82.118" r="6" class="wave-point"/>
        <g class="diagram-label"><text x="153" y="287" text-anchor="middle">${c.circleLabel}</text><text x="532" y="287" text-anchor="middle">${c.waveLabel}</text></g>
        <g class="axis-label"><text x="254" y="169">x</text><text x="161" y="44">y</text><text x="340" y="170">0</text><text x="520" y="170">π</text><text x="700" y="170">2π</text><text x="333" y="60" text-anchor="end">1</text><text x="333" y="250" text-anchor="end">−1</text></g>
        <text x="186" y="137" class="theta-label">θ</text>
        <text x="712" y="41" text-anchor="end" class="formula-label">y = sin θ</text>
      </svg>
    </div>
    <div class="figure-controls js-only"><button id="play-toggle" type="button" aria-pressed="false" data-play-label="${c.play}" data-pause-label="${c.pause}"><span class="play-icon" aria-hidden="true">▶</span><span data-play-text>${c.play}</span></button><label for="angle">${c.angle} <output id="angle-value" for="angle">45°</output></label><input id="angle" type="range" min="0" max="360" value="45" step="1" aria-label="${c.angle}"><span class="sine-readout">sin θ = <output id="sine-value" for="angle">0.707</output></span></div>
    <figcaption><span class="figure-note-dot" aria-hidden="true"></span>${c.figureNote}</figcaption>
  </figure>`;
}

export function renderPage({ locale, release, siteUrl, basePath }) {
  const c = content[locale];
  if (!c) throw new Error(`Unsupported locale: ${locale}`);
  const repo = release.repository;
  const suffix = locale === 'zh' ? '.zh-CN' : '';
  const docs = (name) => `${repo}/blob/${release.tag}/docs/${name}${suffix}.md`;
  const docMain = (name) => `${repo}/blob/main/docs/${name}${suffix}.md`;
  const rootDoc = (name) => `${repo}/blob/main/${name}${suffix}.md`;
  const local = (language) => `${basePath}/${language}/`;
  const canonical = `${siteUrl}/${locale}/`;
  return `<!doctype html>
<html lang="${c.lang}" data-language="${locale}">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="color-scheme" content="light dark">
  <link rel="icon" href="${favicon}">
  <title>${escape(c.title)}</title>
  <meta name="description" content="${escape(c.description)}">
  <link rel="canonical" href="${canonical}">
  <link rel="alternate" hreflang="en" href="${siteUrl}/en/">
  <link rel="alternate" hreflang="zh-CN" href="${siteUrl}/zh/">
  <link rel="alternate" hreflang="x-default" href="${siteUrl}/">
  <meta property="og:type" content="website"><meta property="og:site_name" content="MathCoffee">
  <meta property="og:title" content="${escape(c.title)}"><meta property="og:description" content="${escape(c.description)}">
  <meta property="og:url" content="${canonical}"><meta property="og:locale" content="${locale === 'zh' ? 'zh_CN' : 'en_US'}"><meta property="og:locale:alternate" content="${locale === 'zh' ? 'en_US' : 'zh_CN'}">
  <meta name="twitter:card" content="summary"><meta name="twitter:title" content="${escape(c.title)}"><meta name="twitter:description" content="${escape(c.description)}">
  <script src="${basePath}/assets/preferences.js"></script>
  <link rel="stylesheet" href="${basePath}/assets/styles.css">
  <script type="module" src="${basePath}/assets/app.js"></script>
</head>
<body id="top">
<a class="skip-link" href="#main">${c.skip}</a>
<header class="site-header"><div class="header-inner shell">
  <a class="brand" href="${local(locale)}" aria-label="MathCoffee">${brandSymbol}<span>MathCoffee<span class="brand-period">.</span></span></a>
  <nav class="main-nav" aria-label="${c.navLabel}"><a href="#why">${c.nav.features}</a><a href="#workflow">${c.nav.workflow}</a><a href="#community">${c.nav.community}</a></nav>
  <div class="preferences"><div class="language-switch" role="group" aria-label="${c.language}"><a href="${local('en')}" data-language-link="en" lang="en"${locale === 'en' ? ' aria-current="page"' : ''}>EN</a><span aria-hidden="true">/</span><a href="${local('zh')}" data-language-link="zh" lang="zh-CN"${locale === 'zh' ? ' aria-current="page"' : ''}>中文</a></div><div class="theme-control js-only"><label class="sr-only" for="theme-select">${c.theme}</label><svg viewBox="0 0 24 24" aria-hidden="true" fill="none"><circle cx="12" cy="12" r="7" stroke="currentColor" stroke-width="1.5"/><path d="M12 5a7 7 0 0 1 0 14V5Z" fill="currentColor"/></svg><select id="theme-select" aria-label="${c.theme}">${['system', 'light', 'dark'].map((theme, i) => `<option value="${theme}">${c.themes[i]}</option>`).join('')}</select></div></div>
</div></header>
<main id="main">
  <section class="hero shell" aria-labelledby="hero-title">
    <p class="eyebrow"><span class="status-dot" aria-hidden="true"></span>${c.eyebrow}</p>
    <div class="hero-copy"><h1 id="hero-title">${c.headline}</h1><div class="hero-aside"><p class="hero-intro">${c.intro}</p><p class="hero-detail">${c.introDetail}</p></div></div>
    <div class="hero-actions"><a class="button button-primary" href="#get-started">${c.start}${arrow}</a><a class="text-link" href="${repo}">${c.github}${arrowUp}</a><p class="hero-note">${c.heroNote}</p></div>
    ${mathFigure(c)}
  </section>
  <section id="why" class="values-section shell section-space" aria-labelledby="values-title">
    <div class="section-heading"><div><p class="eyebrow">${c.valueEyebrow}</p><h2 id="values-title">${c.valueTitle}</h2></div><p class="section-intro">${c.valueIntro}</p></div>
    <div class="value-grid">${c.values.map((value, index) => `<article class="value-item"><div class="value-top">${valueIcon(value.icon)}<span class="item-number">0${index + 1}</span></div><h3>${value.title}</h3><p>${value.text}</p></article>`).join('')}</div>
  </section>
  <section id="workflow" class="workflow-section" aria-labelledby="workflow-title"><div class="shell workflow-inner section-space"><div class="workflow-copy"><p class="eyebrow">${c.workflowEyebrow}</p><h2 id="workflow-title">${c.workflowTitle}</h2><p class="section-intro">${c.workflowIntro}</p><p class="workflow-note">${c.workflowNote}</p></div><ol class="workflow-steps">${c.steps.map((step, index) => `<li><span class="step-number">0${index + 1}</span><div><h3>${step.title}</h3><p>${step.text}</p></div></li>`).join('')}</ol></div></section>
  <section id="get-started" class="get-started shell section-space" aria-labelledby="start-title"><div class="section-heading"><div><p class="eyebrow">${c.getStartedEyebrow}</p><h2 id="start-title">${c.getStartedTitle}</h2></div><div class="start-intro"><p class="section-intro">${c.getStartedIntro}</p><p class="release-badges"><a href="${repo}/releases/tag/${escape(release.tag)}"><span class="status-dot" aria-hidden="true"></span>${c.releaseLabel} <span>${escape(release.version)}</span></a><span>${c.platform}</span></p></div></div>
    <div class="agent-grid">${[['codex', 'Codex', c.codexText, '01'], ['claude', 'Claude Code', c.claudeText, '02']].map(([key, name, text, number]) => `<article class="agent-card"><div class="agent-top"><span class="agent-symbol" aria-hidden="true">${key === 'codex' ? '⌘' : '✳'}</span><span class="item-number">${number}</span></div><h3>${name}</h3><p>${text}</p><div class="agent-links"><a class="button button-outline" href="${escape(release.downloads[key])}" aria-label="${c.download} — ${name}">${c.download}${arrow}</a><a class="text-link" href="${docs('installation')}">${c.install}${arrowUp}</a></div></article>`).join('')}</div>
    <aside class="setup-note"><div><h3>${c.setupTitle}</h3><p>${c.setupText}</p></div><a class="text-link" href="${docs('installation')}">${c.setupLink}${arrow}</a></aside>
    <p class="alpha-note">${c.alphaNote} <a href="${docs('implementation_status')}">${c.statusLink}${arrowUp}</a></p>
  </section>
  <section id="community" class="community-section" aria-labelledby="community-title"><div class="shell community-inner"><div class="community-orbit" aria-hidden="true"><span></span><span></span><span></span><i></i></div><div class="community-copy"><p class="eyebrow">${c.communityEyebrow}</p><h2 id="community-title">${c.communityTitle}</h2><p>${c.communityText}</p><div class="community-actions"><a class="button button-light" href="${rootDoc('CONTRIBUTING')}">${c.contribute}${arrow}</a><a class="text-link" href="${repo}/discussions">${c.discussion}${arrowUp}</a></div></div></div></section>
</main>
<footer class="site-footer shell"><div class="footer-top"><a class="brand" href="${local(locale)}">${brandSymbol}<span>MathCoffee<span class="brand-period">.</span></span></a><p>${c.footerTagline}</p><a class="back-top" href="#top" aria-label="${c.top}">↑</a></div><div class="footer-bottom"><p>${c.licenseNote}</p><nav aria-label="${locale === 'zh' ? '项目链接' : 'Project links'}"><a href="${docMain('plugin_roadmap')}">${c.roadmap}</a><a href="${repo}/issues">${c.issues}</a><a href="${repo}/blob/main/LICENSE">${c.license}</a><a href="${rootDoc('THIRD_PARTY_NOTICES')}">${c.thirdParty}</a></nav></div></footer>
</body>
</html>`;
}
