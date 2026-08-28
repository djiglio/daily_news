import re
path = 'public/index.html'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

target = '<!-- Categories and News -->'
mobile_nav = '''<!-- Mobile Navigation -->
        <div class="lg:hidden sticky top-16 z-30 bg-stone-100/90 dark:bg-neutral-900/90 backdrop-blur-md border-b border-stone-200 dark:border-neutral-700 -mx-4 px-4 sm:-mx-6 sm:px-6 py-3 mb-6 overflow-x-auto whitespace-nowrap hide-scrollbar">
            <nav class="flex space-x-6" x-show="!loading && !error">
                <template x-for="(articles, category) in data.categories" :key="category">
                    <a :href="'#' + category.replace(/\\s+/g, '-').toLowerCase()" 
                       class="inline-block text-sm font-medium text-stone-600 dark:text-stone-300 hover:text-indigo-600"
                       x-text="category"></a>
                </template>
            </nav>
        </div>
        
        '''

if '<!-- Mobile Navigation -->' not in content:
    content = content.replace(target, mobile_nav + target)

# also add hide-scrollbar style
style_target = '</style>'
style_add = '''
        .hide-scrollbar::-webkit-scrollbar { display: none; }
        .hide-scrollbar { -ms-overflow-style: none; scrollbar-width: none; }
'''
if '.hide-scrollbar' not in content:
    content = content.replace(style_target, style_add + style_target)

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)
