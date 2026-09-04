function newsApp() {
    return {
        data: { categories: {} },
        lastUpdate: '',
        loading: true,
        error: null,
        activeArticle: null,
        activeCategory: null,
        activeSection: '',
        settingsOpen: false,
        fontSize: 16,
        isDark: false,
        savedArticles: [],
        currentArticleIndex: -1,
        isSpeaking: false,
        
        searchQuery: '',
        isBriefingPlaying: false,

        get searchResults() {
            if (!this.searchQuery) return [];
            const q = this.searchQuery.toLowerCase();
            const results = [];
            // We use a Set to avoid duplicates if Top News has the same article as another category
            const seenTitles = new Set();
            for (const cat in this.data.categories) {
                this.data.categories[cat].forEach(article => {
                    if ((article.title.toLowerCase().includes(q) || article.summary.toLowerCase().includes(q)) && !seenTitles.has(article.title)) {
                        results.push(article);
                        seenTitles.add(article.title);
                    }
                });
            }
            return results;
        },

        toggleBriefing() {
            if (!this.data.briefing_text) {
                alert("Il briefing audio non è ancora pronto.");
                return;
            }
            if (this.isBriefingPlaying) {
                window.speechSynthesis.cancel();
                this.isBriefingPlaying = false;
                return;
            }
            // Stop any other article reading
            if (this.isSpeaking) this.toggleSpeech('');
            
            const cleanText = this.data.briefing_text.replace(/\*\*/g, '');
            const utterance = new SpeechSynthesisUtterance(cleanText);
            utterance.lang = 'it-IT';
            utterance.rate = 1.0;
            utterance.onend = () => { this.isBriefingPlaying = false; };
            window.speechSynthesis.speak(utterance);
            this.isBriefingPlaying = true;
        },

        initApp() {
            // Check theme preference
            if (localStorage.getItem('theme') === 'dark' || (!('theme' in localStorage) && window.matchMedia('(prefers-color-scheme: dark)').matches)) {
                this.isDark = true;
                document.documentElement.classList.add('dark');
            } else {
                this.isDark = false;
                document.documentElement.classList.remove('dark');
            }
            this.updateThemeColor();

            
            let savedSize = localStorage.getItem('fontSize');
            if (savedSize) {
                this.fontSize = parseInt(savedSize);
                document.documentElement.style.fontSize = this.fontSize + 'px';
            }
            
            let savedData = localStorage.getItem('savedArticles');
            if (savedData) {
                try {
                    this.savedArticles = JSON.parse(savedData);
                } catch(e) {
                    this.savedArticles = [];
                }
            }

            this.fetchNews();
            // Scroll spy for navigation highlighting
            window.addEventListener('scroll', () => {
                const sections = document.querySelectorAll('section[id]');
                let current = '';
                sections.forEach(section => {
                    const sectionTop = section.offsetTop;
                    // Adjust 200px for sticky header
                    if (window.scrollY >= sectionTop - 200) {
                        current = section.getAttribute('id');
                    }
                });
                if (current) {
                    this.activeSection = current;
                }
            });

            this.updateThemeColor();
        },

        
        updateThemeColor() {
            const meta = document.getElementById('theme-color-meta');
            if (meta) {
                meta.setAttribute('content', this.isDark ? '#262626' : '#fafaf9');
            }
        },
        
        enablePushNotifications() {
            if (!('Notification' in window)) {
                alert("Questo browser non supporta le notifiche push native.");
                return;
            }
            Notification.requestPermission().then((permission) => {
                if (permission === 'granted') {
                    if (!firebase.apps.length) {
                        firebase.initializeApp({
                            apiKey: "AIzaSyD6eFyVEbQueT_MudaEO0B_4RK_pm091rQ",
                            authDomain: "dailynews-c9a32.firebaseapp.com",
                            projectId: "dailynews-c9a32",
                            storageBucket: "dailynews-c9a32.firebasestorage.app",
                            messagingSenderId: "903970367164",
                            appId: "1:903970367164:web:280515f9c320c9d37312b9"
                        });
                    }
                    const messaging = firebase.messaging();
                    messaging.getToken({ vapidKey: "BARUDz5Bb6MRbnrOnn6mCWf3B8YdPf3SyInB5-oWVrOBxJacneNwFN0_FCsX7-eTeXP_vijV9tZPX8zMumztktI" }).then((currentToken) => {
                        if (currentToken) {
                            prompt("Permesso accordato! Copia questo Token esatto e incollalo nei Secrets di GitHub col nome FCM_TOKEN:", currentToken);
                        } else {
                            alert('Nessun token di registrazione disponibile.');
                        }
                    }).catch((err) => {
                        console.error('Errore durante il recupero del token.', err);
                        alert("Errore FCM: " + err);
                    });
                } else {
                    alert("Hai negato il permesso alle notifiche.");
                }
            });
        },

        changeFontSize(size) {
            this.fontSize = size;
            document.documentElement.style.fontSize = size + 'px';
            localStorage.setItem('fontSize', size);
        },
        
        formatText(text) {
            if (!text) return '';
            // Escape HTML
            let safeText = text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
            // Bold
            safeText = safeText.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
            // Paragraphs
            const paragraphs = safeText.split(/\n\s*\n/).filter(p => p.trim() !== '');
            return paragraphs.map(p => `<p class="mb-5 leading-relaxed text-lg">${p}</p>`).join('');
        },
        toggleTheme() {
            this.isDark = !this.isDark;
            if (this.isDark) {
                document.documentElement.classList.add('dark');
                localStorage.setItem('theme', 'dark');
            } else {
                document.documentElement.classList.remove('dark');
                localStorage.setItem('theme', 'light');
            }
            this.updateThemeColor();
        },

        async fetchNews() {
            try {
                const response = await fetch('/data/news_today.json?v=' + new Date().getTime());
                if (!response.ok) {
                    throw new Error('Impossibile caricare le notizie.');
                }
                const result = await response.json();
                this.data = result;
                
                // Format date
                if (result.timestamp) {
                    const d = new Date(result.timestamp);
                    this.lastUpdate = d.toLocaleTimeString('it-IT', { hour: '2-digit', minute: '2-digit' }) + ' del ' + d.toLocaleDateString('it-IT');
                }
                
                this.loading = false;
            } catch (e) {
                this.error = "Errore durante il caricamento della rassegna stampa: " + e.message;
                this.loading = false;
            }
        },
        // Bookmarks Logic
        toggleSave(article) {
            if (!article) return;
            const index = this.savedArticles.findIndex(a => a.title === article.title);
            if (index > -1) {
                this.savedArticles.splice(index, 1);
            } else {
                this.savedArticles.push(article);
            }
            localStorage.setItem('savedArticles', JSON.stringify(this.savedArticles));
        },
        isSaved(article) {
            if (!article) return false;
            return this.savedArticles.some(a => a.title === article.title);
        },
        
        // TTS Logic
        toggleSpeech(text) {
            if (!text) return;
            if (this.isSpeaking) {
                window.speechSynthesis.cancel();
                this.isSpeaking = false;
                return;
            }
            const cleanText = text.replace(/\*\*/g, '');
            const utterance = new SpeechSynthesisUtterance(cleanText);
            utterance.lang = 'it-IT';
            utterance.rate = 1.0;
            utterance.onend = () => { this.isSpeaking = false; };
            window.speechSynthesis.speak(utterance);
            this.isSpeaking = true;
        },

        // Open Article (modified to track index)
        openArticle(article, category, index) {
            this.activeArticle = article;
            this.activeCategory = category;
            this.currentArticleIndex = index;
            document.body.style.overflow = 'hidden';
            if (this.isSpeaking) this.toggleSpeech(''); // Stop speech if open new
        },
        closeArticle() {
            this.activeArticle = null;
            document.body.style.overflow = '';
            if (this.isSpeaking) this.toggleSpeech(''); // Stop speech on close
        },
        
        // Navigation Logic
        get currentArticlesList() {
            if (this.activeSection === 'salvati') {
                return this.savedArticles;
            }
            return this.activeCategory ? this.data.categories[this.activeCategory] : [];
        },
        hasNextArticle() {
            if (!this.currentArticlesList) return false;
            return this.currentArticleIndex > -1 && this.currentArticleIndex < this.currentArticlesList.length - 1;
        },
        hasPrevArticle() {
            return this.currentArticleIndex > 0;
        },
        nextArticle() {
            if (this.hasNextArticle()) {
                this.openArticle(this.currentArticlesList[this.currentArticleIndex + 1], this.activeCategory, this.currentArticleIndex + 1);
                const drawerContent = document.getElementById('drawer-content');
                if (drawerContent) drawerContent.scrollTop = 0;
            }
        },
        prevArticle() {
            if (this.hasPrevArticle()) {
                this.openArticle(this.currentArticlesList[this.currentArticleIndex - 1], this.activeCategory, this.currentArticleIndex - 1);
                const drawerContent = document.getElementById('drawer-content');
                if (drawerContent) drawerContent.scrollTop = 0;
            }
        }

    }
}
