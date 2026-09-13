"""A single self-contained page for building every chunked playlist on YouTube.

Clicking through dozens of import links is the one genuinely tedious part of the
browser path, so the page tracks which links you have opened (localStorage) and
lets you copy each playlist name for the rename step.
"""

from __future__ import annotations

import html
import json
from pathlib import Path

from ..publish.bulk_links import STEPS, build_links

_CSS = """
:root{--bg:#EFF0F3;--surface:#fff;--surface-2:#F6F7F9;--line:#DCDEE5;--line-soft:#E7E9EF;
--text:#1A1B22;--text-2:#5C6070;--text-3:#868B9B;--accent:#B4551A;--good:#2E7D4F;
--warn:#9A6B12;--warn-bg:#FBF3E0;--shadow:0 1px 2px rgba(20,22,34,.05),0 6px 16px -10px rgba(20,22,34,.18)}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#121319;--surface:#1A1C24;
--surface-2:#20222B;--line:#2E313C;--line-soft:#262933;--text:#ECEDF2;--text-2:#A2A7B6;--text-3:#767C8D;
--accent:#E08A4A;--good:#5FBE87;--warn:#D9AE5A;--warn-bg:#2A2418;--shadow:0 1px 2px rgba(0,0,0,.4),0 8px 20px -12px rgba(0,0,0,.7)}}
:root[data-theme="dark"]{--bg:#121319;--surface:#1A1C24;--surface-2:#20222B;--line:#2E313C;
--line-soft:#262933;--text:#ECEDF2;--text-2:#A2A7B6;--text-3:#767C8D;--accent:#E08A4A;--good:#5FBE87;
--warn:#D9AE5A;--warn-bg:#2A2418;--shadow:0 1px 2px rgba(0,0,0,.4),0 8px 20px -12px rgba(0,0,0,.7)}
*,*::before,*::after{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--text);font:400 15px/1.55 ui-sans-serif,system-ui,-apple-system,Segoe UI,sans-serif}
h1,h2,h3{margin:0;text-wrap:balance;letter-spacing:-.015em}
a{color:inherit}
:focus-visible{outline:2px solid var(--accent);outline-offset:2px;border-radius:4px}
.wrap{max-width:1140px;margin:0 auto;padding:32px 22px 72px}
.top{display:flex;flex-wrap:wrap;gap:18px 32px;align-items:flex-end;justify-content:space-between;
padding-bottom:20px;border-bottom:1px solid var(--line)}
.top h1{font-size:clamp(24px,3.2vw,34px);font-weight:700}
.top p{margin:6px 0 0;color:var(--text-2);max-width:60ch}
.total{text-align:right;font-family:ui-monospace,SFMono-Regular,Menlo,monospace}
.total b{display:block;font-size:28px;font-variant-numeric:tabular-nums}
.total span{font-size:11px;letter-spacing:.09em;text-transform:uppercase;color:var(--text-3)}
.note{display:flex;gap:10px;margin-top:22px;padding:13px 15px;border-radius:8px;background:var(--warn-bg);
border:1px solid color-mix(in srgb,var(--warn) 34%,transparent);font-size:14px}
.note b{color:var(--warn)}
.how{margin:24px 0 0;padding:0;list-style:none;display:grid;gap:11px;
grid-template-columns:repeat(auto-fit,minmax(210px,1fr));counter-reset:s}
.how li{counter-increment:s;background:var(--surface);border:1px solid var(--line-soft);border-radius:9px;
padding:12px 14px;font-size:13.5px;color:var(--text-2)}
.how li::before{content:counter(s);display:inline-flex;align-items:center;justify-content:center;width:19px;
height:19px;margin-right:8px;border-radius:50%;background:var(--text);color:var(--bg);
font:600 11px/1 ui-monospace,monospace;vertical-align:1px}
.bar{height:4px;border-radius:99px;background:var(--line);overflow:hidden;margin-top:26px}
.bar i{display:block;height:100%;width:0;background:var(--accent);transition:width .35s ease}
.grid{display:grid;gap:14px;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));margin-top:22px}
.card{background:var(--surface);border:1px solid var(--line-soft);border-radius:11px;padding:16px 17px 12px;
box-shadow:var(--shadow);display:flex;flex-direction:column;gap:12px}
.card.complete{border-color:color-mix(in srgb,var(--good) 46%,transparent)}
.card-id{display:flex;align-items:center;gap:10px;justify-content:space-between}
.card-id h3{font-family:ui-monospace,monospace;font-size:15px;font-weight:600;color:var(--accent)}
.copy{border:1px solid var(--line);background:var(--surface-2);color:var(--text-2);
font:500 11px/1 inherit;padding:5px 8px;border-radius:5px;cursor:pointer}
.copy:hover{color:var(--text);border-color:var(--text-3)}
.copy.ok{color:var(--good);border-color:var(--good)}
.what{margin:0;font-size:13.5px;color:var(--text-2)}
.stat{margin:0;display:flex;gap:7px;flex-wrap:wrap;font-size:12px;color:var(--text-3);
font-family:ui-monospace,monospace;font-variant-numeric:tabular-nums}
.chips{display:flex;flex-wrap:wrap;gap:7px}
.chip{display:inline-flex;align-items:center;gap:7px;text-decoration:none;border:1px solid var(--line);
background:var(--surface-2);border-radius:7px;padding:6px 10px 6px 7px;font-size:12.5px;color:var(--text-2);transition:.15s}
.chip:hover{border-color:var(--accent);color:var(--text);transform:translateY(-1px)}
.chip-n{display:inline-flex;align-items:center;justify-content:center;min-width:19px;height:19px;border-radius:4px;
background:var(--accent);color:#fff;font:600 11px/1 ui-monospace,monospace}
.chip.done{border-color:color-mix(in srgb,var(--good) 45%,transparent);
background:color-mix(in srgb,var(--good) 11%,transparent);color:var(--text-3)}
.chip.done .chip-n{background:var(--good)}
.chip.done .chip-t{text-decoration:line-through}
.card-ft{display:flex;align-items:center;justify-content:space-between;border-top:1px solid var(--line-soft);
padding-top:9px;margin-top:auto}
.done-n{font:500 12px/1 ui-monospace,monospace;color:var(--text-3);font-variant-numeric:tabular-nums}
.card.complete .done-n{color:var(--good)}
.reset{border:0;background:none;color:var(--text-3);font:500 12px/1 inherit;cursor:pointer;padding:3px 5px}
.reset:hover{color:var(--text)}
.foot{margin-top:46px;padding-top:16px;border-top:1px solid var(--line);display:flex;flex-wrap:wrap;gap:14px;
justify-content:space-between;align-items:center;font-size:12.5px;color:var(--text-3)}
.foot button{border:1px solid var(--line);background:var(--surface);color:var(--text-2);font:500 12px/1 inherit;
padding:7px 11px;border-radius:6px;cursor:pointer}
@media (prefers-reduced-motion:reduce){*{transition:none!important}}
"""

