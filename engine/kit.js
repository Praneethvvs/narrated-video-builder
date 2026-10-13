// Scene kit: GSAP (local node_modules) drives every scene from one paused timeline.
// Python sets window.CUES = {label: seconds} (per-sentence audio offsets), then calls
// window.intervals() once (builds the timeline) and window.seek(t) per frame.
//
// Declarative markup:
//   data-at="cue[+/-sec]"  data-anim = fade|up|left|right|pop|grow-x|grow-y|draw|count|pulse|stagger|keys|hl
//   data-dur, data-out="cue", count: data-from/data-to/data-fmt/data-prefix/data-suffix
//   keys: data-prop (css prop or "text"), data-unit, data-fmt, data-keys="cue:val, cue+0.5:val"
//   <h1 data-at="..."> headlines are revealed word by word with SplitText.
// A scene may also define window.build(tl, at, K) for anything custom.
(function () {
  gsap.registerPlugin(DrawSVGPlugin, SplitText);
  const EASE = 'power2.inOut';
  const fmt = (v, f, el) => {
    const pre = (el && el.dataset.prefix) || '', suf = (el && el.dataset.suffix) || '';
    let s;
    switch (f) {
      case 'usd': s = '$' + Math.round(v).toLocaleString('en-US'); break;
      case 'usdk': s = '$' + Math.round(v).toLocaleString('en-US') + 'k'; break;
      case 'pct': s = Math.round(v) + '%'; break;
      case 'pct1': s = v.toFixed(1) + '%'; break;
      case 'dec1': s = v.toFixed(1); break;
      case 'dec2': s = v.toFixed(2); break;
      case 'dec3': s = v.toFixed(3); break;
      default: s = Math.round(v).toLocaleString('en-US');
    }
    return pre + s + suf;
  };
  const at = spec => {
    if (spec === undefined || spec === '') return 0;
    const m = String(spec).trim().match(/^([A-Za-z_][\w-]*)?\s*([+-]\s*[\d.]+)?$/);
    if (!m) return parseFloat(spec) || 0;
    let t = 0;
    if (m[1]) {
      if (!(m[1] in (window.CUES || {}))) throw new Error('missing cue ' + m[1]);
      t = window.CUES[m[1]];
    }
    if (m[2]) t += parseFloat(m[2].replace(/\s/g, ''));
    return Math.max(0, t);
  };
  const K = {
    fmt, at,
    count(tl, el, from, to, t, dur = 0.9, f = 'int') {
      const o = { v: from };
      el.textContent = fmt(from, f, el);
      tl.to(o, { v: to, duration: dur, ease: 'power1.out', onUpdate() { el.textContent = fmt(o.v, f, el); } }, t);
    },
  };
  let tl = null;
  function setup() {
    tl = gsap.timeline({ paused: true, defaults: { ease: EASE, duration: 0.5 } });
    document.querySelectorAll('h1[data-at]').forEach(h => {
      const st = new SplitText(h, { type: 'words' });
      tl.from(st.words, { yPercent: 70, opacity: 0, stagger: 0.06, duration: 0.55, ease: 'power3.out' }, at(h.dataset.at));
    });
    document.querySelectorAll('[data-anim]').forEach(el => {
      if (el.tagName === 'H1' && el.dataset.at !== undefined) return;
      const a = el.dataset.anim, t = at(el.dataset.at);
      const d = el.dataset.dur ? parseFloat(el.dataset.dur) : null;
      switch (a) {
        case 'fade': tl.from(el, { opacity: 0, duration: d || 0.5 }, t); break;
        case 'up': tl.from(el, { opacity: 0, y: 24, duration: d || 0.55 }, t); break;
        case 'left': tl.from(el, { opacity: 0, x: -36, duration: d || 0.55 }, t); break;
        case 'right': tl.from(el, { opacity: 0, x: 36, duration: d || 0.55 }, t); break;
        case 'pop': tl.from(el, { opacity: 0, scale: 0.94, duration: d || 0.5 }, t); break;
        case 'grow-x': tl.from(el, { scaleX: 0, transformOrigin: 'left center', duration: d || 0.7 }, t); break;
        case 'grow-y': tl.from(el, { scaleY: 0, transformOrigin: 'center bottom', duration: d || 0.7 }, t); break;
        case 'draw': tl.from(el, { drawSVG: '0%', duration: d || 0.9, ease: 'power1.inOut' }, t); break;
        case 'stagger': tl.from(el.children, { opacity: 0, y: 18, stagger: parseFloat(el.dataset.gap || 0.12), duration: d || 0.45 }, t); break;
        case 'pulse': tl.to(el, { scale: 1.06, yoyo: true, repeat: 1, duration: (d || 0.7) / 2, ease: 'sine.inOut' }, t); break;
        case 'hl': tl.to(el, { '--hl': 1, duration: d || 0.5 }, t); break;
        case 'count': {
          tl.from(el, { opacity: 0, duration: 0.2 }, t);
          K.count(tl, el, parseFloat(el.dataset.from || 0), parseFloat(el.dataset.to || 0), t, d || 0.9, el.dataset.fmt);
          break;
        }
        case 'keys': {
          const keys = el.dataset.keys.split(',').map(k => { const i = k.lastIndexOf(':'); return [at(k.slice(0, i)), parseFloat(k.slice(i + 1))]; })
            .sort((x, y) => x[0] - y[0]);
          const prop = el.dataset.prop, unit = el.dataset.unit || '', f = el.dataset.fmt;
          const o = { v: keys[0][1] };
          const apply = () => { if (prop === 'text') el.textContent = fmt(o.v, f, el); else el.style[prop] = o.v + unit; };
          apply();
          if (el.dataset.visible !== 'always') tl.from(el, { opacity: 0, duration: 0.3 }, keys[0][0]);
          for (let i = 1; i < keys.length; i++) tl.to(o, { v: keys[i][1], duration: d || 0.6, onUpdate: apply }, keys[i][0]);
          break;
        }
      }
      if (el.dataset.out) tl.to(el, { opacity: 0, duration: 0.35 }, at(el.dataset.out));
    });
    if (window.build) window.build(tl, at, K);
    tl.seek(0, false);
  }
  window.intervals = () => {
    if (!tl) setup();
    return tl.getChildren(false, true, true).map(c => [c.startTime(), c.startTime() + c.totalDuration()]);
  };
  window.seek = t => { if (!tl) setup(); tl.seek(t, false); return true; };
})();
