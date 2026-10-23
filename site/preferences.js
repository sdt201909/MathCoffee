/* Applied before styles load so an explicit theme has the correct first paint. */
(() => {
  const root = document.documentElement;
  root.classList.add('js');
  const read = (key) => {
    try { return localStorage.getItem(`mathcoffee.${key}`); } catch { return null; }
  };
  const write = (key, value) => {
    try { localStorage.setItem(`mathcoffee.${key}`, value); } catch { /* Optional preference storage. */ }
  };
  const system = window.matchMedia('(prefers-color-scheme: dark)');
  let preference = read('theme');
  if (!['system', 'light', 'dark'].includes(preference)) preference = 'system';
  const applyTheme = () => {
    root.dataset.theme = preference === 'system' ? (system.matches ? 'dark' : 'light') : preference;
    root.style.colorScheme = root.dataset.theme;
  };
  applyTheme();
  system.addEventListener('change', applyTheme);
  window.MathCoffeePreferences = Object.freeze({
    get theme() { return preference; },
    setTheme(value) {
      if (!['system', 'light', 'dark'].includes(value)) return;
      preference = value;
      write('theme', value);
      applyTheme();
    },
    setLanguage(value) { if (['en', 'zh'].includes(value)) write('language', value); }
  });

  if (root.dataset.autoLanguage === 'true') {
    let language = read('language');
    if (!['en', 'zh'].includes(language)) {
      const languages = navigator.languages?.length ? navigator.languages : [navigator.language];
      language = languages.map((value) => String(value).toLowerCase().split('-')[0])
        .find((value) => ['en', 'zh'].includes(value)) || 'en';
    }
    const base = new URL('../', document.currentScript.src).pathname;
    const target = `${base}${language}/${location.search}${location.hash}`;
    location.replace(target);
  }
})();
