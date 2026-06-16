# lark-cli 实测 pitfall 记录(2026-06-15 端到端实战提炼)

> 本文件记录 psych-news-digest 端到端跑「抓取 → 建 docx → 飞书消息」
> 链路时实测踩到的 lark-cli 行为陷阱,供未来 session 快速对照。

## 1. `drive +search` 索引延迟(2026-06-15)

**症状**:刚 `docs +create` 完 N 份 docx,立刻 `drive +search --folder-tokens <folder>
--doc-types docx` 验证,只搜到 N-1 条甚至更少。

**根因**:飞书 server 侧搜索索引有 5-10 分钟延迟(实测 6 条新 docx 只索引到 5 条)。

**正确做法**:
- **不要**因为"少 1 条"就怀疑 docx 没创建成功 — 创建时返回的 `document_id` +
  `url` 是**权威凭据**,以这个为准
- **不要**反复重试 search(索引几分钟内会齐,等就行)
- **正确的验证方式**:用返回的 `document_id` 直接 `docs +fetch --doc <doc_id>` 拿
  内容确认,或 `docs +update` 看 `revision_id` 是否变化

## 2. `docs +create --parent-token` 一次到位(2026-06-15)

**说明**:把 docx 直接建到指定 folder 用 `--parent-token` 参数,一次成功。
**不必**先 `docs +create`(默认在 root)再 `drive +move`(移到 folder)— 后者是
2 步,前者是 1 步。

```bash
# ✅ 推荐(1 步)
lark-cli docs +create --as user \
  --parent-token <folder_token> \
  --doc-format markdown \
  --content "..."

# ❌ 不推荐(2 步,多一次 API call)
lark-cli docs +create --as user --content "..."   # 创建在 root
lark-cli drive +move --as user \
  --file-token <doc_id> --folder-token <folder>   # 再移动
```

兄弟 `sci-psychiatry-digest/references/feishu-doc-workflow.md` 里的旧示例
(L244-254)还写着 "create + move" 两步法,实际可省略 `+move`(v1 时代建议,现以本文件 § 2 为准)。

## 3. `auth login --recommend` 不给 `search:docs:read`(2026-06-15)

**症状**:`lark-cli drive +search --as user` 报 `missing_scope: search:docs:read`。
**根因**:`--recommend` 推荐的 scope 集合里**不含** `search:docs:read`,要单独补一次。

**正确做法**:`auth login` 必须分两次:
```bash
# 第一次:--recommend(常用 scope)
lark-cli auth login --recommend --no-wait --json
# (用户扫码后)
lark-cli auth login --device-code <device_code>

# 第二次:补 search:docs:read
lark-cli auth login --scope "search:docs:read" --no-wait --json
# (用户扫码后)
lark-cli auth login --device-code <device_code>
```

`--scope` 是增量授权(不会撤销已有 scope),可多次叠加。

## 4. `auth login` 卡 strict-mode(2026-06-15)

**症状**:`lark-cli auth login` 直接返 `command_denied`,错 `strict mode is "bot"`。
**根因**:`lark-cli config bind --source hermes --identity bot-only` 后默认
`strict-mode = bot`,user 身份命令全拒。

**修复(必须 user 显式确认,不能 AI 自主决定)**:
```bash
lark-cli config strict-mode off
# 之后显式 --as user 或 --as bot 切换
```

切 `off` 是安全策略变更,必须 user 同意才能执行。

## 5. `--api-version v1` 参数已废止

新版本 lark-cli 的 `docs +create` / `drive +search` / `drive +move` 等命令
**不再需要也不接受 `--api-version v1`**,默认即 v2。传 `v1` 不会报错但**被忽略**,
且在某些命令下会触发 "v1 interface has been shut down" 错误。

**反例**(2026-06-15 实际见过):
```bash
lark-cli drive +search --query "<folder-name>" --as user
```
**正确**:直接省略 `--api-version`,或不带值留默认。

## 6. `drive +move` 必须 `--type docx`(2026-06-16 实战)

**症状**:`lark-cli drive +move --file-token <doc_id> --folder-token <folder> --as user`
报 `Error: required flag(s) "type" not set`。

**根因**:`drive +move` 强制要 `--type` 区分 docx / folder(不能从 file-token 推断)。

**正确做法**:
```bash
lark-cli drive +move --as user \
  --file-token "$DOC_ID" \
  --folder-token "$FOLDER_TOKEN" \
  --type docx
# 或对文件夹 --type folder
```

**注意**:如果走 `docs +create --parent-token <folder>` 一步到位(本文件 § 2 推荐),
**不需要**这一步,直接省掉。

## 7. `--content @<file>` 必须 cwd 相对路径(2026-06-16 实战)

**症状**:`lark-cli docs +create --content @/tmp/pnd-content-xxx.md --as user` 报
```
--content: invalid file path "/tmp/pnd-content-xxx.md":
--file must be a relative path within the current directory,
got "/tmp/pnd-content-xxx.md" (hint: cd to the target directory first,
or use a relative path like ./filename)
```

**根因**:lark-cli v1.0.53 对 `--content @<file>` 和 `--output` 一样走"unsafe path"
校验,只接 cwd 下相对路径。

**正确做法**(Python subprocess):
```python
import subprocess, os
tmp_name = f"content-{os.getpid()}.md"
with open(f"/tmp/{tmp_name}", "w") as f:
    f.write(content)
subprocess.run(
    ["lark-cli", "docs", "+create", "--doc-format", "markdown",
     "--content", f"@{tmp_name}", "--as", "user"],
    cwd="/tmp",            # ← 关键:把 cwd 设到放临时文件的目录
    capture_output=True, text=True)
```

或 shell: `cd /tmp && lark-cli docs +create --content @content.md ...`

**与 § 2 的关系**:走 `--parent-token` 时**也需要**传 `--content` (只是内容字符串而非
`@<file>`),如果内容长想用 `@<file>` 模式省 escape,本节 fix 适用。
