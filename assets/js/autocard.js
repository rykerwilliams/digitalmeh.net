// Card hover previews for the 2,273 card links in the migrated posts.
//
// Each link is <a class="card-link" data-cardname="Black Lotus"> and resolves to
// Scryfall. On hover this shows the card image beside the cursor.
//
// Ported from teamserio.us's assets/js/autocard.js with the problems fixed:
//
//   - it refetched on every single mouseenter. Scryfall's API guidelines ask for
//     caching, and a decklist is 40+ links, so passing the cursor down one could
//     fire dozens of identical requests. This caches in memory and localStorage.
//   - it read data.image_uris.normal unconditionally, which throws on a
//     double-faced card: those carry images under card_faces[] instead.
//   - a failed or 404 request threw and left the tooltip blank.
//   - the tooltip was positioned at cursor+15 always, so it ran off the right
//     and bottom edges of the viewport.
//   - no debounce, so sweeping the cursor across a decklist fired a request per
//     link passed over.
(function () {
  "use strict";

  var SELECTOR = "a.card-link[data-cardname]";
  // Bump this whenever the choice of printing changes. v1 stored whatever
  // cards/named?exact= returned, which is Scryfall's default -- a modern
  // reprint. Those entries would otherwise keep being served from a visitor's
  // localStorage forever, showing Dominaria Remastered 2023 for Worldgorger
  // Dragon instead of Judgment 2002, however many times the fetch is fixed.
  var CACHE_KEY = "dm-card-img-v2-original-printing";
  var STALE_KEYS = ["dm-card-img-v1"];
  var HOVER_DELAY = 140;     // ms before asking Scryfall; a sweep fires nothing
  var MAX_W = 336;           // Scryfall "normal" is 488x680; this keeps it tidy

  // A touch device has no hover, so hovering can never fire there. Rather than
  // bail out and leave the feature invisible on a phone, tapping a card name
  // shows the preview and a second tap follows the link to Scryfall.
  var TOUCH = !!(window.matchMedia && window.matchMedia("(hover: none)").matches);

  var mem = {};
  try {
    mem = JSON.parse(localStorage.getItem(CACHE_KEY) || "{}");
    STALE_KEYS.forEach(function (k) { localStorage.removeItem(k); });
  } catch (e) {
    mem = {};
  }

  function remember(name, url) {
    mem[name] = url;
    try {
      localStorage.setItem(CACHE_KEY, JSON.stringify(mem));
    } catch (e) {
      /* quota or private mode: the in-memory cache still works */
    }
  }

  // Cards whose art was pulled into the repo during the migration are served
  // locally, which avoids a request entirely. The layout emits the list of what
  // is actually present, so the other 385 linked cards are not probed and 404ed.
  var LOCAL = {};
  (window.DM_LOCAL_CARDS || []).forEach(function (basename) {
    LOCAL[basename] = true;
  });

  function localCard(name) {
    var slug = name.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
    return LOCAL[slug] ? "/assets/images/cards/" + slug + ".jpg" : null;
  }

  function imageFrom(data) {
    if (!data) return null;
    if (data.image_uris && data.image_uris.normal) return data.image_uris.normal;
    // Double-faced, split and transforming cards put images on each face.
    if (data.card_faces && data.card_faces.length) {
      for (var i = 0; i < data.card_faces.length; i++) {
        var f = data.card_faces[i];
        if (f.image_uris && f.image_uris.normal) return f.image_uris.normal;
      }
    }
    return null;
  }

  var tip = document.createElement("div");
  tip.className = "cardtip";
  tip.setAttribute("aria-hidden", "true");
  document.body.appendChild(tip);

  var shown = false;
  // Last known cursor position. show() needs it: the tooltip is position:fixed,
  // so until top/left are set it renders at its static position -- the bottom of
  // the document, out of view. Positioning only on mousemove meant that hovering
  // a link and holding still showed nothing at all.
  var cx = 0, cy = 0;

  function hide() {
    shown = false;
    tip.classList.remove("is-visible");
    tip.classList.remove("is-centred");
    tip.textContent = "";
  }

  function show(url) {
    var img = document.createElement("img");
    img.alt = "";
    img.width = MAX_W;
    img.src = url;
    tip.textContent = "";
    tip.appendChild(img);
    shown = true;
    tip.classList.add("is-visible");
    position(cx, cy);
    // Re-position once the image has dimensions, so the edge-flip is accurate.
    img.addEventListener("load", function () { position(cx, cy); });
  }

  // Keep the tooltip inside the viewport: flip left or upward near an edge.
  function position(px, py) {
    if (!shown) return;
    var pad = 16;
    var w = tip.offsetWidth || MAX_W;
    var h = tip.offsetHeight || Math.round(MAX_W * 1.4);
    var x = px + pad;
    var y = py + pad;
    if (x + w > window.innerWidth - pad) x = px - w - pad;
    if (y + h > window.innerHeight - pad) y = window.innerHeight - h - pad;
    if (y < pad) y = pad;
    tip.style.left = Math.max(pad, x) + "px";
    tip.style.top = y + "px";
  }

  function place(ev) {
    cx = ev.clientX;
    cy = ev.clientY;
    position(cx, cy);
  }

  // Fetch for a name and hand back the image url, cache first.
  function resolve(name, opts) {
    if (Object.prototype.hasOwnProperty.call(mem, name)) {
      return Promise.resolve(mem[name]);
    }
    var local = localCard(name);
    if (local) {
      remember(name, local);
      return Promise.resolve(local);
    }
    var original = "https://api.scryfall.com/cards/search?" +
                   "q=" + encodeURIComponent('!"' + name + '" not:reprint');
    var exact = "https://api.scryfall.com/cards/named?exact=" + encodeURIComponent(name);
    return fetch(original, opts)
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (d) {
        var card = d && d.data ? d.data[0] : null;
        var url = card ? imageFrom(card) : null;
        if (url) return url;
        return fetch(exact, opts)
          .then(function (r) { return r.ok ? r.json() : null; })
          .then(function (d2) { return d2 ? imageFrom(d2) : null; });
      })
      .then(function (url) {
        if (url) remember(name, url);
        return url;
      })
      .catch(function () { return null; });
  }

  // Touch: centre the preview rather than chasing a cursor that does not exist.
  function showCentred(url) {
    show(url);
    tip.classList.add("is-centred");
    tip.style.left = "";
    tip.style.top = "";
  }

  if (TOUCH) {
    var armed = null;
    document.addEventListener("click", function (ev) {
      var link = ev.target.closest && ev.target.closest(SELECTOR);
      if (!link) {
        if (armed) { armed = null; hide(); }
        return;
      }
      if (armed === link) { armed = null; hide(); return; }   // second tap: follow it
      ev.preventDefault();
      armed = link;
      resolve(link.dataset.cardname).then(function (url) {
        if (url) showCentred(url); else { armed = null; }
      });
    }, false);
  }

  document.querySelectorAll(SELECTOR).forEach(function (link) {
    if (TOUCH) return;
    var timer = null;
    var controller = null;

    link.addEventListener("mouseenter", function (ev) {
      var name = link.dataset.cardname;
      if (!name) return;
      cx = ev.clientX;
      cy = ev.clientY;

      if (mem[name]) {
        show(mem[name]);
        return;
      }

      timer = setTimeout(function () {
        controller = typeof AbortController !== "undefined" ? new AbortController() : null;
        resolve(name, controller ? { signal: controller.signal } : undefined)
          .then(function (url) {
            if (url) show(url); else hide();
          });
      }, HOVER_DELAY);
    });

    link.addEventListener("mousemove", place);

    link.addEventListener("mouseleave", function () {
      if (timer) clearTimeout(timer);
      if (controller) {
        try { controller.abort(); } catch (e) { /* already settled */ }
      }
      hide();
    });
  });
})();
