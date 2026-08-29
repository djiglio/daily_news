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

messaging.onBackgroundMessage(function(payload) {
  console.log('Received background message ', payload);
  const notificationTitle = payload.notification.title;
  const notificationOptions = {
    body: payload.notification.body,
    icon: '/icon.jpg',
    data: { url: 'https://djiglio.github.io/daily_news/' }
  };

  self.registration.showNotification(notificationTitle, notificationOptions);
});

self.addEventListener('notificationclick', function(event) {
  event.notification.close();
  event.waitUntil(clients.openWindow(event.notification.data.url));
});
