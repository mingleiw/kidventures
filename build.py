#!/usr/bin/env python3
"""
Generate the site: one page per city, plus a root city picker.

    python3 build.py

Reads data/*.json and templates/*, writes index.html and <city-slug>/index.html.
Everything it writes is committed, so GitHub Pages still serves plain static
files with no build running anywhere.

Why a build step at all: a city page needs its places sorted by distance from
that city. Doing it here rather than in the browser means each page ships
genuinely different, crawlable content and still works with JavaScript off.
"""

import json, math, os, re, shutil, html, datetime, hashlib

ROOT = os.path.dirname(os.path.abspath(__file__))
SITE_NAME = 'Kidventures'


def _asset_v(rel):
    with open(os.path.join(ROOT, rel), 'rb') as f:
        return hashlib.sha1(f.read()).hexdigest()[:10]


# Cache-buster for CSS/JS: the hash changes only when the file's contents do,
# so daily data-only rebuilds keep using the cached assets while a code change
# always fetches fresh. Without this, browsers sit on the old app.js after a
# deploy and dated events silently stop rendering.
APP_JS_V = _asset_v('assets/app.js')
STYLE_V = _asset_v('assets/style.css')

# Change this if the repo is renamed or a custom domain is pointed at the site:
# it drives every canonical URL and the sitemap, and a wrong value silently tells
# search engines the pages live somewhere they don't.
BASE_URL = 'https://mingleiw.github.io/kidventures/'

# A city needs at least this many places within MAX_MILES to get its own page.
# Below that the page would be mostly other cities' content — thin, duplicated,
# and worth less than no page at all.
MIN_PLACES = 4
MAX_MILES = 25

# A city page lists only places within this radius. Without a cap every page
# carries all 30 places in a different order, which is 38 near-duplicate pages
# padded with destinations nobody would drive to from there.
LIST_MILES = 40


def load(name):
    with open(os.path.join(ROOT, 'data', name), encoding='utf-8') as f:
        return json.load(f)


def read(path):
    with open(os.path.join(ROOT, path), encoding='utf-8') as f:
        return f.read()


def slugify(name):
    return re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')


def miles(a, b, c, d):
    R, r = 3958.8, math.pi / 180
    dla, dlo = (c - a) * r, (d - b) * r
    s = math.sin(dla / 2) ** 2 + math.cos(a * r) * math.cos(c * r) * math.sin(dlo / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(s), math.sqrt(1 - s))


def show_miles(d):
    return ('%.1f' % d) if d < 10 else str(int(round(d)))


REGIONS = {'sf': 'San Francisco', 'marin': 'Marin & North Bay', 'east': 'East Bay',
           'peninsula': 'Peninsula', 'south': 'South Bay', 'sac': 'Sacramento area'}

GROUPS = [('sf', 'San Francisco'), ('marin', 'Marin & North Bay'), ('east', 'East Bay'),
          ('peninsula', 'Peninsula'), ('south', 'South Bay'), ('sac', 'Sacramento area')]

SPRITE = read('templates/sprite.svg')
TIPS = read('templates/tips.html')

HEAD = '''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>{title}</title>
<meta name="description" content="{desc}" />
<link rel="canonical" href="{canonical}" />

<meta property="og:type" content="website" />
<meta property="og:title" content="{title}" />
<meta property="og:description" content="{desc}" />
<meta property="og:url" content="{canonical}" />

<link rel="icon" href="{up}assets/favicon.svg" type="image/svg+xml" />
<link rel="preconnect" href="https://fonts.googleapis.com" />
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
<link href="https://fonts.googleapis.com/css2?family=Baloo+2:wght@500;600;700;800&family=Nunito:wght@400;600;700;800&display=swap" rel="stylesheet" />
<link rel="stylesheet" href="{up}assets/style.css?v=__STYLE_V__" />
<script>document.documentElement.className += ' js';</script>
</head>
<body>

<a class="skip" href="#list">Skip to places</a>
<div class="grain" aria-hidden="true"></div>

''' + SPRITE + '''

<header class="site-header">
  <div class="wrap header-inner">
    <a class="brand" href="{up}">
      <span class="brand-mark" aria-hidden="true"><svg width="19" height="19"><use href="#i-park"/></svg></span>
      <span class="brand-text">
        <strong>''' + SITE_NAME + '''</strong>
        <small>Northern California</small>
      </span>
    </a>
    <nav class="nav">{nav}</nav>
  </div>
</header>
'''

