import re

path = 'public/index.html'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Fonts
font_link = '<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Playfair+Display:ital,wght@0,600;0,700;0,900;1,600&display=swap" rel="stylesheet">\n    <script src="https://cdn.tailwindcss.com"></script>'
content = content.replace('<script src="https://cdn.tailwindcss.com"></script>', font_link)
content = content.replace("'Merriweather', 'serif'", "'\"Playfair Display\"', 'serif'")

# 2. Header Quick Nav
header_end = '        </div>\n    </header>'
quick_nav = '''        </div>
        <!-- Quick Nav -->
        <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 border-t border-stone-200 dark:border-neutral-700 hidden sm:block">
            <nav class="flex space-x-6 overflow-x-auto py-2 no-scrollbar" x-show="!loading && !error" x-cloak>
                <template x-for="(articles, category) in data.categories" :key="category">
                    <a :href="'#' + category.replace(/\s+/g, '-').toLowerCase()" @click.prevent="document.getElementById(category.replace(/\s+/g, '-').toLowerCase()).scrollIntoView({behavior: 'smooth'})" class="text-sm font-semibold whitespace-nowrap text-stone-600 dark:text-stone-400 hover:text-indigo-600 dark:hover:text-indigo-400 transition" x-text="category"></a>
                </template>
            </nav>
        </div>
    </header>'''
content = content.replace(header_end, quick_nav)

# 3. Section ID and scroll-mt
content = content.replace('<section>', '<section :id="category.replace(/\\s+/g, \'-\').toLowerCase()" class="scroll-mt-32">')

# 4. Asymmetrical grid
loop_start = '<template x-for="article in articles" :key="article.title">'
loop_start_new = '<template x-for="(article, index) in articles" :key="article.title">'
content = content.replace(loop_start, loop_start_new)

article_start = '<article class="bg-stone-50 dark:bg-neutral-800'
article_start_new = '<article :class="index === 0 ? \'md:col-span-2 lg:col-span-2\' : \'\'" class="bg-stone-50 dark:bg-neutral-800'
content = content.replace(article_start, article_start_new)

title_start = '<h3 class="text-lg font-bold mb-3 leading-snug font-serif text-stone-900 dark:text-white"'
title_start_new = '<h3 :class="index === 0 ? \'text-2xl md:text-3xl\' : \'text-lg\'" class="font-bold mb-3 leading-snug font-serif text-stone-900 dark:text-white"'
content = content.replace(title_start, title_start_new)

summary_start = '<p class="text-stone-600 dark:text-stone-300 text-sm flex-grow line-clamp-3"'
summary_start_new = '<p :class="index === 0 ? \'line-clamp-5 text-base\' : \'line-clamp-3 text-sm\'" class="text-stone-600 dark:text-stone-300 flex-grow"'
content = content.replace(summary_start, summary_start_new)

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)
