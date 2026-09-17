/* Shared by every city page.

   Distances are already baked into each card's data-dist at build time, so
   this script never computes geography. It handles the three things that
   can only happen in a browser: today's weather, the shortlist that depends
   on it, and filtering. With JavaScript off the page still renders every
   place, in distance order, which is the important half. */

(function () {
  if (typeof TOWN === 'undefined') return;

  var cards   = [].slice.call(document.querySelectorAll('#cards .card'));
  var countEl = document.getElementById('count');
  var emptyEl = document.getElementById('empty');
  var resetEl = document.getElementById('reset');
  var picksE  = document.getElementById('picks');
  var whyE    = document.getElementById('todayWhy');
  var noteE   = document.getElementById('picksNote');

  var state = { age: 'all', env: 'all' };
  var weather = null;              // null means "unknown", never guessed

  // Remember which city this browser looked at, so the index can offer it.
  try {
    var seg = location.pathname.replace(/\/+$/, '').split('/').pop();
    if (seg) localStorage.setItem('owtk.city', seg);
  } catch (e) {}

  function esc(s) {
    return String(s).replace(/[&<>"]/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c];
    });
  }

  function isIndoor(card) {
    return (card.getAttribute('data-env') || '').indexOf('indoor') !== -1;
  }

  function dist(card) { return +card.getAttribute('data-dist'); }

  // Lower is better: miles, nudged by what today is like.
  function score(card) {
    var d = dist(card);
    if (!weather) return d;
    if (weather.wet || weather.cold) return isIndoor(card) ? d * 0.45 : d * 1.9;
    return isIndoor(card) ? d * 1.15 : d * 0.85;
  }

  // The heading states the rule for today, so a row only speaks up when it
  // is an exception to that rule.
  function reason(card) {
    if (!weather) return '';
    var indoor = isIndoor(card);
    if ((weather.wet || weather.cold) && !indoor) {
      return weather.wet ? 'Mostly outdoors, so expect to get wet.' : 'Mostly outdoors, so wrap up.';
    }
    if (!weather.wet && !weather.cold && indoor) return 'Indoors, if you want a break from the sun.';
    return '';
  }

  function glyph(id) {
    return '<svg class="wx" width="21" height="21" aria-hidden="true"><use href="#' + id + '"/></svg>';
  }

  function renderPicks() {
    var live = cards.filter(function (c) { return !c.hidden; })
                    .sort(function (a, b) { return score(a) - score(b); })
                    .slice(0, 3);

    if (weather === null)      whyE.innerHTML = 'Closest to you first.';
    else if (weather.wet)      whyE.innerHTML = glyph('i-rain') + 'It’s raining, so indoor ideas come first.';
    else if (weather.cold)     whyE.innerHTML = glyph('i-cold') + 'It’s cold out (' + weather.tmaxF + '&deg;F), so indoor ideas come first.';
    else                       whyE.innerHTML = glyph('i-sun') + 'Dry and ' + weather.tmaxF + '&deg;F, so outdoor ideas come first.';

    picksE.innerHTML = live.map(function (c, i) {
      var r = reason(c);
      var href = c.querySelector('.map') ? c.querySelector('.map').getAttribute('href') : '#list';
      return '<a class="pick' + (i === 0 ? ' is-top' : '') + '" href="' + esc(href) + '" target="_blank" rel="noopener">' +
        '<span class="pick-line">' +
          '<span class="pick-name">' + esc(c.querySelector('h3').textContent) + '</span>' +
          '<span class="pick-leader" aria-hidden="true"></span>' +
          '<span class="pick-dist">' + esc(c.getAttribute('data-dist')) + ' mi</span>' +
        '</span>' +
        (r ? '<span class="pick-reason">' + esc(r) + '</span>' : '') +
      '</a>';
    }).join('');

    var n = cards.filter(function (c) { return !c.hidden; }).length;
    noteE.textContent = n ? 'From ' + n + ' places near ' + TOWN.name + '. Full list below.'
                          : 'No places match your filters.';
  }

  function matches(card) {
    for (var k in state) {
      if (state[k] === 'all') continue;
      if ((card.getAttribute('data-' + k) || '').split(/\s+/).indexOf(state[k]) === -1) return false;
    }
    return true;
  }

  function apply() {
    var n = 0;
    cards.forEach(function (c) { var ok = matches(c); c.hidden = !ok; if (ok) n++; });
    var filtered = state.age !== 'all' || state.env !== 'all';
    countEl.textContent = filtered ? n + (n === 1 ? ' place' : ' places') + ' match'
                                   : 'Showing all ' + n + ' places';
    emptyEl.hidden = n !== 0;
    resetEl.hidden = !filtered;
    document.querySelectorAll('[data-group]').forEach(function (g) {
      var key = g.getAttribute('data-group');
      g.querySelectorAll('.chip').forEach(function (b) {
        b.classList.toggle('is-on', b.getAttribute('data-v') === state[key]);
      });
    });
    renderPicks();
  }

  document.querySelectorAll('[data-group]').forEach(function (g) {
    var key = g.getAttribute('data-group');
    g.addEventListener('click', function (e) {
      var btn = e.target.closest('.chip');
      if (!btn || !g.contains(btn)) return;
      state[key] = btn.getAttribute('data-v');
      apply();
    });
  });

  resetEl.addEventListener('click', function () {
    state = { age: 'all', env: 'all' };
    apply();
  });

  // Weather is an enhancement. Any failure leaves it unknown and the
  // shortlist ranks on distance alone, claiming nothing about the sky.
  (function loadWeather() {
    if (!window.fetch) return;
    var url = 'https://api.open-meteo.com/v1/forecast?latitude=' + TOWN.lat +
              '&longitude=' + TOWN.lon +
              '&daily=precipitation_sum,temperature_2m_max&timezone=auto&forecast_days=1';
    var done = false;
    var timer = setTimeout(function () { if (!done) { done = true; renderPicks(); } }, 4000);

    fetch(url).then(function (r) {
      if (!r.ok) throw new Error('bad status');
      return r.json();
    }).then(function (j) {
      var p = j && j.daily && j.daily.precipitation_sum && j.daily.precipitation_sum[0];
      var t = j && j.daily && j.daily.temperature_2m_max && j.daily.temperature_2m_max[0];
      if (typeof p !== 'number' || typeof t !== 'number') throw new Error('bad shape');
      weather = { wet: p >= 1, cold: t < 15, tmaxF: Math.round(t * 9 / 5 + 32) };
    }).catch(function () {
      weather = null;
    }).then(function () {
      if (!done) { done = true; clearTimeout(timer); }
      renderPicks();
    });
  })();

  apply();
})();

