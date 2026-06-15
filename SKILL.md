---
name: psych-news-digest
description: >-
  抓取美国精神病学会 (APA) Psychiatric News / News Releases 的最近 7 天精神科资讯，
  智能翻译为中文，整理成图标美化、含标题/摘要/源链接的纯文本列表（不使用 Markdown 语法）。
  当用户提到「APA 精神科新闻」「Psychiatric News」「精神病学最新资讯/动态」
  「APA 官方新闻速递」「精神科行业新闻汇总」「精神科文献速递」「最近精神科新闻」等时触发。
---

# Psychiatric News (APA) 资讯速递

把美国精神病学会（APA）官方发布的最新精神科新闻，整理成一份图标美化、中文呈现的
纯文本列表，每条包含标题、中文摘要、源链接（裸 URL）。**输出不使用任何 Markdown 语法。**

## 数据源

- 主源：APA News Room — `https://www.psychiatry.org/News-room/News-Releases`
- 说明：`psychnews.psychiatryonline.org` 主站受 Cloudflare 拦截、官方 RSS 已停用，
  因此使用 APA News Releases 列表页（无 JS、结构稳定、可直接抓取）。

### 原文存档（渲染阶段 · 飞书云盘独立文档）

每条新闻在**渲染阶段**作为独立飞书云文档保存到 user 云盘根目录下的「心理精神科新闻日志」文件夹
（`lark-cli --as user` 写入,需 user 提前在云盘建好并提供 `folder_token`）。
- 命名：`YYYY-MM-DD_文章标题`（标题保留原文,不翻译,避免文件名字符不兼容）
- 内容：Markdown 化后的正文（标题 + 作者 + 发布时间 + 段落 + 引用 + 链接列表）
  - **必读 pitfall(2026-06-15 实测 bug)**:docx 内容**必须**用 `body_md` 字段(完整正文 Markdown,html2text 转换)写入,
    **不能用 `summary` 字段**(只有 1 段 meta description,200 字符,丢失 90% 内容)。
    `summary` 字段是给**消息模板**(中文摘要翻译)用的,**不是**给存档 docx 用的。
    误用 `summary` 写 docx 会导致"飞书文档内容和原文内容非常不一致"(用户原话反馈)。
- 触发顺序：渲染阶段,等 doc_url 拿到再统一拼装条目中的 `📄 飞书文档:` 行（不允许"生成中"占位）
- 空结果（7 天 0 条）不存空报告
- 完整 user 身份 workflow + folder_token 获取 + `drive +move` 调用见 sibling `sci-psychiatry-digest/references/feishu-doc-workflow.md` § user 身份 workflow
- lark-cli 实测 pitfall(`drive +search` 索引延迟、`--parent-token` 一次到位、
  `--recommend` 不给 `search:docs:read`、strict-mode 卡 auth login)见
  `references/lark-cli-pitfalls.md`

## 执行流程

0. **前置依赖**(首次跑或新机器部署时):
   ```bash
   pip install -r scripts/requirements.txt
   # 依赖:html2text(把 APA 详情页 HTML 转 Markdown,产出完整 body_md)
   ```
   缺这个包会 `ModuleNotFoundError: No module named 'html2text'`,脚本第 1 条直接报错。

1. **抓取**：运行脚本获取**最近 7 天**的新闻。
   ```bash
   python3 scripts/fetch_news.py            # 默认：最近 7 天（滚动窗口，含当天）
   python3 scripts/fetch_news.py 14         # 可选：最近 N 天（用户明确要更长跨度时）
   ```
   - 默认只返回最近 7 天发布的新闻，不限数量、按发布时间倒序。
   - 输出为 JSON 对象:`{ window, today, count, latest_available, items[] }`，
     每个 item 含 `title` / `url` / `date` / `summary` / **`body_md`(完整正文 Markdown) /
     `paragraphs` / `authors` / `location` / `extra_links`**(2026-06-15 增 extra_links,
     详见 `scripts/fetch_news.py` 顶部 docstring + `references/field-extraction-patterns.md`)。
   - 脚本已自动跳过西语重复稿、按 URL 去重，并对网络请求做 1 次重试。

