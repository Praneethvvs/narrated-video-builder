"""Built-in scene templates. A scene segment with `template: <name>` and a `data:` block is turned into HTML here,
so common scenes need no hand-written HTML. Text fields may contain inline HTML (<b>, &minus;, ...).

Every element that should appear on cue takes a `cue` (a line's cue name from the segment's `lines`), optionally
with an offset: "s2+0.4". Numbers can count up: value: {count: [0, 1080], fmt: usdk, prefix: "", suffix: ""}.
fmt is one of int, usd, usdk, pct, pct1, dec1, dec2, dec3 (see engine/kit.js).
"""
import html as _html


def _val(v):
    if isinstance(v, dict) and "count" in v:
        a, b = v["count"]
        return (f'<span data-anim="count" data-dur="{v.get("dur", 0.9)}" data-from="{a}" data-to="{b}" '
                f'data-fmt="{v.get("fmt", "int")}" data-prefix="{_html.escape(str(v.get("prefix", "")))}" '
                f'data-suffix="{_html.escape(str(v.get("suffix", "")))}"></span>')
    return "" if v is None else str(v)


def _recap(d):
    r = d.get("recap")
    return f'<div class="recap" data-anim="up" data-at="{r["cue"]}">{r["text"]}</div>' if r else ""


def _page(head, foot, d, style, body):
    step = f'<div class="step">{d["step"]}</div>' if d.get("step") else ""
    return (f'{head}<style>{style}</style></head><body><div class="top"></div>{step}'
            f'{body}{foot}</body></html>')


def title(d, head, foot):
    items = d.get("items", [])
    cue = d.get("items_cue", "0.6")
    tiles = "".join(f'<div data-anim="up" data-at="{cue}+{0.25 * i:.2f}"><b>{i + 1}</b>{t}</div>' for i, t in enumerate(items))
    style = """.t { position: absolute; top: 250px; left: 130px; right: 130px; } .t h1 { font-size: 112px; }
.items { display: grid; grid-template-columns: repeat(3, 1fr); gap: 22px; margin-top: 60px; }
.items div { font-size: 32px; background: var(--panel); border: 2px solid var(--rule); border-radius: 16px; padding: 20px 26px; }
.items b { color: var(--accent); margin-right: 10px; }"""
    body = (f'<div class="t"><h1 data-anim="up" data-at="0.1">{d["title"]}</h1>'
            f'<div class="sub" data-anim="up" data-at="0.4" style="font-size:44px;">{d.get("subtitle", "")}</div>'
            f'<div class="items">{tiles}</div></div>')
    return _page(head, foot, {}, style, body)


def card(d, head, foot):
    style = """.c { position: absolute; left: 130px; top: 380px; }
.st { font-size: 34px; font-weight: 700; letter-spacing: 4px; text-transform: uppercase; color: var(--accent); }
.nm { font-size: 84px; font-weight: 700; letter-spacing: -1px; margin-top: 14px; }
.rule { height: 6px; width: 140px; background: var(--accent); border-radius: 3px; margin-top: 30px; }"""
    body = (f'<div class="c"><div class="st" data-anim="up" data-at="0.05">{d.get("label", "")}</div>'
            f'<div class="nm" data-anim="up" data-at="0.25">{d["name"]}</div>'
            f'<div class="rule" data-anim="grow-x" data-at="0.45"></div></div>')
    return _page(head, foot, {}, style, body)


def bullets(d, head, foot):
    pts = "".join(f'<div class="pt" data-anim="left" data-at="{p["cue"]}"><span class="dot"></span><span>{p["text"]}</span></div>'
                  for p in d.get("points", []))
    style = """.pt { display: flex; gap: 26px; align-items: baseline; font-size: 38px; line-height: 1.4; margin-bottom: 28px; max-width: 1500px; }
.dot { flex: none; width: 16px; height: 16px; border-radius: 50%; background: var(--accent); transform: translateY(-6px); }"""
    body = (f'<div class="wrap"><h1 data-at="0">{d["title"]}</h1><div class="sub" data-anim="up" data-at="0.3">{d.get("sub", "")}</div>'
            f'{pts}{_recap(d)}</div>')
    return _page(head, foot, d, style, body)


