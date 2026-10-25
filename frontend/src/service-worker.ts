/// <reference types="@sveltejs/kit" />
/// <reference no-default-lib="true"/>
/// <reference lib="esnext" />
/// <reference lib="webworker" />
// Precache the app shell; cache-first for thumbnails; never cache video proxy, SSE or other API calls.
import { build, files, version } from '$service-worker';

const sw = self as unknown as ServiceWorkerGlobalScope;
const SHELL = `bt-shell-${version}`;
const THUMBS = 'bt-thumbs-v1';
const MAX_THUMBS = 600;
const ASSETS = [...build, ...files];

sw.addEventListener('install', (event) => {
	event.waitUntil(
		(async () => {
			const cache = await caches.open(SHELL);
			await cache.addAll(ASSETS);
			// SPA fallback page (served by FastAPI for any non-API path).
			await cache.add(new Request('/', { cache: 'reload' })).catch(() => undefined);
			await sw.skipWaiting();
		})()
	);
});

sw.addEventListener('activate', (event) => {
	event.waitUntil(
		(async () => {
			for (const key of await caches.keys()) if (key !== SHELL && key !== THUMBS) await caches.delete(key);
			await sw.clients.claim();
		})()
	);
});

async function trimThumbs() {
	const cache = await caches.open(THUMBS);
	const keys = await cache.keys();
	for (let i = 0; i < keys.length - MAX_THUMBS; i++) await cache.delete(keys[i]);
}

sw.addEventListener('fetch', (event) => {
	const req = event.request;
	if (req.method !== 'GET') return;
	const url = new URL(req.url);
	if (url.origin !== sw.location.origin) return;

	// Thumbnails: cache-first.
	if (url.pathname.startsWith('/api/thumb/')) {
		event.respondWith(
			(async () => {
				const cache = await caches.open(THUMBS);
				const hit = await cache.match(req);
				if (hit) return hit;
				const res = await fetch(req);
				if (res.ok) {
					await cache.put(req, res.clone());
					if (Math.random() < 0.05) trimThumbs();
				}
				return res;
			})()
		);
		return;
	}

	// Everything else under /api (proxy, agent stream, data): network-only, untouched.
	if (url.pathname.startsWith('/api/')) return;

	// Build assets + static files: cache-first.
	if (ASSETS.includes(url.pathname)) {
		event.respondWith(caches.match(req).then((hit) => hit ?? fetch(req)));
		return;
	}

	// Navigations: network-first, fall back to the cached shell when offline.
	if (req.mode === 'navigate') {
		event.respondWith(
			(async () => {
				try {
					return await fetch(req);
				} catch {
					return (await caches.match('/')) ?? Response.error();
				}
			})()
		);
	}
});