2. **翻译**：将每条的 `title` 与 `summary` **智能翻译成简体中文**。
   - 标题：译为通顺、专业的中文短标题；专有名词（药名、期刊名、人名、机构名）
     可保留英文或采用通行中文译名。
   - 摘要：意译为 1–3 句通顺中文，准确传达原意，不要逐字硬译。
   - `url` / `date` **保持原样**，绝不翻译或改写链接。

3. **渲染**：严格按下方模板输出**纯文本列表**（保留图标，不使用 Markdown 语法）。

4. **空结果处理**：若 `count` 为 0（最近 7 天无发稿），**不要伪造内容**。这是**正常稳态**而非故障——
   - APA 的发稿节奏是「月初刊 1 篇『June 2026 Issues of APA Journals』期刊汇总 + 月中下旬 0-2 篇新闻」
   - 任何月份的 6-25 日抓 7 天窗, **常态就是 0 条**(实测多次)
   - **必须**告诉用户「最近 7 天 APA 暂无新发布, 最新一条发布于 `<date>`: `<title>`」+ 提示 `fetch_news.py 30` 看 30 天
   - **不要**误判为脚本/网站坏掉而启动 `web_search` fallback(`Step 5`)

5. **抓取失败降级**（仅当步骤 1 返回 `{"error": ...}`）：
   用 `web_search` 搜索 `site:psychiatry.org news releases` 补充，
   仍保留「标题 / 中文摘要 / 源链接」三要素与图标格式。

> 🔧 维护提示：若 APA 改版导致结果恒为 0，需更新脚本中的 class 选择器
> （`c-article-item` / `c-meta__date` / 文章正文）。各字段的 regex 库、命中率
> 天花板(83% authors / 33% extra_links 是设计上限,不是 bug)、典型盲区,
> 维护时优先看 `references/field-extraction-patterns.md`。

## 输出格式（必须严格遵守）

**纯文本输出,保留图标,禁止任何 Markdown 语法**:不得使用 `#` 标题、
`**加粗**`、`-`/`*` 列表符、`>` 引用、表格,以及 `[文字](链接)` 超链接语法。
链接一律以裸 URL 直接展示。条目之间用一行 `────────` 分隔。
图标语义固定:📰 标题 | 🗓️ 日期 | 📝 摘要 | 👥 作者 | 📍 地点 |
📄 飞书文档(原文存档的云文档链接) | 📑 期刊全文(若有,ajp.psychiatryonline.org 链接) |
🎬 视频摘要(若有,youtube 链接) | 🌐 西语版(若有,psychiatry.org 西语镜像) |
🔗 原文链接。

模板（原样照此风格输出）:

```text
🧠 APA 精神科资讯速递 · Psychiatric News
来源:美国精神病学会（APA）官方新闻室 | 最近 7 天（<window 区间>）| 共 N 条
────────
📰 1. 中文标题
🗓️ 日期：May 19, 2026
📝 摘要：中文摘要……
👥 作者：Allen Schatzberg, M.D.
📍 地点：San Francisco
📄 飞书文档:https://feishu.cn/docx/XXXX
🔗 原文:https://www.psychiatry.org/News-room/News-Releases/....
────────
📰 2. 中文标题
🗓️ 日期：……
📝 摘要：……
👥 作者：……
📍 地点：……
📄 飞书文档:https://feishu.cn/docx/YYYY
📑 期刊全文:https://ajp.psychiatryonline.org/toc/ajp/current
🎬 视频摘要:https://youtu.be/XeM_qfxEBrs
🌐 西语版:https://www.psychiatry.org/News-room/News-Releases/Nueva-investigacion-2026-TDAH
🔗 原文:https://....
```