def calc(d, head, foot):
    """Calculation board: formula strip built piece by piece, one numbered row per step, plain-words card, recap."""
    f_html = "".join(f'<span class="fp" data-anim="up" data-at="{p["cue"]}">{p["text"]}</span>' for p in d.get("formula", []))
    strip = f'<div class="fstrip">{f_html}</div>' if f_html else ""
    rows = "".join(
        f'<div class="crow" data-anim="left" data-at="{r["cue"]}"><span class="cn">{i + 1}</span>'
        f'<span class="cl">{r["label"]}</span><span class="cv">{_val(r.get("value"))}</span></div>'
        for i, r in enumerate(d.get("rows", [])))
    m = d.get("meaning")
    mean = (f'<div class="side"><div class="card mean" data-anim="up" data-at="{m["cue"]}"><span class="tag green">In plain words</span>'
            f'<p>{m["text"]}</p></div></div>') if m else ""
    style = """.fstrip { font-family: 'Cascadia Mono', Consolas, monospace; font-size: 36px; min-height: 64px; display: flex; flex-wrap: wrap; gap: 14px;
  align-items: baseline; background: var(--panel); border: 2px solid var(--rule); border-radius: 14px; padding: 12px 20px; width: fit-content; max-width: 1040px; }
.fp { display: inline-block; }
.crow { display: flex; align-items: center; gap: 22px; height: 84px; border-bottom: 2px solid var(--rule); width: 1040px; }
.cn { flex: none; width: 46px; height: 46px; border-radius: 50%; background: var(--accent); color: #fff; font-weight: 700; font-size: 24px;
  display: flex; align-items: center; justify-content: center; }
.cl { flex: 1; font-size: 30px; color: var(--ink2); line-height: 1.25; }
.cv { font-family: 'Cascadia Mono', Consolas, monospace; font-size: 40px; font-weight: 700; white-space: nowrap; }
.side { position: absolute; left: 1110px; top: 150px; width: 550px; } .mean p { font-size: 31px; }"""
    body = (f'<div class="wrap"><h1 data-at="0">{d["title"]}</h1><div class="sub" data-anim="up" data-at="0.3">{d.get("question", "")}</div>'
            f'{strip}<div style="margin-top: 14px;">{rows}</div>{mean}{_recap(d)}</div>')
    return _page(head, foot, d, style, body)


def cards(d, head, foot):
    """Option board: cards appear one by one, optional small table on the right, recap ribbon."""
    c_html = "".join(
        f'<div class="card" data-anim="up" data-at="{c["cue"]}"><span class="tag {c.get("color", "blue")}">{c.get("tag", "")}</span>'
        f'<h2>{c["title"]}</h2><p>{c.get("text", "")}</p></div>' for c in d.get("cards", []))
    t = d.get("table")
    t_html = ""
    if t:
        head_row = "".join(f"<th>{h}</th>" for h in t["head"])
        body_rows = "".join(
            f'<tr{" class=total" if r.get("total") else ""} data-anim="left" data-at="{r["cue"]}">'
            + "".join(f"<td>{_val(x)}</td>" for x in r["cells"]) + "</tr>" for r in t["rows"])
        t_html = (f'<div class="tbl" data-anim="up" data-at="{t.get("cue", "0.5")}"><div class="tt">{t.get("title", "")}</div>'
                  f'<table class="t"><tr>{head_row}</tr>{body_rows}</table></div>')
    width = "1040px" if t else "100%"
    style = f""".grid {{ display: grid; grid-template-columns: repeat({d.get("cols", 2)}, 1fr); gap: 22px; width: {width}; }}
.grid .card {{ padding: 22px 28px; }} .grid .card h2 {{ font-size: 34px; margin-bottom: 8px; }} .grid .card p {{ font-size: 28px; }}
.tbl {{ position: absolute; left: 1090px; top: 150px; width: 580px; }}
.tt {{ font-size: 26px; font-weight: 700; color: var(--ink2); margin-bottom: 8px; }}
table.t {{ font-size: 30px; width: 100%; }} table.t td, table.t th {{ padding: 10px 16px; }}
table.t td {{ font-family: 'Cascadia Mono', Consolas, monospace; }}"""
    body = (f'<div class="wrap"><h1 data-at="0">{d["title"]}</h1><div class="sub" data-anim="up" data-at="0.3">{d.get("sub", "")}</div>'
            f'<div class="grid">{c_html}</div>{t_html}{_recap(d)}</div>')
    return _page(head, foot, d, style, body)


TEMPLATES = {"title": title, "card": card, "bullets": bullets, "calc": calc, "cards": cards}
