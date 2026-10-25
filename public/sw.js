importScripts('https://www.gstatic.com/firebasejs/10.9.0/firebase-app-compat.js');
importScripts('https://www.gstatic.com/firebasejs/10.9.0/firebase-messaging-compat.js');

firebase.initializeApp({
  apiKey: "AIzaSyD6eFyVEbQueT_MudaEO0B_4RK_pm091rQ",
  authDomain: "dailynews-c9a32.firebaseapp.com",
  projectId: "dailynews-c9a32",
  storageBucket: "dailynews-c9a32.firebasestorage.app",
  messagingSenderId: "903970367164",
  appId: "1:903970367164:web:280515f9c320c9d37312b9"
});

const messaging = firebase.messaging();

// Gestore messaggi in background:
// Se il messaggio contiene già l'oggetto "notification", il browser e iOS APNs
// mostrano la notifica automaticamente. Chiamare showNotification() qui creerebbe
// una seconda notifica duplicata identica sullo smartphone.
messaging.onBackgroundMessage(function(payload) {
  console.log('Received background message: ', payload);
  if (!payload.notification && payload.data) {
    const notificationTitle = payload.data.title || 'Il tuo Daily News';
    const notificationOptions = {
      body: payload.data.body || 'La rassegna stampa è pronta! Tocca qui per scoprire le notizie fondamentali di oggi.',
      icon: '/icon.jpg',
      data: { url: payload.data.url || 'https://djiglio.github.io/daily_news/' }
    };
    self.registration.showNotification(notificationTitle, notificationOptions);
  }
});

self.addEventListener('notificationclick', function(event) {
  event.notification.close();
  const targetUrl = (event.notification.data && event.notification.data.url) ? event.notification.data.url : 'https://djiglio.github.io/daily_news/';
  event.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then(windowClients => {
      for (let client of windowClients) {
        if (client.url.includes('daily_news') && 'focus' in client) {
          return client.focus();
        }
      }
      if (clients.openWindow) {
        return clients.openWindow(targetUrl);
      }
    })
  );
});

const CACHE_NAME = 'dailynews-v2';
const ASSETS_TO_CACHE = [
  '/',
  '/index.html',
  '/js/app.js',
  '/manifest.json',
  '/icon.jpg'
];

self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => {
      return cache.addAll(ASSETS_TO_CACHE);
    })
  );
});

self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(cacheNames => {
      return Promise.all(
        cacheNames
          .filter(name => name !== CACHE_NAME)
          .map(name => caches.delete(name))
      );
    })
  );
});

self.addEventListener('fetch', event => {
  // Always fetch news_today.json from network first
  if (event.request.url.includes('news_today.json')) {
    event.respondWith(
      fetch(event.request)
        .then(response => {
          const responseClone = response.clone();
          caches.open(CACHE_NAME).then(cache => {
            cache.put(event.request, responseClone);
          });
          return response;
        })
        .catch(() => caches.match(event.request))
    );
    return;
  }

  // Network first, falling back to cache for everything else
  event.respondWith(
    fetch(event.request)
      .then(response => {
        const responseClone = response.clone();
        caches.open(CACHE_NAME).then(cache => {
          cache.put(event.request, responseClone);
        });
        return response;
      })
      .catch(() => caches.match(event.request))
  );
});
