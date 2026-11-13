import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { test } from 'node:test';

const configPath = fileURLToPath(new URL('../../vercel.json', import.meta.url));
const config = JSON.parse(await readFile(configPath, 'utf8'));

test('deep links for every React route resolve to the SPA entry point', () => {
  const paths = ['/login', '/chat', '/documents', '/admin', '/admin/access'];

  for (const path of paths) {
    const route = config.services.frontend.rewrites.find((item) => item.source === path);
    assert.equal(route?.destination, '/index.html', `${path} should load index.html on direct visits`);
  }
});

test('HTML, manifest, API, and service worker endpoints require revalidation and are not stored', () => {
  const paths = ['/', '/index.html', '/login', '/chat', '/documents', '/admin', '/admin/access', '/api/:path*', '/sw.js', '/registerSW.js', '/workbox-:filename.js', '/manifest.webmanifest'];

  for (const path of paths) {
    const rule = config.headers.find((item) => item.source === path);
    const cacheControl = rule?.headers.find((header) => header.key.toLowerCase() === 'cache-control')?.value ?? '';
    assert.match(cacheControl, /no-store/iu, `${path} must not be stored`);
    assert.match(cacheControl, /must-revalidate/iu, `${path} must be revalidated`);
  }
});