_JS = """
(function(){
 var KEY="ytps-build-"+(document.body.dataset.key||"default"),state={};
 try{state=JSON.parse(localStorage.getItem(KEY)||"{}")||{}}catch(e){state={}}
 function save(){try{localStorage.setItem(KEY,JSON.stringify(state))}catch(e){}}
 var chips=[].slice.call(document.querySelectorAll(".chip")),tot=document.getElementById("tot");
 function render(){
  chips.forEach(function(c){c.classList.toggle("done",!!state[c.dataset.key])});
  document.querySelectorAll(".card").forEach(function(card){
   var cs=card.querySelectorAll(".chip"),n=0;
   cs.forEach(function(c){if(state[c.dataset.key])n++});
   card.querySelector(".done-n").textContent=n+" / "+cs.length;
   card.classList.toggle("complete",cs.length>0&&n===cs.length)});
  var d=chips.filter(function(c){return state[c.dataset.key]}).length;
  tot.textContent=d+"/"+chips.length;
  document.querySelector(".bar i").style.width=(chips.length?d/chips.length*100:0)+"%"}
 chips.forEach(function(c){c.addEventListener("click",function(){state[c.dataset.key]=true;save();render()})});
 document.querySelectorAll(".reset").forEach(function(b){b.addEventListener("click",function(){
  b.closest(".card").querySelectorAll(".chip").forEach(function(c){delete state[c.dataset.key]});save();render()})});
 document.getElementById("resetAll").addEventListener("click",function(){state={};save();render()});
 document.querySelectorAll(".copy").forEach(function(b){b.addEventListener("click",function(){
  var t=b.dataset.copy,ok=function(){var o=b.textContent;b.textContent="Copied";b.classList.add("ok");
   setTimeout(function(){b.textContent=o;b.classList.remove("ok")},1200)};
  function fb(){var a=document.createElement("textarea");a.value=t;a.style.position="fixed";a.style.opacity=0;
   document.body.appendChild(a);a.select();try{document.execCommand("copy");ok()}catch(e){}document.body.removeChild(a)}
  if(navigator.clipboard&&navigator.clipboard.writeText){navigator.clipboard.writeText(t).then(ok,fb)}else{fb()}})});
 render()})();
"""


