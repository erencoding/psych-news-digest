# 字段抽取模式与盲区(2026-06-15 提炼)

> 覆盖 `scripts/fetch_news.py` 6 个抽取型字段(`summary` / `body_md` / `paragraphs` /
> `authors` / `location` / `extra_links`)的**正则模式、覆盖率天花板、典型盲区**。
> APA 改版命中率下降时,优先对照本表。
>
> 文档创建/飞书消息拼装等其他链路见 `references/lark-cli-pitfalls.md` +
> `sci-psychiatry-digest/references/feishu-doc-workflow.md`。

## 1. `summary`(meta description 优先,body 兜底)

| 维度 | 数据 |
|---|---|
| 命中率 | 6/6 = **100%** |
| 抽取方式 | `<meta name="description" content="...">` 正则 |
| 兜底 | `body_md` 第一段截 400 字符 |
| 用途 | **仅给消息模板的中文摘要翻译用**,**不是**给存档 docx 用(SKILL.md L23 必读 pitfall) |

### 盲区
- meta description 通常是 APA 编辑部 1 段营销文案,不是研究摘要本身
- 长度 150-200 字符,**不含数据点**(95 例 / 34.7% / 66.6% 之类全无)
- **若误用 summary 写 docx**:存档会丢失 90% 内容(2026-06-15 用户原话
  「飞书文档内容和原文内容非常不一致」)

---

## 2. `body_md`(完整正文 Markdown,html2text 转换)

| 维度 | 数据 |
|---|---|
| 命中率 | 6/6 = **100%** |
| 抽取方式 | 先抽 `<article>` 块 → html2text 转 Markdown |
| 用途 | **存档 docx 用**,不翻译,直接写飞书云文档 |

### html2text 配置(已验证最优)
```python
h2t.body_width = 0           # 不自动换行(避免破坏链接)
h2t.ignore_links = False     # 保留链接 → 给 extra_links 抓
h2t.ignore_images = True     # 图片不抓(APA 新闻页图片是 logo/装饰)
h2t.ignore_emphasis = False  # 保留加粗/斜体(给 location 抓 dateline **City** 用)
h2t.bypass_tables = False    # 表格转 Markdown 表(期刊汇总有用)
```

### 盲区
- html2text 偶尔会把 `<br>` 渲染成 `\n`(段间断行),paragraphs 切分时已过滤
- APA 新闻页**无 `<article>` 标签**时,fallback 到全文 + 删除 `<header>/<footer>/<nav>/<aside>/<script>/<style>`,**命中率仍 100%**(实测)

---

## 3. `paragraphs`(从 body_md 按空行切)

| 维度 | 数据 |
|---|---|
| 命中率 | 6/6 = **100%** |
| 过滤 | 长度 < 40 字符的短段(导航/版权/版权声明) |
| 用途 | location / authors / extra_links 抽取的输入 |

### 切分铁律
- **按 `\n\s*\n` 切**(双换行 = 段间)
- **保留 markdown 标记**(`#` / `**` / `>` / `[]()`)— 给下游正则用
- 长度过滤只看**纯文本长度**(去 markdown 装饰后),不用粗长度

---

## 4. `authors`(3 优先级 + 2 兜底,共 5 步)

| 维度 | 数据 |
|---|---|
| 命中率 | 5/6 = **83%**(2026-06-15 实测 30 天窗 6 条) |
| **理论上限** | **6/6 中 1 条是期刊汇总,本身无作者段 → 永久 N/A** |
| 真实命中 | 5/6 = 83% 是天花板,**不要尝试"再修"** |

### 5 步优先级(顺序尝试,前一步命中则跳过后续)

#### Step 1: "study authors include/included/are A, B, and C"
- **模式**:`(?i)(?:study\s+authors?\s+(?:include|included|are)|authors?\s+(?:include|included|are))\s+`
- **截断**:先 `, of <机构>` 截;否则句末 `. [A-Z][a-zÀ-ÿ]`
- **拆分**:`, and ` / `, ` / `; ` 三种分隔符都试
- **严苛过滤**:长度 8-60、首大写、≥2 词、词首均大写、**不以 `.` 结尾**(排除孤立 "M.D.")
- **覆盖**:研究型新闻主流 4/6

#### Step 2: dateline 兜底(人物公告类)
- **场景**:「Mark Rapaport, M.D., began his...」(APA 协会人事任命)
- **模式**:`[A-Z][a-z…'-]+(\s+[A-Z]\.)?\s+[A-Z][a-z…'-]+,?\s*(?:M\.D\.|Ph\.D\.|M\.A\.|M\.S\.|Psy\.D\.|R\.N\.|Dr\.)`
- **覆盖**:1/6(人事公告)

#### Step 3: senior/lead/corresponding author 模式(3 子模式)
- **场景**:APA 故意不公布全部作者,引用句形如「said X, M.D., senior author」
- **3 子模式**(顺序尝试):
  1. `(?:according to )?(?:senior|lead|corresponding) author Name`
  2. `Name, M.D., (senior|lead|corresponding) author`
  3. `(?:said|according to) Name, M.D.`(兜底,无显式 senior 标志)
- **范围**:前 6 段(比 Step 2 扩 2 倍,因为引用句常在更后)
- **覆盖**:1/6(Ketamine: Allen Schatzberg)

#### 为什么 5/6 是天花板

