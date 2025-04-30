const CACHE_NAME = 'adai-playground-cache-v1'; // Change version to force update
const urlsToCache = [
    '/', // Cache the root page
    '/offline.html', // Cache the offline fallback page
    '/static/css/style.css',
    '/static/js/script.js',
    '/static/js/pwa.js',
    '/manifest.json',
    '/static/images/favicon.ico',
    '/static/images/icons/icon-192x192.png',
    '/static/images/icons/icon-512x512.png'
    // Add other core static assets if needed (e.g., fonts, logo image)
];

// Install event: Cache core assets
self.addEventListener('install', event => {
    console.log('Service Worker: Installing...');
    event.waitUntil(
        caches.open(CACHE_NAME)
            .then(cache => {
                console.log('Service Worker: Caching app shell');
                return cache.addAll(urlsToCache);
            })
            .then(() => {
                console.log('Service Worker: Installation complete');
                return self.skipWaiting(); // Activate worker immediately
            })
            .catch(error => {
                console.error('Service Worker: Caching failed', error);
            })
    );
});

// Activate event: Clean up old caches
self.addEventListener('activate', event => {
    console.log('Service Worker: Activating...');
    event.waitUntil(
        caches.keys().then(cacheNames => {
            return Promise.all(
                cacheNames.map(cacheName => {
                    if (cacheName !== CACHE_NAME) {
                        console.log('Service Worker: Clearing old cache:', cacheName);
                        return caches.delete(cacheName);
                    }
                })
            );
        }).then(() => {
             console.log('Service Worker: Activation complete');
             return self.clients.claim(); // Take control of existing clients
        })
    );
});

// Fetch event: Serve cached assets, fallback to network, provide offline page
self.addEventListener('fetch', event => {
    // We only want to intercept navigation requests and potentially API calls
    // Let's focus on serving cached assets and an offline page for navigation

    const requestUrl = new URL(event.request.url);

    // For API calls (/api/generate), always go to network. AI needs to be live.
    if (requestUrl.pathname.startsWith('/api/')) {
        event.respondWith(fetch(event.request));
        return;
    }

    // For other GET requests (pages, static assets)
    if (event.request.method === 'GET') {
         event.respondWith(
            caches.match(event.request)
                .then(cachedResponse => {
                    // Cache hit - return response
                    if (cachedResponse) {
                        // console.log('Service Worker: Serving from cache:', event.request.url);
                        return cachedResponse;
                    }

                    // Not in cache - fetch from network
                    // console.log('Service Worker: Fetching from network:', event.request.url);
                    return fetch(event.request).then(
                        response => {
                            // Check if we received a valid response
                            if (!response || response.status !== 200 || response.type !== 'basic') {
                                // Don't cache error responses or non-basic types (like opaque responses from CDNs)
                                return response;
                            }

                            // IMPORTANT: Clone the response. A response is a stream
                            // and because we want the browser to consume the response
                            // as well as the cache consuming the response, we need
                            // to clone it so we have two streams.
                            const responseToCache = response.clone();

                            caches.open(CACHE_NAME)
                                .then(cache => {
                                     // console.log('Service Worker: Caching new resource:', event.request.url);
                                    cache.put(event.request, responseToCache);
                                });

                            return response;
                        }
                    ).catch(error => {
                         // Network request failed, try serving offline page for navigation requests
                        console.log('Service Worker: Network fetch failed for:', event.request.url, error);
                        // Only serve offline page for navigation requests (HTML pages)
                        if (event.request.mode === 'navigate') {
                            console.log('Service Worker: Serving offline page.');
                            return caches.match('/offline.html');
                        }
                        // For other asset types (CSS, JS), just let the error propagate
                        // so the browser shows its default offline behavior for those assets.
                    });
                })
        );
    }
});