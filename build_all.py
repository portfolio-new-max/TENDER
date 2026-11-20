"""Open landing from PREZ.pdf + AI.pdf (sequential merge). Run: python3 build_all.py  (needs internet once, for Vimeo aspect ratios)"""
import json, os, re, time, urllib.parse, urllib.request
import pymupdf as fitz

BASE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(BASE, '..')
PREZ_THANKS = 99

# merged order: PREZ 1-98, AI 1-34, then PREZ "Спасибо"
ORDER = [('p', n) for n in range(1, PREZ_THANKS)] + [('a', n) for n in range(1, 35)] + [('p', PREZ_THANKS)]
SRC = {'p': fitz.open(os.path.join(ROOT, 'PREZ.pdf')), 'a': fitz.open(os.path.join(ROOT, 'AI.pdf'))}

# (menu title, first slide id, last slide id, [(slide id, label)])
MENU = [
    ('E-GROCERY', 'p2', 'p43', [('p3', 'Купер'), ('p11', 'Самокат'), ('p31', 'Яндекс Еда'), ('p37', 'Vprok.ru')]),
    ('FMCG', 'p44', 'p62', [('p45', 'Мираторг'), ('p50', 'Valio / Viola'), ('p54', 'Сыробогатов'), ('p58', 'Hungry Panda')]),
    ('RETAIL', 'p63', 'p68', [('p64', 'Desport')]),
    ('BANKING/FINTECH', 'p69', 'p80', [('p70', 'Home Credit Bank'), ('p77', 'РСХБ')]),
    ('E-SERVICES', 'p81', 'p98', [('p82', 'ivi'), ('p93', 'hh.ru')]),
    ('Использование ИИ', 'a1', 'a34', []),
]
GAP_BEFORE = 5  # extra space (and a hairline) before the last menu item

ids = [f'{k}{n}' for k, n in ORDER]
pos = {i: x for x, i in enumerate(ids)}

def chapter_of(sid):
    for k, (_, a, b, _) in enumerate(MENU):
        if pos[a] <= pos[sid] <= pos[b]:
            return k
    return -1

def canon(uri):
    m = re.search(r'vimeo\.com/(?:manage/videos/)?(\d+)(?:/([a-f0-9]+))?', uri)
    if m: return ('vimeo', m.group(1), m.group(2))
    m = re.search(r'(?:youtube\.com/watch\?v=|youtu\.be/)([\w-]+)', uri)
    if m: return ('youtube', m.group(1), None)
    return ('link', uri, None)

aspect_cache = {}
def vimeo_aspect(vid, h):
    key = (vid, h)
    if key in aspect_cache: return aspect_cache[key]
    url = f'https://vimeo.com/{vid}' + (f'/{h}' if h else '')
    try:
        api = 'https://vimeo.com/api/oembed.json?width=1920&url=' + urllib.parse.quote(url, safe='')
        d = json.loads(urllib.request.urlopen(urllib.request.Request(api, headers={'User-Agent': 'Mozilla/5.0'}), timeout=10).read())
        a = round(d['width'] / d['height'], 4)
    except Exception as e:
        print('  no aspect for', url, '->', e); a = None
    aspect_cache[key] = a; time.sleep(0.15)
    return a

sections, report = [], []
for src, n in ORDER:
    sid = f'{src}{n}'
    page = SRC[src][n - 1]
    dst = os.path.join(BASE, 'img', f'{sid}.jpg')
    if not os.path.exists(dst):
        page.get_pixmap(matrix=fitz.Matrix(1, 1), alpha=False).save(dst, jpg_quality=88)
    groups = {}
    for l in page.get_links():
        u = l.get('uri')
        if not u: continue
        r = fitz.Rect(l['from']); g = groups.setdefault(canon(u), {'rect': r, 'uri': u})
        g['rect'] |= r
    hot, has_video = '', ''
    for (kind, vid, h), g in sorted(groups.items(), key=lambda kv: -(kv[1]['rect'].width * kv[1]['rect'].height)):
        r = g['rect']
        style = f'left:{r.x0/1920*100:.4f}%;top:{r.y0/1080*100:.4f}%;width:{r.width/1920*100:.4f}%;height:{r.height/1080*100:.4f}%;'
        if kind == 'link':
            hot += (f'\n      <a class="hotspot hotspot-link" style="{style}" href="{g["uri"]}" target="_blank" '
                    f'rel="noopener noreferrer" aria-label="Открыть ссылку"></a>')
            continue
        if kind == 'vimeo':
            embed = f'https://player.vimeo.com/video/{vid}?' + (f'h={h}&' if h else '') + 'autoplay=1&title=0&byline=0&portrait=0'
            a = vimeo_aspect(vid, h); asp = f' data-aspect="{a}"' if a else ''
        else:
            embed, asp = f'https://www.youtube.com/embed/{vid}?autoplay=1&rel=0', ''
        hot += (f'\n      <button class="hotspot hotspot-video" style="{style}" data-embed="{embed}"{asp} '
                f'aria-label="Смотреть видео"></button>')
        has_video = ' has-video'; report.append((sid, kind, vid, h))
    sections.append(f'    <section class="slide{has_video}" id="{sid}" data-page="{sid}" data-chapter="{chapter_of(sid)}">\n'
                    f'      <img src="img/{sid}.jpg" alt="Слайд {len(sections) + 1}" loading="lazy" draggable="false">{hot}\n    </section>')

