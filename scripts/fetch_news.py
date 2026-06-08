#!/usr/bin/env python3
"""Fetch recent APA News Releases (Psychiatric News) -> structured JSON.

Source: https://www.psychiatry.org/News-room/News-Releases
(The official RSS was discontinued and psychnews.* is behind Cloudflare,
so we parse this stable, JS-free listing page.)

Default: releases from the LAST 7 DAYS (rolling, inclusive of today).
  fetch_news.py        -> last 7 days
  fetch_news.py 14     -> last 14 days (arg = N days, 1-60)

Output JSON: { window, today, count, latest_available, items[] }
each item: { title, url, date, summary }

Maintenance: if APA redesigns the site and results drop to 0, update the
class selectors below (c-article-item / c-meta__date / article body).
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


def fetch_summary(item):
    """Attach a clean summary: prefer <meta description>, else first paragraphs."""
    try:
        h = get(item["url"])
        md = re.search(r'<meta name="description" content="([^"]*)"', h)
        if md and md.group(1).strip():
            item["summary"] = html.unescape(md.group(1)).strip()
        else:
            paras = re.findall(r'<p[^>]*>(.*?)</p>', h, re.S)[:3]
            txt = " ".join(re.sub(r'<[^>]+>', '', p) for p in paras)
            item["summary"] = html.unescape(re.sub(r'\s+', ' ', txt)).strip()[:400]
    except Exception as e:
        item["summary"] = ""
        item["_error"] = str(e)
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
        selected = list(ex.map(fetch_summary, picks))

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
