import re
path = 'public/index.html'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

main_old = '<main class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 min-h-screen">'
main_new = '''<main class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 min-h-screen flex flex-col lg:flex-row gap-8">
        
        <!-- Sidebar Navigation (Desktop) -->
        <aside class="hidden lg:block w-48 flex-shrink-0">
            <div class="sticky top-24">
                <h3 class="text-xs font-bold text-stone-900 dark:text-stone-400 uppercase tracking-wider mb-4">Sezioni</h3>
                <nav class="flex flex-col space-y-2" x-show="!loading && !error">
                    <template x-for="(articles, category) in data.categories" :key="category">
                        <a :href="'#' + category.replace(/\\s+/g, '-').toLowerCase()" 
                           class="text-sm text-stone-600 dark:text-stone-300 hover:text-indigo-600 dark:hover:text-indigo-400 font-medium transition"
                           x-text="category"></a>
                    </template>
                </nav>
            </div>
        </aside>

        <!-- Main Content -->
        <div class="flex-grow min-w-0">'''

content = content.replace(main_old, main_new)

content = content.replace('</main>', '</div>\n    </main>')

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)
