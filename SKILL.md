---
name: psych-news-digest
description: >-
  抓取美国精神病学会 (APA) Psychiatric News / News Releases 的最近 7 天精神科资讯，
  智能翻译为中文，整理成图标美化、含标题/摘要/源链接的纯文本列表（不使用 Markdown 语法）。
  当用户提到「APA 精神科新闻」「Psychiatric News」「精神病学最新资讯/动态」
  「APA 官方新闻速递」「精神科行业新闻汇总」「精神科文献速递」「最近精神科新闻」等时触发。
---

# Psychiatric News (APA) 资讯速递

把美国精神病学会(APA)官方发布的最新精神科新闻,整理成一份图标美化、中文呈现的
纯文本列表。**输出不使用任何 Markdown 语法,链接以裸 URL 展示。**

## 环境前置条件(首次跑前自查)

| 组件 | 用途 | 安装/验证 |
|---|---|---|
| **Python 3 + `html2text`** | `scripts/fetch_news.py` 依赖 | `pip install -r scripts/requirements.txt` |
| **外网访问 `psychiatry.org`** | 抓取 News Releases 列表 + 各 release 全文 | 测试:`curl -sI https://www.psychiatry.org/News-room/News-Releases` 返 200 |
| **(可选) `lark-cli` v1.0.53+** | step 4 写飞书云文档 | `which lark-cli && lark-cli --version` |
| **(可选) Feishu user OAuth** | 写到自己云盘文件夹 | `lark-cli auth status` 看 user 身份 ready + openId |

**降级矩阵**:

| 环境 | 能做什么 | 不能做什么 |
|---|---|---|
| 全功能(本机)| 抓 + 翻译 + 写飞书云文档 + 推消息 | — |
| 仅有 Python | 抓 + 翻译 | 不能写云文档;step 4 自动降级为输出 `psychiatry.org` 原文链接 |
| 仅有 Python + 无外网 | 不能抓(`fetch_news.py` 必失败) | step 6 web_search fallback 仅当外网时可用 |
| 有 lark-cli 但 user 未授权 | 抓 + 翻译 | 不能写 user 云盘;只能走 bot 云盘(需 user 手动加协作者) |

## 数据源

- 主源:`https://www.psychiatry.org/News-room/News-Releases`
- 备份:`psychnews.psychiatryonline.org` 受 Cloudflare 拦截、官方 RSS 已停用,故用列表页

## 执行流程

**0. 前置依赖**(首次跑时):
```bash
pip install -r scripts/requirements.txt   # html2text
```

**1. 抓取**:
```bash
python3 scripts/fetch_news.py [N]   # N = 天数,默认 7(1-60)
```
输出 JSON: `{ window, today, count, latest_available, items[] }`,
每个 item 含 8 字段:`date` / `title` / `url` / `summary` / **`body_md` 完整正文 Markdown** /
`paragraphs` / `authors` / `location` / `extra_links`(详见 `references/field-extraction-patterns.md`)。

**2. 翻译**:`title` + `summary` 译为简体中文(机构名给中英对照,术语/药名/期刊名可保留英文)。
`url` / `date` **不翻译**。

**3. 渲染**:严格按下方图标语义,纯文本输出,条目间用 `────────` 分隔。

**4. 原文存档(可选)**:每条 `body_md` 写入 user 云盘「心理精神科新闻日志」文件夹
(默认 folder_name;**可被调用方覆盖** — 任何 skill 调用方在 prompt 里说"用 XX 文件夹"就该用 XX)。
`lark-cli docs +create --parent-token <folder_token>` 一步到位(umbrella skill §6.2 α 走法;
**避免** `+create` + `+move --type docx` 两步走)。
docx content 必须含 `<title>...</title>` 标签(v2 markdown 格式要求)+ `# 标题` + 元信息 + 英文全文 +
**中文全文翻译章节**。完整 user 身份 workflow + folder_token + 反编造铁律见 class-level umbrella
**`productivity/feishu-docx-workflow`**(lark-cli v1.0.53 实测:`--type docx` 必带、
`@<file>` 必须是 cwd 相对路径、`<title>` XML 标签、search-or-create-and-cache)。
lark-cli pitfall(索引延迟、auth login split-flow、strict-mode 卡登录)见 `references/lark-cli-pitfalls.md`。

**4.5 body_md 全文中文翻译**(2026-06-16 实战引入):
- 翻译时**严格保留 markdown 结构**:`#` / `**` / `*` / `[text](url)` / `<email>` / URL 完全不动,只翻译文本内容
- 链接 label 可译(`[The American Journal of Psychiatry]` → `[美国精神病学杂志 (The American Journal of Psychiatry)]`)
- 药名/期刊名/机构名给中英对照(`buprenorphine(丁丙诺啡)` / `AJP(美国精神病学杂志)`)
- 推荐用 `delegate_task` subagent 跑翻译(隔离上下文,主 agent 不被 6 条 ~3KB body_md 撑爆),子 agent 写 `/tmp/pnd-translations.json`,主 agent 读 JSON 后 `build_content()` 拼装 docx
- 翻译结果存 docx 末尾独立 `## 📝 全文中文翻译 / Chinese Translation` 章节(不是替换英文原文)
- 翻译质量用主对话同模型即可(MiniMax-M3 / Claude 都行),无需外部翻译 API

