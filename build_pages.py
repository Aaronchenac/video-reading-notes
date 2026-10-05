#!/usr/bin/env python3
"""把 Obsidian 里的完整图文阅读稿转成 GitHub Pages 页面（index.html + cubox.html）。

用法: build_pages.py <源目录> [源目录 ...]
每个源目录 = 00-Inbox/{日期}-{简称}/，内含 {标题}-完整图文阅读稿.md + assets/。
输出到本仓库 {video_id}/ 下：index.html（带样式阅读版）、cubox.html（Cubox 抓取版，图片绝对 URL）、
assets/、text.txt、subtitle.srt。
"""
import html
import os
import re
import shutil
import sys

REPO_DIR = os.environ.get("OUT_ROOT") or os.path.dirname(os.path.abspath(__file__))
# 图片绝对地址的宿主：默认 GitHub Pages；给香港服务器构建时设 SITE=http://43.135.4.239:8080
SITE = os.environ.get("SITE") or "https://aaronchenac.github.io/video-reading-notes"

CSS = """:root{--paper:#fbfaf7;--ink:#1e2d38;--muted:#687779;--line:#dedfd8;--accent:#176e68;--wash:#edf3ef}
*{box-sizing:border-box}html{scroll-behavior:smooth;scroll-padding-top:28px}
body{margin:0;background:var(--paper);color:var(--ink);font-family:"PingFang SC","Noto Sans CJK SC","Microsoft YaHei",sans-serif;font-size:18px;line-height:1.95}
a{color:var(--accent);text-underline-offset:4px}::selection{background:#d2e9de}
header{max-width:1080px;margin:auto;padding:56px 28px 28px;border-bottom:1px solid var(--line)}
.eyebrow{font-size:12px;letter-spacing:.19em;color:var(--accent);font-weight:700}
h1{font-size:clamp(28px,4.4vw,46px);line-height:1.28;font-weight:700;letter-spacing:-.02em;margin:14px 0 14px}
.subtitle{font-size:19px;color:#475b60;margin:0 0 20px}
.metadata{display:flex;gap:8px 20px;flex-wrap:wrap;font-size:14px;color:var(--muted)}
main{max-width:1080px;margin:0 auto;padding:34px 28px 80px}
.intro{font-size:19px;color:#43575a;border-left:3px solid var(--accent);padding-left:20px;margin-bottom:38px}
section{margin:0 0 46px}
h2{font-size:25px;line-height:1.45;margin:0 0 18px;font-weight:650}
h3{font-size:20px;line-height:1.5;margin:26px 0 12px;font-weight:650;color:#2b414c}
p{margin:0 0 18px}
figure{margin:26px 0}
figure img{width:100%;height:auto;border:1px solid var(--line);border-radius:6px;display:block}
figcaption{font-size:14px;color:var(--muted);line-height:1.75;margin-top:9px}
blockquote{margin:22px 0;padding:14px 20px;background:var(--wash);border-left:3px solid var(--accent);font-size:17px;color:#3c5257}
blockquote p{margin:0}
ul,ol{margin:0 0 18px;padding-left:26px}li{margin:7px 0}
table{border-collapse:collapse;width:100%;margin:22px 0;font-size:16px}
th,td{border:1px solid var(--line);padding:9px 12px;text-align:left}
th{background:var(--wash);font-weight:650}
footer{border-top:1px solid var(--line);margin-top:40px;padding-top:20px;font-size:14px;color:var(--muted)}
.srcline{font-size:14px;color:var(--muted)}"""


def esc(t):
    return html.escape(t, quote=False)


def inline(t):
    """行内：链接、加粗。先转义再插标签。"""
    t = esc(t)
    t = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', t)
    t = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", t)
    return t


def parse_front(md):
    m = re.match(r"^---\n(.*?)\n---\n", md, re.S)
    if not m:
        return {}, md
    fm = {}
    for line in m.group(1).splitlines():
        if re.match(r"^\s*-\s", line):          # tags 列表项
            if not isinstance(fm.get("tags"), list):
                fm["tags"] = [] if not fm.get("tags") else [fm["tags"]]
            fm["tags"].append(line.strip("- ").strip())
        elif ":" in line:
            k, v = line.split(":", 1)
            fm[k.strip()] = v.strip().strip('"')
    return fm, md[m.end():]


