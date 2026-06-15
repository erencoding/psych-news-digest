#!/usr/bin/env python3
"""
Fetch recent APA News Releases (Psychiatric News) -> structured JSON.

Source: https://www.psychiatry.org/News-room/News-Releases
(The official RSS was discontinued and psychnews.* is behind Cloudflare,
so we parse this stable, JS-free listing page.)

Default: releases from the LAST 7 DAYS (rolling, inclusive of today).
  fetch_news.py        -> last 7 days
  fetch_news.py 14     -> last 14 days (arg = N days, 1-60)

Output JSON: { window, today, count, latest_available, items[] }

Each item has these fields (all best-effort; failures yield empty defaults,
never raise):
  - date        : str              发布日期(原文,例 "May 18, 2026")
  - title       : str              标题(原文,英文)
  - url         : str              详情页 URL(psychiatry.org)
  - summary     : str              1 段简短摘要(meta description 优先,fallback 段落 1)
                                   → 给消息模板(中文摘要翻译后)用
  - body_md     : str              **完整正文** Markdown(html2text 转换)
                                   块引用/列表/小标题/链接/强调全保
                                   → 给飞书云文档存档用
  - paragraphs  : list[str]        从 body_md 切出的实质段落(>=40 字符,过滤导航/版权)
  - authors     : list[str]        作者列表(从"study authors include/included/are"
                                   或 dateline 兜底抓"FirstName LastName, M.D.")
  - location    : str              发布城市/机构地(从首段 dateline 抓 "San Francisco")
  - extra_links : list[dict]       次级原文链接(非 psychiatry.org 主页),按类型分组:
                                   [{"type": "journal"|"youtube"|"spanish", "url": ..., "label": ...}]
                                   - journal: ajp.psychiatryonline.org / ps.psychiatryonline.org
                                   - youtube: youtu.be / youtube.com 视频摘要
                                   - spanish: psychiatry.org 西语版镜像(Nueva-/TDAH/Español)

Maintenance: if APA redesigns the site and results drop to 0, update the
class selectors below (c-article-item / c-meta__date / article body).

Dependency: html2text (pip install html2text) — used in fetch_full() to
            convert article HTML to Markdown for the body_md field.
"""
import sys
import re
import json
import html
import time
import datetime
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor
import html2text

LIST_URL = "https://www.psychiatry.org/News-room/News-Releases"
BASE = "https://www.psychiatry.org"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")
MONTHS = {m: i for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june", "july",
     "august", "september", "october", "november", "december"], 1)}


def get(url, timeout=25, retries=1):
    """Fetch URL text with one retry + backoff; raises on final failure."""
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read().decode("utf-8", errors="ignore")
        except (urllib.error.URLError, OSError):
            if attempt == retries:
                raise
            time.sleep(1.5 * (attempt + 1))


def parse_date(s):
    """Locale-independent parse of 'May 19, 2026' -> date; None if invalid."""
    m = re.match(r'([A-Za-z]+)\s+(\d{1,2}),\s*(\d{4})', s.strip())
    if not m:
        return None
    mon = MONTHS.get(m.group(1).lower())
    if not mon:
        return None
    try:
        return datetime.date(int(m.group(3)), mon, int(m.group(2)))
    except ValueError:
        return None


