/* Starling — shared data loading + rendering helpers (classic script, no modules). */
(function (global) {
  "use strict";

  // github/linguist colors
  var LANG = {
    Rust: "#dea584", TypeScript: "#3178c6", Go: "#00ADD8", Python: "#3572A5", JavaScript: "#f1e05a",
    Zig: "#ec915c", "C++": "#f34b7d", C: "#8a8a8a", "C#": "#178600", CSS: "#563d7c", Shell: "#89e051",
    Swift: "#F05138", Java: "#b07219", Ruby: "#701516", Kotlin: "#A97BFF", HTML: "#e34c26",
    Dart: "#00B4AB", PHP: "#4F5D95", "Jupyter Notebook": "#DA5B0B", Vue: "#41b883", Lua: "#000080"
  };
  var WLABEL = { day: "Today", week: "This week", month: "This month" };
  var WSUB = { day: "24h", week: "7d", month: "30d" };
  var WSINCE = { day: "vs. yesterday", week: "vs. 7 days ago", month: "vs. 30 days ago" };

  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }
  var fmt = function (n) { return (n == null || isNaN(n)) ? "—" : Number(n).toLocaleString("en-US"); };
  var pctOf = function (p) { p = p || 0; return (p * 100).toFixed(Math.abs(p) < 0.1 ? 1 : 0); };
  var langColor = function (l) { return LANG[l] || "#8A93A0"; };

  // build a safe GitHub URL from owner/name (do not trust arbitrary html_url in an href)
  function repoUrl(r) {
    return "https://github.com/" + encodeURIComponent(r.owner) + "/" + encodeURIComponent(r.name);
  }

  // some linguist colors (JS yellow) are too light for text/thin strokes on light paper
  function readable(hex) {
    var h = hex.replace("#", "");
    var r = parseInt(h.slice(0, 2), 16), g = parseInt(h.slice(2, 4), 16), b = parseInt(h.slice(4, 6), 16);
    var L = (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255;
    if (L < 0.6) return hex;
    function to2(n) { return Math.round(n * 0.42).toString(16).padStart(2, "0"); }
    return "#" + to2(r) + to2(g) + to2(b);
  }

  function sparkline(pts, opts) {
    opts = opts || {};
    var w = opts.w || 112, h = opts.h || 32, pad = opts.pad || 2, stroke = opts.stroke || "var(--up)";
    var fill = opts.fill !== false;
    if (!pts || pts.length < 2) return '<span style="font:11px var(--mono);color:var(--faint)">new</span>';
    var max = Math.max.apply(null, pts), min = Math.min.apply(null, pts), rng = (max - min) || 1;
    var x = function (i) { return pad + (i / (pts.length - 1)) * (w - 2 * pad); };
    var y = function (v) { return h - pad - ((v - min) / rng) * (h - 2 * pad); };
    var d = "M" + x(0).toFixed(1) + " " + y(pts[0]).toFixed(1);
    for (var i = 1; i < pts.length; i++) d += " L" + x(i).toFixed(1) + " " + y(pts[i]).toFixed(1);
    var ex = x(pts.length - 1).toFixed(1), ey = y(pts[pts.length - 1]).toFixed(1);
    var area = fill ? '<path d="' + d + " L" + ex + " " + h + " L" + x(0).toFixed(1) + " " + h + ' Z" fill="' + stroke + '" opacity=".10"/>' : "";
    return '<svg viewBox="0 0 ' + w + " " + h + '" width="' + w + '" height="' + h + '" fill="none" aria-hidden="true">' + area +
      '<path d="' + d + '" stroke="' + stroke + '" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>' +
      '<circle cx="' + ex + '" cy="' + ey + '" r="2.4" fill="' + stroke + '"/></svg>';
  }

  // APG tabs: roving tabindex + arrow-key activation for a .seg[role=tablist]
  function segKeys(el) {
    var tabs = [].slice.call(el.querySelectorAll('[role="tab"]'));
    if (!tabs.length) return;
    function setTabbable() { tabs.forEach(function (t) { t.tabIndex = t.getAttribute("aria-selected") === "true" ? 0 : -1; }); }
    el.addEventListener("keydown", function (e) {
      var i = tabs.indexOf(document.activeElement), j = -1;
      if (i < 0) return;
      if (e.key === "ArrowRight" || e.key === "ArrowDown") j = (i + 1) % tabs.length;
      else if (e.key === "ArrowLeft" || e.key === "ArrowUp") j = (i - 1 + tabs.length) % tabs.length;
      else if (e.key === "Home") j = 0;
      else if (e.key === "End") j = tabs.length - 1;
      if (j < 0) return;
      e.preventDefault(); tabs[j].click(); tabs[j].focus(); setTabbable();
    });
    el.addEventListener("click", setTabbable); // runs after the buttons' own handlers update aria-selected
    setTabbable();
  }

  // Build the marquee ticker from a window's repos (doubled for a seamless loop)
  function buildTicker(el, repos) {
    if (!el) return;
    var top = repos.slice(0, 18);
    el.innerHTML = top.concat(top).map(function (r) {
      return '<a class="tick" href="' + repoUrl(r) + '" target="_blank" rel="noopener" tabindex="-1">' +
        '<span class="sym">' + esc(r.name) + '</span><span class="mv">▲' + pctOf(r.pct_gain) + '%</span></a>';
    }).join("");
  }

  var Starling = {
    data: null,
    LANG: LANG, WLABEL: WLABEL, WSUB: WSUB, WSINCE: WSINCE,
    esc: esc, fmt: fmt, pctOf: pctOf, langColor: langColor, readable: readable,
    sparkline: sparkline, repoUrl: repoUrl, buildTicker: buildTicker,

    load: function () {
      var self = this;
      return fetch("./data/latest.json", { cache: "no-cache" }).then(function (res) {
        if (!res.ok) throw new Error("HTTP " + res.status);
        return res.json();
      }).then(function (json) { self.data = json; return json; });
    },
    win: function (w) {
      var d = this.data && this.data.windows && this.data.windows[w];
      return d || { repos: [], count: 0, boundary_date: "" };
    },
    generatedDate: function () {
      if (!this.data || !this.data.generated_at) return "—";
      var dt = new Date(this.data.generated_at);
      return isNaN(dt) ? this.data.generated_at : dt.toLocaleDateString("en-US", { weekday: "short", year: "numeric", month: "short", day: "numeric" });
    },
    // wire the masthead clock + keyboard support for segmented tab controls
    // (nav current state is static aria-current in each page)
    chrome: function () {
      var clock = document.getElementById("clock");
      if (clock) clock.innerHTML = "UPDATED · <b>" + esc(this.generatedDate()) + "</b> · daily";
      [].slice.call(document.querySelectorAll('.seg[role="tablist"]')).forEach(segKeys);
    },
    // graceful failure into any container id
    fail: function (id, err) {
      var el = document.getElementById(id);
      if (el) el.innerHTML = '<div class="state err" role="alert">Couldn’t load the latest data (' + esc(String(err && err.message || err)) +
        '). It refreshes once a day — try again shortly.</div>';
    }
  };

  global.Starling = Starling;
})(window);