/* ---- This week ---- */
(function () {
  var stripEl = document.getElementById('daystrip');
  var evEl    = document.getElementById('events');
  var weekMt  = document.getElementById('weekEmpty');
  if (!stripEl || !evEl || typeof EVENTS === 'undefined') return;

  var DAYS  = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];
  var SHORT = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];

  var today = new Date(); today.setHours(0, 0, 0, 0);
  var week = [];
  for (var i = 0; i < 7; i++) {
    var d = new Date(today); d.setDate(today.getDate() + i); week.push(d);
  }
  var picked = 0;

  function esc(s) {
    return String(s).replace(/[&<>"]/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c];
    });
  }

  function hhmm(t) {
    var p = t.split(':'), h = +p[0], m = p[1], ap = h >= 12 ? 'pm' : 'am';
    h = h % 12; if (h === 0) h = 12;
    return m === '00' ? h + ' ' + ap : h + ':' + m + ' ' + ap;
  }

  function strip() {
    stripEl.innerHTML = '';
    week.forEach(function (d, i) {
      var b = document.createElement('button');
      b.className = 'day' + (i === picked ? ' is-on' : '');
      b.setAttribute('role', 'tab');
      b.setAttribute('aria-selected', i === picked ? 'true' : 'false');
      var label = i === 0 ? 'Today' : (i === 1 ? 'Tomorrow' : SHORT[d.getDay()]);
      b.innerHTML = '<span class="day-name">' + label + '</span><span class="day-num">' + d.getDate() + '</span>';
      b.addEventListener('click', function () { picked = i; strip(); render(); });
      stripEl.appendChild(b);
    });
  }

  function render() {
    var d = week[picked];
    // An entry may have no time: the day and venue are confirmed but the hour
    // is not. Those sort last and say so rather than showing a made-up clock.
    var list = EVENTS.filter(function (e) { return e.day === d.getDay(); })
                     .sort(function (a, b) {
                       var ta = a.time || '99:99', tb = b.time || '99:99';
                       return ta < tb ? -1 : (ta > tb ? 1 : 0);
                     });

    evEl.innerHTML = list.map(function (e) {
      var when = e.time ? hhmm(e.time) + (e.until ? ' – ' + hhmm(e.until) : '') : '';
      return '<article class="event">' +
        '<div class="ev-time' + (when ? '' : ' ev-time-unknown') + '">' +
          (when ? esc(when) : 'Time not confirmed') + '</div>' +
        '<div class="ev-body">' +
          '<h3>' + esc(e.title) + '</h3>' +
          '<p class="ev-where">' + esc(e.venue) + ', ' + esc(e.city) + '</p>' +
          '<p class="ev-blurb">' + esc(e.blurb) + '</p>' +
          '<div class="ev-foot">' +
            '<span class="ev-tag">' + esc(e.ages) + '</span>' +
            '<a class="map" href="https://www.google.com/maps/search/?api=1&query=' +
              encodeURIComponent(e.venue + ' ' + e.city) + '" target="_blank" rel="noopener">Map</a>' +
            (e.source ? '<a class="ev-src" href="' + esc(e.source) + '" target="_blank" rel="noopener">Where this came from</a>' : '') +
          '</div>' +
        '</div></article>';
    }).join('');

    var when = picked === 0 ? 'today' : (picked === 1 ? 'tomorrow' : 'on ' + DAYS[d.getDay()]);
    weekMt.hidden = list.length !== 0;
    weekMt.textContent = 'Nothing listed ' + when + '.';
  }

  strip();
  render();
})();