def convert(body, video_id, absolute_images):
    """Markdown 正文 -> HTML 片段（语义化 article/section/figure）"""
    out, sec_open = [], False
    lines = body.splitlines()
    i = 0
    while i < len(lines):
        ln = lines[i]
        s = ln.strip()
        if not s:
            i += 1
            continue
        # 图片 + 图注（图注在下一非空行，以「原视频」开头）
        m = re.match(r"^!\[([^\]]*)\]\(([^)]+)\)$", s)
        if m:
            alt, src = m.group(1), m.group(2)
            if absolute_images:
                src = f"{SITE}/{video_id}/{src}"
            cap = ""
            j = i + 1
            while j < len(lines) and not lines[j].strip():
                j += 1
            if j < len(lines) and lines[j].strip().startswith("原视频"):
                cap = lines[j].strip()
                i = j
            fig = f'<figure><img src="{esc(src)}" alt="{esc(alt)}" loading="lazy">'
            if cap:
                fig += f"<figcaption>{inline(cap)}</figcaption>"
            fig += "</figure>"
            out.append(fig)
            i += 1
            continue
        # H1（标题已在 header 里，正文跳过）
        if s.startswith("# "):
            i += 1
            continue
        # 标题
        if s.startswith("### "):
            if not sec_open:
                out.append("<section>")
                sec_open = True
            out.append(f"<h3>{inline(s[4:])}</h3>")
            i += 1
            continue
        if s.startswith("## "):
            if sec_open:
                out.append("</section>")
            out.append("<section>")
            sec_open = True
            out.append(f"<h2>{inline(s[3:])}</h2>")
            i += 1
            continue
        # 表格
        if s.startswith("|"):
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                rows.append([c.strip() for c in lines[i].strip().strip("|").split("|")])
                i += 1
            head, data = rows[0], [r for r in rows[2:]]
            t = ["<table><thead><tr>"] + [f"<th>{inline(c)}</th>" for c in head] + ["</tr></thead><tbody>"]
            for r in data:
                t.append("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in r) + "</tr>")
            t.append("</tbody></table>")
            out.append("".join(t))
            continue
        # 引用
        if s.startswith("> "):
            buf = []
            while i < len(lines) and lines[i].strip().startswith(">"):
                buf.append(lines[i].strip().lstrip(">").strip())
                i += 1
            out.append("<blockquote><p>" + "<br>".join(inline(b) for b in buf) + "</p></blockquote>")
            continue
        # 列表
        if re.match(r"^([-*]|\d+\.)\s", s):
            ordered = bool(re.match(r"^\d+\.\s", s))
            tag = "ol" if ordered else "ul"
            items = []
            while i < len(lines) and re.match(r"^([-*]|\d+\.)\s", lines[i].strip()):
                items.append(re.sub(r"^([-*]|\d+\.)\s+", "", lines[i].strip()))
                i += 1
            out.append(f"<{tag}>" + "".join(f"<li>{inline(x)}</li>" for x in items) + f"</{tag}>")
            continue
        # 普通段落（合并连续行）
        buf = [s]
        i += 1
        while i < len(lines) and lines[i].strip() and not re.match(r"^(#|!\[|>|\||[-*]\s|\d+\.\s)", lines[i].strip()):
            buf.append(lines[i].strip())
            i += 1
        text = " ".join(buf)
        cls = ' class="srcline"' if text.startswith("来源：") else ""
        out.append(f"<p{cls}>{inline(text)}</p>")
    if sec_open:
        out.append("</section>")
    return "".join(out)


def page(title, subtitle, body_html, meta_bits, full):
    """full=True 出带样式的 index.html；False 出精简 cubox.html"""
    css = f"<style>{CSS}</style>" if full else ""
    head_extra = ""
    if not full:
        head_extra = ""  # Cubox 版保持精简，只要语义结构
    meta = "".join(f"<span>{esc(b)}</span>" for b in meta_bits)
    cover = f'<p class="subtitle">{esc(subtitle)}</p>' if subtitle else ""
    if full:
        return (f'<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">'
                f'<meta name="viewport" content="width=device-width,initial-scale=1">'
                f'<title>{esc(title)}</title><meta name="author" content="{esc(meta_bits[0] if meta_bits else "")}">'
                f'<meta property="og:type" content="article"><meta property="og:title" content="{esc(title)}">'
                f"{css}</head><body><header><div class=\"eyebrow\">视频图文阅读稿</div>"
                f"<h1>{esc(title)}</h1>{cover}<div class=\"metadata\">{meta}</div></header>"
                f"<main><article>{body_html}</article></main></body></html>")
    return (f'<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>{esc(title)}</title><meta name="author" content="{esc(meta_bits[0] if meta_bits else "")}">'
            f'<meta property="og:type" content="article"><meta property="og:title" content="{esc(title)}">'
            f"{css}</head><body><main><article><header><h1>{esc(title)}</h1>"
            f"<p>{' · '.join(esc(b) for b in meta_bits)}</p></header>{body_html}</article></main></body></html>")


def slim(html):
    """Cubox 抓取版必须扁平化：它按 <section>/<figure>/<h3> 分块打分，只挑一段当中段正文，
    会把其余章节整段丢掉（2601005 实测：江浙沪 6714 字只抓到 1862 字、ETF 砍掉一半）。
    去掉 section 包裹、图改成普通段落、h3 降级为加粗段落，即可全文抓取。"""
    html = re.sub(r'<figure><img ([^>]*)><figcaption>(.*?)</figcaption></figure>',
                  r'<p><img \1></p>\n<p class="cap">\2</p>', html, flags=re.S)
    html = re.sub(r'<figure><img ([^>]*)></figure>', r'<p><img \1></p>', html, flags=re.S)
    html = html.replace("<section>", "").replace("</section>", "")
    html = re.sub(r"<h3>(.*?)</h3>", r"<p><strong>\1</strong></p>", html, flags=re.S)
    html = html.replace("<header>", "").replace("</header>", "")
    return html


def build(src_dir):
    mds = [f for f in os.listdir(src_dir) if f.endswith(".md")]
    if not mds:
        print(f"✗ {src_dir}: 无 .md")
        return None
    md = open(os.path.join(src_dir, mds[0]), encoding="utf-8").read()
    fm, body = parse_front(md)
    video_id = fm.get("video_id", "").strip('"')
    if not video_id:
        print(f"✗ {src_dir}: frontmatter 缺 video_id")
        return None
    title = ""
    m = re.search(r"^# (.+)$", body, re.M)
    if m:
        title = m.group(1).strip()
    # 副标题 = 标题后第一段（导读前的斜体说明行）
    sub = ""
    lines = body.splitlines()
    for idx, ln in enumerate(lines):
        if ln.startswith("# "):
            for j in range(idx + 1, min(idx + 6, len(lines))):
                if lines[j].strip():
                    sub = lines[j].strip()
                    break
            break
    out_dir = os.path.join(REPO_DIR, video_id)
    os.makedirs(out_dir, exist_ok=True)
    # 资源
    shutil.rmtree(os.path.join(out_dir, "assets"), ignore_errors=True)
    shutil.copytree(os.path.join(src_dir, "assets"), os.path.join(out_dir, "assets"))
    for f in ("text.txt", "subtitle.srt"):
        p = os.path.join(src_dir, f)
        if os.path.isfile(p):
            shutil.copy2(p, os.path.join(out_dir, f))
    # 元信息行
    duration = fm.get("duration", "").strip('"')
    author = fm.get("author", "")
    source = fm.get("source", "")
    meta_bits = [author, f"视频时长 {duration}", "完整图文阅读稿"]
    if source:
        meta_bits.append(f"原视频 {source}")
    i_html = page(title, sub, convert(body, video_id, False), meta_bits, True)
    c_html = slim(page(title, sub, convert(body, video_id, True), meta_bits, False))
    open(os.path.join(out_dir, "index.html"), "w", encoding="utf-8").write(i_html)
    open(os.path.join(out_dir, "cubox.html"), "w", encoding="utf-8").write(c_html)
    n_img = len(re.findall(r"<img ", c_html))
    print(f"✓ {video_id}  {title[:32]}  {len(c_html)//1024}KB  {n_img}图")
    return {"video_id": video_id, "title": title, "author": author}


if __name__ == "__main__":
    built = []
    for d in sys.argv[1:]:
        r = build(d)
        if r:
            built.append(r)
    # 重建仓库首页索引
    idx = ['<!doctype html><html lang="zh-CN"><meta charset="utf-8">',
           '<meta name="viewport" content="width=device-width,initial-scale=1">',
           "<title>视频图文阅读稿</title><style>body{font-family:-apple-system,'PingFang SC',sans-serif;max-width:760px;margin:60px auto;padding:0 20px;line-height:1.9;color:#1e2d38}a{color:#176e68}li{margin:8px 0}</style>",
           "<h1>视频图文阅读稿</h1><ul>"]
    for sub in sorted(os.listdir(REPO_DIR)):
        p = os.path.join(REPO_DIR, sub, "index.html")
        if os.path.isfile(p):
            t = re.search(r"<title>(.*?)</title>", open(p, encoding="utf-8").read())
            idx.append(f'<li><a href="{sub}/">{t.group(1) if t else sub}</a></li>')
    idx.append("</ul></body></html>")
    open(os.path.join(REPO_DIR, "index.html"), "w", encoding="utf-8").write("\n".join(idx))
    print(f"\n共 {len(built)} 篇；仓库首页已更新")
