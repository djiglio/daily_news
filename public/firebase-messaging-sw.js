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
// Se il payload inviato dal server contiene già l'oggetto "notification",
// il browser e iOS APNs mostrano già la notifica in modo automatico.
// Non dobbiamo chiamare self.registration.showNotification(), altrimenti lo smartphone mostrerà 2 notifiche duplicate!
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