def parse_listing(htm):
    """Yield {date,title,url} per release; de-dup by URL, drop Spanish variants."""
    items, seen = [], set()
    for block in re.findall(r'<article class="c-article-item".*?</article>', htm, re.S):
        a = re.search(r'<h2[^>]*>\s*<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>', block, re.S)
        if not a:
            continue
        href = a.group(1)
        url = href if href.startswith("http") else BASE + href
        # De-dup + skip Spanish releases (URL slug carries 'Nueva'/'Investigacion').
        if url in seen or re.search(r'(Nueva|Nuevo|Investigaci|Aviso)', href, re.I):
            continue
        seen.add(url)
        title = html.unescape(re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', '', a.group(2)))).strip()
        d = re.search(r'c-meta__date[^>]*>([^<]+)<', block)
        items.append({"date": d.group(1).strip() if d else "", "title": title, "url": url})
    return items


def fetch_full(item):
    """Attach full article body + structured fields.

    Fields added to item (all best-effort, failure = empty/default, never raises):
      - summary    : str  (kept for back-compat; 1 段 meta description or first paragraphs)
      - body_md    : str  (整段 Markdown,html2text 转换,块引用/列表/小标题/链接/强调全保)
      - paragraphs : list[str]  (从 body_md 按空行切,只留 >=40 字符的实质段落)
      - authors    : list[str]  (从正文 "The study authors include ..." 解析;空=未解析到)
      - location   : str        (首段 dateline, "San Francisco — ..." → "San Francisco";空=未抓到)
      - extra_links: list[dict] (次级原文链接,非 psychiatry.org 主页:
                                  type=journal/youtube/spanish, url, label)
    """
    try:
        h = get(item["url"])
    except Exception as e:
        item["summary"] = ""
        item["body_md"] = ""
        item["paragraphs"] = []
        item["authors"] = []
        item["location"] = ""
        item["extra_links"] = []
        item["_error"] = str(e)
        return item

    # 1) summary 字段(给消息模板用,1 段):meta description 优先,否则 body_md 第一段
    md = re.search(r'<meta name="description" content="([^"]*)"', h)
    if md and md.group(1).strip():
        item["summary"] = html.unescape(md.group(1)).strip()
    else:
        item["summary"] = ""  # body_md 计算后再回填

    # 2) 抽 <article> 块(没有就 fallback 到全文,但要去掉 header/footer/aside/nav)
    article = re.search(r'<article[^>]*>(.*?)</article>', h, re.S)
    if article:
        body_html = article.group(1)
    else:
        # fallback:去掉常见非正文块
        body_html = h
        for tag in ('header', 'footer', 'nav', 'aside', 'script', 'style'):
            body_html = re.sub(rf'<{tag}[^>]*>.*?</{tag}>', '', body_html, flags=re.S)

    # 3) html2text 转 Markdown
    h2t = html2text.HTML2Text()
    h2t.body_width = 0           # 不自动换行(避免破坏链接)
    h2t.ignore_links = False     # 保留链接
    h2t.ignore_images = True     # 图片不抓
    h2t.ignore_emphasis = False  # 保留加粗/斜体
    h2t.bypass_tables = False    # 表格转 Markdown 表
    item["body_md"] = h2t.handle(body_html).strip()

    # 3.5) 抽次级原文链接(非 psychiatry.org 主页之外的延伸链接)
    #      三类:journal(ajp.psychiatryonline.org / ps.psychiatryonline.org toc 或 article)
    #            youtube(视频摘要)
    #            spanish(西语版镜像,host 仍是 psychiatry.org → 必须先在分类里特判)
    #      SKILL.md 模板中,📑/🎬/🌐 行只在该类型 extra_links 非空时才渲染(空则跳过该行)
    item["extra_links"] = []
    seen_urls = set()
    # 抽 [label](url) 形式 + 裸 URL 形式
    link_pattern = re.compile(
        r'\[([^\]]+)\]\((https?://[^\s)]+)\)|(https?://[^\s)\]]+)', re.I
    )
    for m in link_pattern.finditer(item["body_md"]):
        if m.group(2):
            label, url = m.group(1).strip(), m.group(2).strip()
        else:
            url, label = m.group(3).strip(), ""
        if url in seen_urls:
            continue
        # 分类优先:spanish(西语版)→ journal(期刊)→ youtube(视频)→ 否则跳过
        if re.search(r'psychiatry\.org/.*?(Nueva|Nuevo|Investigaci|TDAH|Espa[ñn]ol)', url, re.I):
            type_ = "spanish"
        elif re.search(r'(ajp|ps)\.psychiatryonline\.org', url, re.I):
            type_ = "journal"
        elif re.search(r'youtu\.?be', url, re.I):
            type_ = "youtube"
        elif "psychiatry.org" in url:
            continue  # 主页/其他 psychiatry.org 页(非 journal/spanish)跳过
        else:
            continue  # facebook/twitter 等外部站跳过
        seen_urls.add(url)
        item["extra_links"].append({"type": type_, "url": url, "label": label[:50]})
        if len(item["extra_links"]) >= 5:  # 上限 5 条
            break

    # 4) 切 paragraphs(按空行,过滤 < 40 字符的短段)
    raw_paras = re.split(r'\n\s*\n', item["body_md"])
    paras = []
    for p in raw_paras:
        p = p.strip()
        if not p:
            continue
        # 去掉纯 Markdown 链接块、引用符号(> 开头)、列表前缀
        p_clean = re.sub(r'^[\s>*\-\d.]+', '', p, flags=re.M)
        p_clean = p_clean.strip()
        if len(p_clean) >= 40:
            paras.append(p)
    item["paragraphs"] = paras

    # 5) summary fallback:body_md 第一个实质段落
    if not item["summary"] and item["paragraphs"]:
        item["summary"] = item["paragraphs"][0][:400]

    # 6) location:首段 dateline,兼容 "City, ST --" / "**City, ST**" / "City, ST —"
    #    paragraphs[0] 通常是 H1 标题,跳过;从 paragraphs[1] 开始找 dateline
    #    去掉段落中所有 markdown 强调符 ** _ * > 避免干扰
    item["location"] = ""
    candidates = item["paragraphs"][1:4] if len(item["paragraphs"]) > 1 else item["paragraphs"]
    for p in candidates:
        # 去掉段落中所有 ** _ * > 等 markdown 强调符
        first_clean = re.sub(r'[\s>*_`*]+', ' ', p).strip()
        m = re.match(r'^([A-Z][A-Za-z\s,.\']+?)\s*[—\-]{1,2}\s+', first_clean)
        if m:
            item["location"] = m.group(1).strip().strip('*').strip()
            break

    # 7) authors:从正文匹配 "study authors include/included/are A, B, C, and D"
    #    两步法:先定位起点,再截到下个句号
    authors = []
    m = re.search(
        r'(?i)(?:study\s+authors?\s+(?:include|included|are)|authors?\s+(?:include|included|are))\s+',
        item["body_md"],
    )
    if m:
        start = m.end()
        rest = item["body_md"][start:]
        # author_str 通常在一行内(APA 模板:"...Mark Zimmerman, M.D., and Daniel M. Mackin, M.A., of <机构>...")
        # 截到 ", of" (机构引介词) OR 句末 OR 换行 — 避免截到缩写 M.D./中间名 M. 里的点
        nl = rest.find('\n')
        first_line = rest[:nl] if nl > 0 else rest
        # 优先: 截到 ", of" 之前
        m2 = re.search(r',\s+of\s+[A-Z]', first_line)
        if m2:
            author_str = first_line[:m2.start()].strip()
        else:
            # 兜底: 句号 + 空格 + 大写字母(非缩写)
            m3 = re.search(r'\.\s+[A-Z][a-z\u00C0-\u017F]', first_line)
            if m3:
                author_str = first_line[:m3.start()].strip()
            else:
                author_str = first_line.strip()
        # 拆 ", and " / ", " / "; " (APA 有时用 ; 分作者)
        parts = re.split(r',\s*and\s+|\s*[,;]\s+', author_str)
        for p in parts:
            p = p.strip().rstrip(',').rstrip(';').strip()
            # 去掉 "and " / "or " 前缀
            p = re.sub(r'^(?:and|or)\s+', '', p)
            # 严苛:首字符大写、长度 8-60、至少 2 个单词 (FirstName LastName)
            words = p.split()
            if (
                8 <= len(p) <= 60
                and p[0].isupper()
                and len(words) >= 2
                and all(w[0].isupper() for w in words)
                and not p.endswith('.')  # 排除单独的 "M.D." / "Ph.D."
            ):
                authors.append(p)
    item["authors"] = authors

    # 8) dateline 兜底:研究型文章没 "study authors include" 时,试从 dateline 段抓
    #    适用于人物公告类(例:"Mark Rapaport, M.D., began his...")
    #    或文末"XX, M.D., of <institution>" 形式
    if not authors:
        for p in item["paragraphs"][:3]:
            # 匹配 "FirstName LastName, M.D." 形式(dateline 开头)
            m3 = re.search(
                r'([A-Z][a-z\u00C0-\u017F\'\-]+(?:\s+[A-Z]\.?)?\s+[A-Z][a-z\u00C0-\u017F\'\-]+),?\s*(?:M\.D\.|Ph\.D\.|M\.A\.|M\.S\.|Psy\.D\.|R\.N\.|Dr\.)',
                p,
            )
            if m3:
                name = m3.group(1).strip()
                # 过滤太短或太通用("The American" 等)
                if 8 <= len(name) <= 50 and name not in ("The American", "American Psychiatric"):
                    authors.append(name)
                    break
    item["authors"] = authors

    # 9) senior/lead/corresponding author 模式:APA 故意不公布所有作者时,
    #    引用句常形如 "according to senior author Allen Schatzberg, M.D., of Stanford"
    #    / "said X, M.D., senior author" / "lead author Y, Ph.D., of ..."
    #    只在 authors 还空时补 1 条(避免重复)
    if not item["authors"]:
        for p in item["paragraphs"][:6]:  # 范围扩到 6 段(引用句可能在更后)
            # 顺序尝试 3 种模式
            patterns = [
                # "according to senior author Name, M.D." / "lead author Name, Ph.D."
                r'(?i)(?:according\s+to\s+)?(?:senior|lead|corresponding)\s+author\s+([A-Z][a-z\u00C0-\u017F\'\-]+(?:\s+[A-Z]\.?)?\s+[A-Z][a-z\u00C0-\u017F\'\-]+)',
                # "Name, M.D., senior author" / "Name, Ph.D., lead author"
                r'([A-Z][a-z\u00C0-\u017F\'\-]+(?:\s+[A-Z]\.?)?\s+[A-Z][a-z\u00C0-\u017F\'\-]+),?\s*(?:M\.D\.|Ph\.D\.|M\.A\.|M\.S\.|Psy\.D\.),?\s+(?:senior|lead|corresponding)\s+author',
                # "said Name, M.D.," 形式(无显式 senior/lead 标志,只在第一段兜底)
                r'(?i)(?:said|according\s+to)\s+([A-Z][a-z\u00C0-\u017F\'\-]+(?:\s+[A-Z]\.?)?\s+[A-Z][a-z\u00C0-\u017F\'\-]+),?\s*(?:M\.D\.|Ph\.D\.|M\.A\.)',
            ]
            for pat in patterns:
                m_sa = re.search(pat, p)
                if m_sa:
                    name = m_sa.group(1).strip()
                    # 严苛过滤:首大写、长度合理、非通用词
                    if (8 <= len(name) <= 50
                            and name not in ("The American", "American Psychiatric", "Senior Author")
                            and len(name.split()) >= 2):
                        item["authors"] = [name]
                        break
            if item["authors"]:
                break
    return item


def main():
    today = datetime.date.today()
    days = 7
    if len(sys.argv) > 1 and sys.argv[1].strip().isdigit():
        days = max(1, min(60, int(sys.argv[1].strip())))

    try:
        listing = parse_listing(get(LIST_URL))
    except Exception as e:
        print(json.dumps({"error": f"fetch listing failed: {e}"}))
        sys.exit(1)

    dated = [(parse_date(x["date"]), x) for x in listing]
    dated = [(d, x) for d, x in dated if d]                 # keep parseable dates
    latest = max(dated, key=lambda t: t[0]) if dated else None

    cutoff = today - datetime.timedelta(days=days - 1)
    picks = [x for d, x in dated if cutoff <= d <= today]
    with ThreadPoolExecutor(max_workers=6) as ex:
        selected = list(ex.map(fetch_full, picks))

    print(json.dumps({
        "window": f"last {days} days ({cutoff.isoformat()} ~ {today.isoformat()})",
        "today": today.isoformat(),
        "count": len(selected),
        "latest_available": ({"date": latest[1]["date"], "title": latest[1]["title"],
                              "url": latest[1]["url"]} if latest else None),
        "items": selected,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
