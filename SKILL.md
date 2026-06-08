---
name: psych-news-digest
description: >-
  抓取美国精神病学会 (APA) Psychiatric News / News Releases 的**最近 7 天**精神科资讯，
  智能翻译为中文，整理成图标美化、含标题/摘要/源链接（超链接）的结构化 Markdown 列表。
  当用户提到「APA 精神科新闻」「Psychiatric News」「精神病学最新资讯/动态」
  「APA 官方新闻速递」「精神科行业新闻汇总」「精神科文献速递」「最近精神科新闻」等时触发。
---

# Psychiatric News (APA) 资讯速递

把美国精神病学会（APA）官方发布的最新精神科新闻，整理成一份**图标美化、中文呈现**的
Markdown 列表，每条包含**标题（超链接）、中文摘要、源链接**。

## 数据源

- 主源：APA News Room — `https://www.psychiatry.org/News-room/News-Releases`
- 说明：`psychnews.psychiatryonline.org` 主站受 Cloudflare 拦截、官方 RSS 已停用，
  因此使用 APA News Releases 列表页（无 JS、结构稳定、可直接抓取）。

## 执行流程

1. **抓取**：运行脚本获取**最近 7 天**的新闻。
   ```bash
   python3 scripts/fetch_news.py            # 默认：最近 7 天（滚动窗口，含当天）
   python3 scripts/fetch_news.py 14         # 可选：最近 N 天（用户明确要更长跨度时）
   ```
   - 默认只返回最近 7 天发布的新闻，不限数量、按发布时间倒序。
   - 输出为 JSON 对象：`{ window, today, count, latest_available, items[] }`，
     每个 item 含 `title` / `url` / `date` / `summary`。
   - 脚本已自动跳过西语重复稿、按 URL 去重，并对网络请求做 1 次重试。

2. **翻译**：将每条的 `title` 与 `summary` **智能翻译成简体中文**。
   - 标题：译为通顺、专业的中文短标题；专有名词（药名、期刊名、人名、机构名）
     可保留英文或采用通行中文译名。
   - 摘要：意译为 1–3 句通顺中文，准确传达原意，不要逐字硬译。
   - `url` / `date` **保持原样**，绝不翻译或改写链接。

3. **渲染**：严格按下方模板输出 Markdown 列表。

4. **空结果处理**：若 `count` 为 0（最近 7 天无发稿），不要伪造内容。
   读取 `latest_available`，告知用户「最近 7 天 APA 暂无新发布，最新一条发布于
   <date>：<title>」，并提示可用 `fetch_news.py 30` 查看更早内容。

5. **抓取失败降级**（仅当步骤 1 返回 `{"error": ...}`）：
   用 `web_search` 搜索 `site:psychiatry.org news releases` 补充，
   仍保留「标题 / 中文摘要 / 源链接」三要素与图标格式。

> 🔧 维护提示：若 APA 改版导致结果恒为 0，需更新脚本中的 class 选择器
> （`c-article-item` / `c-meta__date` / 文章正文）。

## 输出格式（必须严格遵守）

整体以一个主题标题开头，每条新闻为一个二级条目，条目之间用 `---` 分隔。
图标语义固定：📰 标题 ｜ 🗓️ 日期 ｜ 📝 摘要 ｜ 🔗 原文链接。

模板：

```markdown
## 🧠 APA 精神科资讯速递 · Psychiatric News

> 来源：美国精神病学会（APA）官方新闻室 ｜ 最近 7 天（<window 区间>）｜ 共 N 条

---

### 📰 1. [中文标题](原文URL)

🗓️ **日期**：May 19, 2026
📝 **摘要**：中文摘要……
🔗 **原文**：[阅读原文](原文URL)
```

## 硬性规则

- 标题与「阅读原文」都必须是可点击的 Markdown 超链接，指向脚本返回的真实 `url`。
- **默认只取最近 7 天**；用户若明确要更长跨度（如「最近两周」），把天数作为脚本参数。
- 输出语言：中文（标题、摘要均翻译；链接与日期保持原文）。
- 不做栏目分类，按发布时间倒序平铺。
- 全程多用图标提升可读性，但保持上方约定的图标语义一致，不要滥用花哨表情。
