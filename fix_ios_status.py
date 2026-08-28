path = 'public/index.html'
with open(path, 'r', encoding='utf-8') as f:
    html = f.read()

target_header = 'header class="sticky top-0 z-40 bg-stone-50/80 dark:bg-neutral-800/80 backdrop-blur-md border-b border-stone-200 dark:border-neutral-700 shadow-sm"'
new_header = 'header class="sticky top-0 z-40 bg-stone-50/80 dark:bg-neutral-800/80 backdrop-blur-md border-b border-stone-200 dark:border-neutral-700 shadow-sm pt-[env(safe-area-inset-top)]"'

if target_header in html:
    html = html.replace(target_header, new_header)

head_target = '<meta id="theme-color-meta" name="theme-color" content="#fafaf9">'
apple_meta = '<meta name="apple-mobile-web-app-capable" content="yes">\n    <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">\n    '

if 'apple-mobile-web-app-status-bar-style' not in html:
    html = html.replace(head_target, apple_meta + head_target)

with open(path, 'w', encoding='utf-8') as f:
    f.write(html)
