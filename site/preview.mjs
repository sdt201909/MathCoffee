import http from 'node:http';
import { readFile, stat } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../out/site');
const portIndex = process.argv.indexOf('--port');
const port = Number(portIndex >= 0 ? process.argv[portIndex + 1] : 4173);
const mime = { '.html': 'text/html; charset=utf-8', '.css': 'text/css; charset=utf-8', '.js': 'text/javascript; charset=utf-8', '.xml': 'application/xml; charset=utf-8', '.txt': 'text/plain; charset=utf-8' };
const server = http.createServer(async (request, response) => {
  try {
    const url = new URL(request.url, 'http://localhost');
    const pathname = decodeURIComponent(url.pathname);
    if (pathname === '/') { response.writeHead(302, { Location: '/MathCoffee/' }); response.end(); return; }
    if (pathname === '/MathCoffee') { response.writeHead(301, { Location: '/MathCoffee/' }); response.end(); return; }
    if (!pathname.startsWith('/MathCoffee/')) { response.writeHead(404); response.end('Not found'); return; }
    let filename = path.resolve(root, pathname.slice('/MathCoffee/'.length));
    if (filename !== root && !filename.startsWith(root + path.sep)) { response.writeHead(403); response.end(); return; }
    let code = 200;
    try {
      if ((await stat(filename)).isDirectory()) {
        if (!pathname.endsWith('/')) { response.writeHead(301, { Location: `${url.pathname}/${url.search}` }); response.end(); return; }
        filename = path.join(filename, 'index.html');
      }
      await stat(filename);
    } catch { filename = path.join(root, '404.html'); code = 404; }
    const bytes = await readFile(filename);
    response.writeHead(code, { 'Content-Type': mime[path.extname(filename)] || 'application/octet-stream', 'Cache-Control': 'no-store' });
    response.end(bytes);
  } catch { response.writeHead(400); response.end('Bad request'); }
});
server.listen(port, '127.0.0.1', () => console.log(`MathCoffee preview: http://127.0.0.1:${port}/MathCoffee/`));
for (const signal of ['SIGINT', 'SIGTERM']) process.on(signal, () => server.close(() => process.exit(0)));