nav = []
for k, (title, first, _, items) in enumerate(MENU):
    cls = 'chapter-item chapter-gap' if k == GAP_BEFORE else 'chapter-item'
    link = f'<a href="#{first}" class="chapter-link" data-chapter-idx="{k}">{title}</a>'
    if not items:
        nav.append(f'<div class="{cls}">{link}</div>'); continue
    subs = '\n          '.join(f'<a href="#{sid}" class="chapter-sub-link">{name}</a>' for sid, name in items)
    nav.append(f'<div class="{cls}">\n      {link}\n      <div class="chapter-dropdown">\n        <div class="chapter-dropdown-inner">\n          {subs}\n        </div>\n      </div>\n    </div>')

tpl = open(os.path.join(ROOT, 'project_fin', 'index.html'), encoding='utf-8').read()
CSS = re.search(r'<style>(.*?)</style>', tpl, re.S).group(1)
JS = re.search(r'<script>(.*?)</script>', tpl, re.S).group(1)
JS = JS.replace("  function playInline(btn) {", """  var vimeoApi;
  function withVimeoApi(cb) {
    if (window.Vimeo) { cb(); return; }
    if (!vimeoApi) {
      vimeoApi = document.createElement('script');
      vimeoApi.src = 'https://player.vimeo.com/api/player.js';
      document.head.appendChild(vimeoApi);
    }
    vimeoApi.addEventListener('load', cb);
  }

  function playInline(btn) {""", 1)
assert 'withVimeoApi' in JS
JS = JS.replace("    section.appendChild(closeBtn);\n  }", """    section.appendChild(closeBtn);
    if (/player\\.vimeo\\.com/.test(iframe.src)) {
      withVimeoApi(function () {
        try { new Vimeo.Player(iframe).on('ended', function () { closeBtn.click(); }); } catch (e) {}
      });
    }
  }""", 1)
assert "on('ended'" in JS
total = len(sections)
html = f'''<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<title>Креатив и ИИ — Тутков/Будков</title>
<meta name="description" content="Портфолио агентства Тутков/Будков: кейсы по отраслям и использование ИИ.">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex, nofollow, noarchive">
<link rel="icon" href="data:,">
<style>{CSS}
  .chapternav {{ gap: 4px 20px; }}
  .chapter-sub-link {{ white-space: normal; max-width: 340px; }}
  .chapter-gap {{ margin-left: 22px; padding-left: 26px; border-left: 1px solid rgba(255,255,255,0.22); }}
  @media (max-width: 700px) {{ .chapter-gap {{ margin-left: 0; padding-left: 0; border-left: 0; }} }}
</style>
</head>
<body>

<div class="topbar"><div class="topbar-fill" id="topbarFill"></div></div>

<nav class="chapternav">
  {chr(10).join("  " + x for x in nav).lstrip()}
</nav>

<div class="scroller">
<div class="deck">
{chr(10).join(sections)}
</div>
</div>

<div class="slidenav" id="slidenav">
  <button id="prevSlide" aria-label="Предыдущий слайд">&#8249;</button>
  <span class="slide-counter" id="slideCounter">1 / {total}</span>
  <button id="nextSlide" aria-label="Следующий слайд">&#8250;</button>
</div>

<script>{JS}</script>

</body>
</html>
'''
open(os.path.join(BASE, 'index.html'), 'w', encoding='utf-8').write(html)
open(os.path.join(BASE, 'robots.txt'), 'w').write('User-agent: *\nDisallow: /\n')
found = set(re.findall(r'id="([pa]\d+)"', html))
print(total, 'slides | videos:', len(report), '| broken menu links:', [l for l in re.findall(r'href="#([pa]\d+)"', html) if l not in found])
