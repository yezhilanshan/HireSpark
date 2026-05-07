const CACHE_NAME = 'panelmind-v1';
const OFFLINE_URL = '/offline';

const STATIC_ASSETS = [
  '/',
  '/offline',
  '/icon.svg',
  '/manifest.json',
];

const CACHE_STRATEGIES = {
  // Static assets: cache first, fallback to network
  static: (request) =>
    caches.match(request).then((cached) => cached || fetch(request).then((response) => {
      if (response.ok) {
        const clone = response.clone();
        caches.open(CACHE_NAME).then((cache) => cache.put(request, clone));
      }
      return response;
    })),

  // API / dynamic: network first, fallback to cache
  networkFirst: (request) =>
    fetch(request).then((response) => {
      if (response.ok) {
        const clone = response.clone();
        caches.open(CACHE_NAME).then((cache) => cache.put(request, clone));
      }
      return response;
    }).catch(() => caches.match(request)),
};

// Skip waiting so the new SW activates immediately
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(STATIC_ASSETS))
  );
  self.skipWaiting();
});

// Clean old caches
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key)))
    )
  );
  self.clients.claim();
});

self.addEventListener('fetch', (event) => {
  const { request } = event;
  const url = new URL(request.url);

  // Only handle GET requests
  if (request.method !== 'GET') return;

  // Skip non-http requests
  if (!url.protocol.startsWith('http')) return;

  // Skip chrome-extension and other non-standard protocols
  if (url.protocol === 'chrome-extension:') return;

  // Static assets: JS, CSS, fonts, images, models
  if (
    /\.(js|css|png|jpg|jpeg|gif|svg|ico|woff|woff2|ttf|eot|webp|avif|task|wasm)$/.test(url.pathname) ||
    url.pathname.startsWith('/_next/') ||
    url.pathname.startsWith('/facephys/')
  ) {
    event.respondWith(CACHE_STRATEGIES.static(request));
    return;
  }

  // API calls: network first
  if (
    url.pathname.startsWith('/api/') ||
    url.pathname.includes('socket.io')
  ) {
    event.respondWith(CACHE_STRATEGIES.networkFirst(request));
    return;
  }

  // Navigation requests: network first, fallback to offline page
  if (request.mode === 'navigate') {
    event.respondWith(
      fetch(request).catch(() => caches.match(OFFLINE_URL))
    );
    return;
  }

  // Default: network first
  event.respondWith(CACHE_STRATEGIES.networkFirst(request));
});