**5. 空结果**(常态,7 天 0 命中 ≠ 故障):提示「最近 7 天 APA 暂无新发布,最新一条发布于
`<date>`: `<title>`」+ `fetch_news.py 30` 跑 30 天。**不要**误判为抓取失败而启动 `web_search` fallback。
**实测 baseline**(2026-06-16):7 天 0 命中 / 30 天 6 条 / latest = June 01, 2026。
夏季 APA 发文低谷,7 天 0 命中是常态,持续 ≥3 天再考虑维护选择器(见下)。

**6. 抓取失败降级**(仅步骤 1 返回 `{"error": ...}`):`web_search site:psychiatry.org news releases` 补,
仍保留「标题 / 中文摘要 / 源链接」三要素 + 图标。

|> 🔧 维护:APA 改版 0 命中持续 3 天 → 更新 `scripts/fetch_news.py` class 选择器
|> (`c-article-item` / `c-meta__date` / `<article>` 块)。字段正则维护见 `references/field-extraction-patterns.md` § 维护清单。

## 输出格式

图标语义固定:📰 标题 | 🗓️ 日期 | 📝 摘要 | 👥 作者 | 📍 地点 |
📄 飞书文档(原文存档) | 📑 期刊全文(若有) | 🎬 视频摘要(若有) | 🌐 西语版(若有) | 🔗 原文链接。

**所有图标行按空值跳过该行**(无作者不显示「作者:无」空架子)。

模板(原样照此风格):
```text
🧠 APA 精神科资讯速递 · Psychiatric News
来源:美国精神病学会(APA)官方新闻室 | 最近 7 天(<window 区间>)| 共 N 条
────────
📰 1. 中文标题
🗓️ 日期:May 19, 2026
📝 摘要:中文摘要……
👥 作者:Allen Schatzberg, M.D.
📍 地点:San Francisco
📄 飞书文档:https://feishu.cn/docx/XXXX
🔗 原文:https://www.psychiatry.org/News-room/News-Releases/....
────────
📰 2. 中文标题
📄 飞书文档:https://feishu.cn/docx/YYYY
📑 期刊全文:https://ajp.psychiatryonline.org/toc/ajp/current
🎬 视频摘要:https://youtu.be/XeM_qfxEBrs
🌐 西语版:https://www.psychiatry.org/News-room/News-Releases/Nueva-...
🔗 原文:https://www....
```

## 📤 输出方式(飞书 · v3.4 默认云文档)

- **默认**:飞书云文档(`lark-cli docs +create` 一步到位,见 step 4)
- **备选**:飞书消息(`send_message` 推到当前 chat,纯文本 + 图标)
- **触发判断**(用户明示优先):
  - 明示"飞书文档/云文档/docx"→ **云文档**(v3.4 翻转)
  - 明示"消息/对话气泡"→ 消息
  - **未明示 → 走消息**(实测 2026-06-16 "执行这个 skill" 续接场景:cron job 上下文,产物同步到 chat)
  - cron 自动任务固定走消息
- **docx 失败兜底**:该条不渲染 `📄 飞书文档:` 行 + 末尾汇总 `⚠️ N 条存档失败:<url>`,**不**伪造 doc_url
- 与 sibling `sci-psychiatry-digest` 保持一致(用户 2026-06-12 反馈"给我飞书文档")

## 硬性规则

- 链接一律**裸 URL**,不用 Markdown 超链语法
- 整段输出**不含任何 Markdown 标记**(无 `#` / `**` / `-` / `>` / `[](...)`)
- 默认 7 天窗;用户明确要更长跨度时传参
- 输出中文(标题/摘要译;链接/日期保留原文),按发布时间倒序平铺,不做栏目分类
- 🚨 **每条推荐配飞书文档 + 全文中文翻译**(通用化偏好):`psychiatry.org` 原文链接
  对无外网访问能力的用户不可达。**`🔗 原文:` 行的 value 推荐是飞书云文档 URL**
  (而不是 APA 原文 URL),飞书文档内部含:中英标题 / 作者 / 地点 / 日期 / 中英摘要 /
  相关链接 / **英文 body_md 全文** + **中文 body_md 全文翻译** 2 个独立章节 /
  原文链接。**禁止**只给裸 `psychiatry.org` 链接就交付。如果调用方有外网访问能力,
  可降级为输出 `psychiatry.org` 直接链接(见 step 4 「可选」标记)。

## 编辑纪律(本 skill 适用)

1. **改前先 grep 终态**:用 `grep -c` 验"用户要的目标态"是否已在文件中(避免 no-op)
2. **改前划最小边界**:只动 grep 命中的行,不动未命中行;不"顺手优化"
3. **出方案前先读全文件**:避免 plan 空想(读到 grep 结果才知已实现)
4. **跨 skill 共享 references 必 grep**:避免重复造轮子(兄弟文件已覆盖就不写)
