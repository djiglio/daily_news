const APP_URL = 'https://daily-news-8wu.pages.dev/';

self.addEventListener('install', event => {
  self.skipWaiting();
});

self.addEventListener('activate', event => {
  event.waitUntil(self.clients.claim());
});

self.addEventListener('push', function(event) {
  let payload = {};
  if (event.data) {
    try {
      payload = event.data.json();
    } catch (e) {
      payload = {};
    }
  }

  const notification = payload.notification || {};
  const data = payload.data || {};
  const fcmOptions = payload.fcmOptions || payload.fcm_options || {};

  const title = notification.title || data.title || 'Il tuo Daily News';
  const body = notification.body || data.body || 'La rassegna stampa è pronta! Tocca qui per scoprire le notizie fondamentali di oggi.';
  const targetUrl = fcmOptions.link || data.url || APP_URL;

  const options = {
    body: body,
    icon: '/icon.jpg',
    badge: '/icon.jpg',
    tag: 'daily-news-push',
    renotify: false,
    data: { url: targetUrl }
  };

  event.waitUntil(
    self.registration.showNotification(title, options)
  );
});

self.addEventListener('notificationclick', function(event) {
  event.notification.close();
  const targetUrl = (event.notification.data && event.notification.data.url && !event.notification.data.url.includes('djiglio.github.io'))
    ? event.notification.data.url
    : (self.location.origin + '/');

  event.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then(windowClients => {
      for (let client of windowClients) {
        if (client.url.startsWith(self.location.origin) && 'focus' in client) {
          return client.focus();
        }
      }
      if (clients.openWindow) {
        return clients.openWindow(targetUrl);
      }
    })
  );
});