# Bake the CSS content hash into the template once: every page served after a
# style.css change points at a new URL, so no browser keeps the old stylesheet.
HEAD = HEAD.replace('__STYLE_V__', STYLE_V)

FOOT = '''
<footer class="site-footer">
  <div class="wrap footer-inner">
    <p class="footer-brand">''' + SITE_NAME + '''</p>
    <p class="footer-note">Find somewhere to take them today.</p>
    <p class="footer-disclaimer">
      Places listed are long-running and established.
      <strong>Hours, admission and seasonal closures change without notice &mdash; always
      confirm through the map link before you set out.</strong>
    </p>
  </div>
</footer>
</body>
</html>
'''


def place_card(p, dist=None):
    meta = ''
    if dist is not None:
        meta += '<li class="m-dist">%s mi</li>' % show_miles(dist)
    meta += '<li class="m-region">%s</li><li class="m-age">%s</li><li class="m-env">%s</li>' % (
        REGIONS.get(p['region'], p['region']), p['ages'], p['envlabel'])
    return '''
        <article class="card" data-cat="{cat}" data-age="{age}" data-region="{region}" data-env="{env}"{dattr}>
          <div class="card-top">
            <span class="ico"><svg width="20" height="20"><use href="#{icon}"/></svg></span>
            <div><h3>{name}</h3><p class="en">{where}</p></div>
          </div>
          <p class="desc">{desc}</p>
          <ul class="meta">{meta}</ul>
          <p class="note"><b>Before you go</b> {note}</p>
          <a class="map" href="https://www.google.com/maps/search/?api=1&query={mapq}" target="_blank" rel="noopener">{cta}</a>
        </article>
'''.format(dattr=('' if dist is None else ' data-dist="%.1f"' % dist), meta=meta, **p)


FILTERS = '''
      <div class="filters" role="group" aria-label="Filters">
        <div class="filter-row">
          <span class="filter-label">Age</span>
          <div class="chips" data-group="age">
            <button class="chip is-on" data-v="all">Any age</button>
            <button class="chip" data-v="0-2">Under 3</button>
            <button class="chip" data-v="3-5">3&ndash;5</button>
            <button class="chip" data-v="6-9">6&ndash;9</button>
            <button class="chip" data-v="10+">10 and up</button>
          </div>
        </div>
        <div class="filter-row">
          <span class="filter-label">Weather</span>
          <div class="chips" data-group="env">
            <button class="chip is-on" data-v="all">Either</button>
            <button class="chip" data-v="indoor">Mostly indoors</button>
            <button class="chip" data-v="outdoor">Mostly outdoors</button>
          </div>
        </div>
        <div class="filter-foot">
          <p class="filter-count" id="count" aria-live="polite"></p>
          <button class="reset" id="reset" hidden>Clear all</button>
        </div>
      </div>
'''


