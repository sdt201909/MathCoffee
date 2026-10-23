const preferences = window.MathCoffeePreferences;
const theme = document.querySelector('#theme-select');
if (theme && preferences) {
  theme.value = preferences.theme;
  theme.addEventListener('change', () => preferences.setTheme(theme.value));
}
for (const link of document.querySelectorAll('[data-language-link]')) {
  link.addEventListener('click', () => {
    preferences?.setLanguage(link.dataset.languageLink);
    if (location.hash && !link.hash) link.hash = location.hash;
  });
}

const angle = document.querySelector('#angle');
const play = document.querySelector('#play-toggle');
const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
const setAttributes = (id, values) => {
  const element = document.getElementById(id);
  if (element) for (const [key, value] of Object.entries(values)) element.setAttribute(key, String(value));
};

if (angle && play) {
  let degrees = Number(angle.value);
  let running = false;
  let frame;
  let lastTime;
  const point = (value) => {
    const radians = value * Math.PI / 180;
    return { x: 150 + 96 * Math.cos(radians), y: 150 - 96 * Math.sin(radians), sine: Math.sin(radians) };
  };
  const draw = () => {
    const state = point(degrees);
    const waveX = 350 + degrees;
    setAttributes('circle-point', { cx: state.x, cy: state.y });
    setAttributes('radius', { x2: state.x, y2: state.y });
    setAttributes('projection-line', { x1: state.x, y1: state.y, x2: waveX, y2: state.y });
    setAttributes('wave-point', { cx: waveX, cy: state.y });
    const samples = Array.from({ length: Math.ceil(degrees / 2) + 1 }, (_, i) => Math.min(degrees, i * 2));
    setAttributes('wave-progress', { points: samples.map((value) => `${350 + value},${point(value).y}`).join(' ') });
    const radius = 27;
    const end = { x: 150 + radius * Math.cos(degrees * Math.PI / 180), y: 150 - radius * Math.sin(degrees * Math.PI / 180) };
    const arc = degrees >= 359.99
      ? `M177,150 A27,27 0 1 0 123,150 A27,27 0 1 0 177,150`
      : `M177,150 A27,27 0 ${degrees > 180 ? 1 : 0} 0 ${end.x},${end.y}`;
    setAttributes('angle-arc', { d: arc });
    document.querySelector('#angle-value').textContent = `${Math.round(degrees)}°`;
    const sine = Math.abs(state.sine) < 0.0005 ? 0 : state.sine;
    document.querySelector('#sine-value').textContent = sine.toFixed(3);
    angle.value = String(degrees);
    angle.setAttribute('aria-valuetext', `${Math.round(degrees)}°`);
  };
  const stop = () => {
    running = false;
    cancelAnimationFrame(frame);
    lastTime = undefined;
    play.setAttribute('aria-pressed', 'false');
    play.textContent = play.dataset.playLabel;
  };
  const animate = (time) => {
    if (!running) return;
    if (lastTime !== undefined) degrees = (degrees + Math.min(time - lastTime, 100) * 0.025) % 360;
    lastTime = time;
    draw();
    frame = requestAnimationFrame(animate);
  };
  angle.addEventListener('input', () => { stop(); degrees = Number(angle.value); draw(); });
  play.addEventListener('click', () => {
    if (running) { stop(); return; }
    running = true;
    play.setAttribute('aria-pressed', 'true');
    play.textContent = play.dataset.pauseLabel;
    frame = requestAnimationFrame(animate);
  });
  reducedMotion.addEventListener('change', (event) => { if (event.matches) stop(); });
  document.addEventListener('visibilitychange', () => { if (document.hidden) stop(); });
  draw();
}
