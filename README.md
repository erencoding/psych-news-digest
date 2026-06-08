# 🧠 psych-news-digest

> Hermes Agent skill · 美国精神病学会 (APA) 精神科资讯每日速递（中文版）

抓取 [APA News Releases](https://www.psychiatry.org/News-room/News-Releases) 最近 7 天的新闻发布，整理成图标美化、含标题/摘要/源链接的结构化中文 Markdown 列表。

## 触发场景

- 「APA 精神科新闻」「Psychiatric News」
- 「精神病学最新资讯 / 动态」
- 「APA 官方新闻速递」「精神科行业新闻汇总」
- 「精神科文献速递」「最近精神科新闻」

## 数据源

| 来源 | 用途 | 备注 |
|---|---|---|
| `psychiatry.org/News-room/News-Releases` | **主源**（本 skill 使用） | 静态 HTML、无 JS、可直接抓取 |
| `psychnews.psychiatryonline.org` | ~~旧主站~~ | Cloudflare 拦截 |
| 官方 RSS | ~~已停用~~ | 2024 年后无更新 |

## 工作流

```
┌────────────┐   ┌────────────┐   ┌────────────┐   ┌────────────┐
│  抓取 HTML │──▶│  解析+去重 │──▶│  7天窗口   │──▶│ 抓取摘要   │
│ (urllib)   │   │(regex+thread)│   │  过滤     │   │(并行,6线程)│
└────────────┘   └────────────┘   └────────────┘   └────────────┘
                                                            │
                                                            ▼
                       ┌────────────┐   ┌────────────┐
                       │  飞书 / 终端│◀──│  翻译+渲染 │
                       │  Markdown  │   │ (LLM 翻译) │
                       └────────────┘   └────────────┘
```

## 仓库结构

```
psych-news-digest/
├── README.md
├── SKILL.md              # Hermes skill 描述 + LLM 渲染指令
└── scripts/
    └── fetch_news.py     # 抓取 + 解析 + JSON 输出
```

## 用法

### 命令行（直跑脚本）

```bash
# 最近 7 天（默认）
python3 scripts/fetch_news.py

# 自定义窗口（1-60 天）
python3 scripts/fetch_news.py 14
```

输出 JSON：
```json
{
  "window": "last 7 days (2026-06-02 ~ 2026-06-08)",
  "today": "2026-06-08",
  "count": 5,
  "latest_available": {...},
  "items": [
    {
      "title": "...",
      "url": "https://www.psychiatry.org/...",
      "date": "Jun 3, 2026",
      "summary": "..."
    }
  ]
}
```

### 在 Hermes Agent 中

把仓库的 raw URL 写进 Hermes skill 索引，或直接放进 `~/.hermes/skills/psych-news-digest/`，LLM 会根据 `SKILL.md` 的 frontmatter 自动发现触发词并按指令渲染。

## 维护提示

- 解析器依赖的 CSS class：`c-article-item` / `c-meta__date` / `<meta name="description">`。
- **若 APA 改版导致 `count` 恒为 0**：先用浏览器 DevTools 抓新 HTML，对照更新 `scripts/fetch_news.py` 里的 regex（参见 SKILL.md 的"抓取失败降级"段）。
- 抓取会跳过西语重复稿（URL slug 含 `Nueva` / `Nuevo` / `Investigaci` / `Aviso`），并按 URL 去重。
- 网络请求 1 次重试 + 摘要抓取 6 线程并发。

## 许可

MIT