def city_page(town, places, events, dated, base):
    slug = slugify(town['name'])
    name = town['name']
    ranked = sorted(((miles(town['lat'], town['lon'], p['lat'], p['lon']), p) for p in places),
                    key=lambda x: x[0])
    listed = [(d, p) for d, p in ranked if d <= LIST_MILES]
    near = [p for d, p in ranked if d <= MAX_MILES]
    ev = [e for e in events if e['region'] == town['region']]
    # Dated events (e.g. library storytimes refreshed daily) join the weekly
    # ones for the 7 days the strip actually shows. Anything further out is
    # refreshed into view by tomorrow's build.
    today = datetime.date.today()
    week = {str(today + datetime.timedelta(days=i)) for i in range(7)}
    ev += [e for e in dated if e['region'] == town['region'] and e['date'] in week]

    title = 'Where to take the kids in %s · %s' % (name, SITE_NAME)
    desc = ('Places to take kids near %s, sorted by how far they are. '
            'The closest is %s, %s miles away.' % (name, ranked[0][1]['name'], show_miles(ranked[0][0])))

    out = HEAD.format(title=html.escape(title, quote=True), desc=html.escape(desc, quote=True),
                      canonical='%s%s/' % (base, slug), up='../',
                      nav='<a href="../"><span class="nav-full">Change city</span>'
                          '<span class="nav-short">Cities</span></a>')

    out += '''
<main id="top">

  <section class="hero">
    <div class="wrap hero-inner">
      <h1 class="hero-title"><span class="hl">Where to take the kids in %s</span></h1>
      <p class="lede">%d places within %d miles, closest first. %s</p>
      <p class="city-switch"><a href="../">Not your city? Pick another &rarr;</a></p>
    </div>
  </section>

  <!-- ad slot: below the fold, above the answer -->

  <section class="pick-section" id="today">
    <div class="wrap">
      <div class="section-head">
        <h2 id="todayHead">Today, near %s</h2>
        <p class="section-sub" id="todayWhy">Closest to you first.</p>
      </div>
      <div class="picks" id="picks"></div>
      <p class="picks-note" id="picksNote"></p>
    </div>
  </section>
''' % (html.escape(name), len(listed), LIST_MILES,
       'Weekly markets and events too.' if ev else '',
       html.escape(name))

    if ev:
        out += '''
  <section class="week" id="week">
    <div class="wrap">
      <div class="section-head">
        <h2>This week in the %s</h2>
        <p class="section-sub">Regular weekly events &mdash; markets, storytimes, open gyms</p>
      </div>
      <div class="daystrip" id="daystrip" role="tablist" aria-label="Pick a day"></div>
      <div class="events" id="events"></div>
      <p class="empty" id="weekEmpty" hidden></p>
      <p class="week-foot">
        Times are what organisers publish for the regular weekly slot.
        Schedules change and sessions get cancelled &mdash; confirm with the venue before you set out.
      </p>
    </div>
  </section>
''' % html.escape(REGIONS.get(town['region'], town['region']))

    out += '''
  <section class="list-section" id="list">
    <div class="wrap">
      <div class="section-head">
        <h2>Places near %s</h2>
        <p class="section-sub">Open year-round, closest first</p>
      </div>
%s
      <div class="cards" id="cards">
%s
      </div>
      <p class="empty" id="empty" hidden>Nothing matches that combination &mdash; try loosening a filter.</p>
    </div>
  </section>
''' % (html.escape(name), FILTERS, ''.join(place_card(p, d) for d, p in listed))

    out += TIPS
    out += '\n</main>\n'
    out += '<script>\nvar TOWN = %s;\nvar EVENTS = %s;\n</script>\n' % (
        json.dumps({'name': name, 'lat': town['lat'], 'lon': town['lon']}),
        json.dumps(ev, ensure_ascii=False))
    out += '<script src="../assets/app.js?v=' + APP_JS_V + '"></script>\n'
    out += FOOT
    return slug, out


