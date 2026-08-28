function newsApp() {
    return {
        data: { categories: {} },
        lastUpdate: '',
        loading: true,
        error: null,
        activeArticle: null,
        activeCategory: null,
        activeSection: '',
        isDark: false,

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

        openArticle(article, category) {
            this.activeArticle = article;
            this.activeCategory = category;
        },

        closeArticle() {
            this.activeArticle = null;
            this.activeCategory = null;
        }
    }
}