| 文章类型 | 作者数 | 原因 |
|---|---|---|
| 研究型(4/6) | 4 | "study authors include ..." 模式 |
| 人物公告(1/6) | 1 | dateline 直接带 "Name, M.D." |
| Ketamine 类(1/6) | 1 | APA 故意不公布具体作者,只 senior |
| **期刊汇总(0/6)** | **0** | **期刊级别汇总,无作者段,N/A 性质** |

**结论**:83% 已是合理上限,期刊汇总 = N/A 是设计使然不是 bug。

### 误抓铁律
- Step 3 子模式 3(`said Name, M.D.`)有风险:**只在前 6 段 + 严苛过滤(首大写 + 8-50 字符 + 2 词)**
- 段 7 提到「Dr. Alan Schatzberg」(Alan ≠ Allen,且无 `said` 上下文)→ 不会被错抓

---

## 5. `location`(首段 dateline 抓城市)

| 维度 | 数据 |
|---|---|
| 命中率 | 6/6 = **100%** |
| 模式 | 跳过 H1 标题(paragraphs[0])→ 从 paragraphs[1:4] 找 dateline |
| dateline 形态 | `**Washington, D.C. --**` / `**San Francisco --**` / `City, ST —` |

### 抽取铁律
- **去 markdown 装饰**:`re.sub(r'[\s>*_`*-]+', ' ', p).strip()`(处理 `**` / `>` / `_`)
- **匹配**:`r'^([A-Z][A-Za-z\s,.\']+?)\s*[—\-]{1,2}\s+'`
- **城市名提取**:取 group(1),再 `strip('*').strip()`
- **城市名可能含逗号**:"Washington, D.C." / "New York, NY" 都能匹配

### 盲区
- APA 偶尔用「Online」/「Virtual」开头 → 不会匹配,location 为空
- APA 极少数新闻无 dateline(纯人物引言开头)→ 走「全文找 City, ST — 」兜底

---

## 6. `extra_links`(3 类型,2026-06-15 新增)

| 维度 | 数据 |
|---|---|
| 命中率 | 2/6 = **33%** |
| **覆盖规律** | 期刊汇总 / 西语版镜像 / 视频摘要 / 期刊全文 4 类信息**只在 1/6 ~ 2/6 文章出现** |
| 上限 | 不需要修,APA 新闻页结构决定 |

### 3 类型识别(顺序敏感)

| 优先级 | type | 匹配 regex | 出现频次 |
|---|---|---|---|
| **1** | `spanish` | `psychiatry\.org/.*?(Nueva\|Nuevo\|Investigaci\|TDAH\|Espa[ñn]ol)` | 1/6 |
| 2 | `journal` | `(ajp\|ps)\.psychiatryonline\.org` | 2/6(只在期刊汇总) |
| 3 | `youtube` | `youtu\.?be` | 1/6(只在期刊汇总) |
| × | 跳过 | `psychiatry.org` 主页 / facebook / twitter | — |

### ⚠️ PITFALL · spanish 类型 host 仍是 psychiatry.org

**反例**(2026-06-15 第一版踩过):
```python
# ❌ spanish 永远被过滤(因为前一步 "psychiatry.org in url" 跳过了)
if "psychiatry.org" in url:
    continue
# 分类...
elif re.search(r'psychiatry\.org/.*?(Nueva|...)', url):
    type_ = "spanish"  # 永远到不了这里
```

**正确做法**:
```python
# ✅ spanish 必须在分类第一步特判,再统一 dedup
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
```

### 抽取 regex(同时支持 `[label](url)` 和裸 URL 两种格式)
```python
link_pattern = re.compile(
    r'\[([^\]]+)\]\((https?://[^\s)]+)\)|(https?://[^\s)\]]+)', re.I
)
for m in link_pattern.finditer(body_md):
    if m.group(2):
        label, url = m.group(1).strip(), m.group(2).strip()
    else:
        url, label = m.group(3).strip(), ""
    # ... 分类逻辑见上表
```

### 上限说明
- **journal(2/6)**:只期刊汇总会出现 AJP/PS 期刊 TOC 链接,研究型单篇新闻**不引用具体文章链接**
- **youtube(1/6)**:只期刊汇总有 Deputy Editor 视频摘要
- **spanish(1/6)**:APA 大约每 5-10 篇有 1 篇西语版镜像

**结论**:2/6 (33%) 是合理上限,不要尝试"再修"。

---

## 7. 维护清单(APA 改版时)

| 信号 | 改哪里 |
|---|---|
| `count=0` 持续 3 天 | 更新 `parse_listing()` 的 class selector(`c-article-item` / `c-meta__date`) |
| `summary` 命中率 < 80% | meta description 正则失效 → 改去抓 `<p>` 标签前 200 字符 |
| `body_md` 字符骤降 | html2text 升级 / `<article>` 标签改名 → 改 `re.search(r'<article[^>]*>...')` |
| `location` 命中率 < 80% | dateline 格式变化 → 检查 APA 模板是否改 "—" 为 ":",改 regex |
| `authors` 命中率 < 70% | 模板变化 → 新增 senior author 子模式 / 改 dateline 兜底 |
| `extra_links` 命中率 < 20% | 链接结构变化 → 检查 `link_pattern` 是否还覆盖 `[](url)` 和裸 URL 两种 |

**改任何一处之前**:先 `grep -c "目标旧态"` 确认 unique,避免 patch-no-op 陷阱(本 skill SKILL.md 末尾"编辑纪律"段已固化此规则)

## 版本

- v1.0 (2026-06-15):从 2026-06-15 端到端实战提炼(30 天窗 6 条数据)
