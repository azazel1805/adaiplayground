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
                // Use addAll - it fetches and caches in one step.
                // It rejects if any of the fetches fail.
                return cache.addAll(urlsToCache);
            })
            .then(() => {
                console.log('Service Worker: App Shell Caching complete.');
                // Force the waiting service worker to become the active service worker.
                return self.skipWaiting();
            })
            .catch(error => {
                // Log the error but installation might still partially succeed
                // depending on which asset failed.
                console.error('Service Worker: Caching failed during install', error);
                // Optionally, prevent activation if core assets fail? For now, just log.
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
             console.log('Service Worker: Activation complete, claiming clients.');
             // Ensure the activated worker takes control of the page immediately.
             return self.clients.claim();
        })
    );
});

// Fetch event: Serve cached assets, fallback to network, provide offline page
self.addEventListener('fetch', event => {
    const requestUrl = new URL(event.request.url);

    // --- Strategy: Network First for API calls ---
    // Always try the network for API calls. If it fails, return a simple error response.
    if (requestUrl.pathname.startsWith('/api/')) {
        event.respondWith(
            fetch(event.request)
            .catch(error => {
                console.error('Service Worker: API fetch failed:', error);
                // Return a synthetic error response (JSON format matching backend errors)
                return new Response(JSON.stringify({ error: 'Network error: Could not reach API.' }), {
                    status: 503, // Service Unavailable
                    headers: { 'Content-Type': 'application/json' }
                });
            })
        );
        return; // Don't process further for API calls
    }

    // --- Strategy: Cache First, Fallback to Network (then Offline Page for Nav) for GET requests ---
    if (event.request.method === 'GET') {

        // --- Skip non-web schemes (like chrome-extension://) ---
        if (!['http:', 'https:'].includes(requestUrl.protocol)) {
            // console.log(`SW: Ignoring non-http(s) request: ${requestUrl.protocol}`);
            // Let the browser handle it normally by not calling respondWith
            return;
        }

        // --- Handle web requests (HTML pages, CSS, JS, images etc.) ---
        event.respondWith(
            caches.match(event.request)
                .then(cachedResponse => {
                    // 1. Cache Hit: Return cached response
                    if (cachedResponse) {
                        // console.log('SW: Serving from cache:', event.request.url);
                        return cachedResponse;
                    }

                    // 2. Cache Miss: Go to Network
                    // console.log('SW: Fetching from network:', event.request.url);
                    return fetch(event.request).then(
                        networkResponse => {
                            // Check if we received a valid response to cache
                            // Don't cache errors (4xx, 5xx) or redirects (3xx) usually
                            if (!networkResponse || networkResponse.status !== 200 || networkResponse.type !== 'basic') {
                                // Return the non-cacheable response as is
                                return networkResponse;
                            }

                            // Clone the response because it needs to be used by browser and cache
                            const responseToCache = networkResponse.clone();

                            // Cache the newly fetched resource
                            caches.open(CACHE_NAME)
                                .then(cache => {
                                    // console.log('SW: Caching new resource:', event.request.url);
                                    cache.put(event.request, responseToCache);
                                });

                            // Return the original network response to the browser
                            return networkResponse;
                        }
                    ).catch(error => {
                         // 3. Network Failed: Serve Offline Fallback (for navigation requests only)
                        console.log('SW: Network fetch failed for:', event.request.url, error);

                        // Only serve the offline page for navigating to HTML pages
                        if (event.request.mode === 'navigate') {
                            console.log('SW: Serving offline fallback page.');
                            return caches.match('/offline.html');
                        }

                        // For other failed assets (CSS, JS, images), let the browser handle the error
                        // Returning undefined here will result in the browser's default behavior
                        // (e.g., broken image icon, style not applied).
                        return undefined;
                    });
                })
        ); // end event.respondWith
    } // end if GET request

    // else: For non-GET requests (POST, PUT, etc.) that weren't API calls,
    // just let the browser handle them by default (don't call respondWith).
    // console.log(`SW: Ignoring non-GET request: ${event.request.method} ${event.request.url}`);

}); // end fetch event listener