**次级原文链接行(📑/🎬/🌐)渲染规则**:
- 📑 期刊全文:仅当 `extra_links` 里有 `type="journal"` 时输出
- 🎬 视频摘要:仅当 `extra_links` 里有 `type="youtube"` 时输出
- 🌐 西语版:仅当 `extra_links` 里有 `type="spanish"` 时输出
- 👥 作者:仅当 `authors` 非空时输出;空时跳过该行(避免出现"作者:无"的空架子)
- 📍 地点:仅当 `location` 非空时输出
- 三类次级链接可能同时出现(期刊汇总 = journal ×2 + youtube ×1),按 JSON 顺序渲染
- 渲染数据来源:见 `scripts/fetch_news.py` `fetch_full()` 步骤 3.5

## 📤 输出方式（飞书 · v3.4 默认云文档）

> 飞书写操作资源(文件夹/folder_token/搜/建/缓存)的标准流程见
> sibling **`sci-psychiatry-digest/references/feishu-doc-workflow.md`**
> (含 strict-mode 切换、auth login split-flow、`drive +create-folder`、
> `docs +create` + `drive +move`、反编造铁律等)。本 skill 不重复 lark-cli
> 安装/登录/缓存细节,仅引用其结论。

与 sibling skill `sci-psychiatry-digest` 保持一致（用户 2026-06-12 反馈"给我飞书文档"）:

- **默认:飞书云文档**(走 `lark-cli docs +create` + `block_insert_after` 分块追加,完整 workflow 见 sibling `sci-psychiatry-digest/references/feishu-doc-workflow.md`)
- **备选:飞书消息**(`send_message` 推到当前 chat,纯文本 + 图标 + ──── 分隔,无任何 Markdown 标记)
- **触发判断**:用户明示"飞书文档/云文档/docx"→ 走文档;明示"消息/对话气泡/不要文档"→ 走消息;**未明示默认走文档**(v3.4 翻转);cron 触发自动任务仍走消息
- **空结果(常态 0 条)**:框线化提示「最近 7 天 APA 暂无新发布」+ 给出 latest_available 链接 + 提示 `fetch_news.py 30` 跑 30 天

### 原文存档(user 云盘「心理精神科新闻日志」)

每条新闻的全文**同时**作为独立飞书云文档保存到 user 云盘根目录下的「心理精神科新闻日志」文件夹,
命名 `YYYY-MM-DD_文章标题`。条目渲染时插入 `📄 飞书文档:<doc_url>` 行(裸 URL),**云文档模式与消息模式都带这一行**。
完整 user 身份 workflow(auth login split-flow + folder_token 获取 + `drive +move` + 反编造铁律)见 sibling `sci-psychiatry-digest/references/feishu-doc-workflow.md` § user 身份 workflow。

## 硬性规则

- 链接以**裸 URL**形式展示（直接粘贴 `url`），不得用 Markdown 超链接语法。
- 整段输出**不含任何 Markdown 标记**，仅纯文本 + 图标 + 分隔线。
- **默认只取最近 7 天**；用户若明确要更长跨度（如「最近两周」），把天数作为脚本参数。
- 输出语言：中文（标题、摘要均翻译；链接与日期保持原文）。
- 不做栏目分类，按发布时间倒序平铺。
- 全程多用图标提升可读性，但保持上方约定的图标语义一致，不要滥用花哨表情。

### 渲染阶段铁律(2026-06-15 新增)

- **`📄 飞书文档:` 行必须等 doc_url 到位再统一拼装**,绝不允许出现"生成中"占位、临时 stub、或"详见飞书"等模糊文本
- **整条延后渲染(z 方案)**:doc_url 全部拿齐 → 一次性渲染所有条目 → 单一最终输出(不要中途输出"3/5 已完成"这种半成品)
- 失败兜底:某一条 docx 创建失败 → 该条不渲染 `📄 飞书文档:` 行,保留其他行 + 末尾汇总 `⚠️ N 条存档失败:<url>`,不要伪造 doc_url