def write_console(chunks, path: str | Path, title: str = "Playlist Build Console") -> Path:
    """`chunks` is a list of ytps.chunking.Chunk."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    e = html.escape
    cards, total = [], 0
    for ch in chunks:
        links = build_links(ch.songs)
        total += len(links)
        chips = "".join(
            f'<a class="chip" href="{e(bl["url"])}" target="_blank" rel="noopener" '
            f'data-key="{e(ch.name)}::{bl["index"]}"><span class="chip-n">{bl["index"]}</span>'
            f'<span class="chip-t">{"Save as new" if bl["index"] == 1 else "Add all"}</span></a>'
            for bl in links
        )
        cards.append(
            f'<article class="card"><div class="card-id"><h3>{e(ch.name)}</h3>'
            f'<button class="copy" type="button" data-copy="{e(ch.name)}">Copy name</button></div>'
            f'<p class="what">{e(ch.description)}</p>'
            f'<p class="stat"><span>{len(ch.songs)} songs</span><span>·</span>'
            f'<span>{ch.runtime}</span><span>·</span><span>{len(links)} link'
            f'{"s" if len(links) != 1 else ""}</span></p>'
            f'<div class="chips">{chips}</div>'
            f'<footer class="card-ft"><span class="done-n">0 / {len(links)}</span>'
            f'<button class="reset" type="button">Reset</button></footer></article>'
        )
    steps = "".join(f"<li>{e(s)}</li>" for s in STEPS)
    songs_total = sum(len(c.songs) for c in chunks)
    key = json.dumps(title)[1:-1].replace(" ", "-").lower()
    return _write(path, title, key, cards, steps, total, songs_total, len(chunks))


def _write(path, title, key, cards, steps, total, songs_total, n_chunks) -> Path:
    e = html.escape
    path.write_text(
        f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{e(title)}</title><style>{_CSS}</style></head>
<body data-key="{e(key)}"><div class="wrap">
<div class="top"><div><h1>{e(title)}</h1>
<p>{n_chunks} playlists, {songs_total} songs. Each link builds a temporary playlist of up to 50 videos
— save the first, then add the rest into it.</p></div>
<div class="total"><b id="tot">0/{total}</b><span>links opened</span></div></div>
<p class="note"><b>Before you start —</b>&nbsp;sign in to the YouTube account that should own these playlists.</p>
<ol class="how">{steps}</ol>
<div class="bar"><i></i></div>
<div class="grid">{"".join(cards)}</div>
<div class="foot"><span>Progress is saved in this browser only. Songs repeat across playlists by design.</span>
<button id="resetAll" type="button">Reset all progress</button></div>
</div><script>{_JS}</script></body></html>""",
        encoding="utf-8",
    )
    return path