def root_page(towns_with_pages, places, base):
    title = '%s · Where to take the kids in Northern California' % SITE_NAME
    desc = ('Pick your city and get places to take the kids, sorted by how far away they are. '
            '%d cities across the Bay Area and Sacramento.' % len(towns_with_pages))

    out = HEAD.format(title=html.escape(title, quote=True), desc=html.escape(desc, quote=True),
                      canonical=base, up='', nav='')

    options, links = '', ''
    for key, label in GROUPS:
        group = [t for t in towns_with_pages if t['region'] == key]
        if not group:
            continue
        options += '            <optgroup label="%s">\n' % html.escape(label)
        links += '        <section class="city-group">\n          <h3>%s</h3>\n          <ul>\n' % html.escape(label)
        for t in group:
            s = slugify(t['name'])
            options += '              <option value="%s/">%s</option>\n' % (s, html.escape(t['name']))
            links += '            <li><a href="%s/">%s</a></li>\n' % (s, html.escape(t['name']))
        options += '            </optgroup>\n'
        links += '          </ul>\n        </section>\n'

    out += '''
<main id="top">
  <section class="hero">
    <div class="wrap hero-inner">
      <h1 class="hero-title">
        <span class="hl">Where are we</span>
        <span class="hl">going today?</span>
      </h1>
      <p class="lede">
        Pick your city. You get the places nearby, closest first, with the parking
        and weather notes that decide whether it is actually worth the drive.
      </p>

      <div class="picker">
        <p class="picker-q">Choose your city</p>
        <div class="loc-row">
          <select id="citySelect" aria-label="Choose your city">
            <option value="">Pick a city&hellip;</option>
%s          </select>
        </div>
        <p class="loc-hint" id="lastCity" hidden></p>
      </div>
    </div>
  </section>

  <!-- ad slot: between picker and city index -->

  <section class="list-section" id="list">
    <div class="wrap">
      <div class="section-head">
        <h2>All cities</h2>
        <p class="section-sub">%d cities, %d places. Every city links straight through.</p>
      </div>
      <div class="city-index">
%s      </div>
    </div>
  </section>
</main>
''' % (options, len(towns_with_pages), len(places), links)

    out += '''<script>
// Offer the city this browser used last, without getting in the way of the list.
(function () {
  var sel = document.getElementById('citySelect');
  var hint = document.getElementById('lastCity');
  sel.addEventListener('change', function () {
    if (sel.value) location.href = sel.value;
  });
  try {
    var last = localStorage.getItem('owtk.city');
    if (last && document.querySelector('.city-index a[href="' + last + '/"]')) {
      hint.hidden = false;
      hint.innerHTML = 'Last time you looked at <a href="' + last + '/">' +
        document.querySelector('.city-index a[href="' + last + '/"]').textContent + '</a>.';
    }
  } catch (e) {}
})();
</script>
'''
    out += FOOT
    return out


def main():
    towns = load('towns.json')
    places = load('places.json')
    events = load('events.json')
    try:
        dated = load('dated_events.json')
    except FileNotFoundError:
        dated = []  # first run before any refresh; weekly events still render
    base = BASE_URL

    keep, skipped = [], []
    for t in towns:
        n = sum(1 for p in places if miles(t['lat'], t['lon'], p['lat'], p['lon']) <= MAX_MILES)
        (keep if n >= MIN_PLACES else skipped).append((t, n))

    towns_with_pages = [t for t, _ in keep]

    # remove previously generated city directories that no longer qualify
    valid = {slugify(t['name']) for t in towns_with_pages}
    for entry in os.listdir(ROOT):
        p = os.path.join(ROOT, entry)
        if os.path.isdir(p) and os.path.exists(os.path.join(p, '.generated')) and entry not in valid:
            shutil.rmtree(p)

    for t in towns_with_pages:
        slug, page = city_page(t, places, events, dated, base)
        d = os.path.join(ROOT, slug)
        os.makedirs(d, exist_ok=True)
        open(os.path.join(d, 'index.html'), 'w', encoding='utf-8').write(page)
        open(os.path.join(d, '.generated'), 'w').write('written by build.py\n')

    open(os.path.join(ROOT, 'index.html'), 'w', encoding='utf-8').write(
        root_page(towns_with_pages, places, base))

    # sitemap, so the city pages are actually discoverable
    urls = [base] + ['%s%s/' % (base, slugify(t['name'])) for t in towns_with_pages]
    sm = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    sm += ''.join('  <url><loc>%s</loc></url>\n' % u for u in urls)
    sm += '</urlset>\n'
    open(os.path.join(ROOT, 'sitemap.xml'), 'w', encoding='utf-8').write(sm)
    open(os.path.join(ROOT, 'robots.txt'), 'w', encoding='utf-8').write(
        'User-agent: *\nAllow: /\nSitemap: %ssitemap.xml\n' % base)

    print('built %d city pages' % len(towns_with_pages))
    if skipped:
        print('skipped (fewer than %d places within %d mi):' % (MIN_PLACES, MAX_MILES))
        for t, n in skipped:
            print('   %-14s %d' % (t['name'], n))


if __name__ == '__main__':
    main()
