# {{DOC_NAME}} — 文档生产骨架

> 触发约定：用户说「开工：X」（可带 @路径）= 按本文件与 `.agent/` 规程执行 X；调度细则见骨架库 `ROUTER.md`；门禁照走不豁免。

## 文档卡

| 项 | 内容 |
|---|---|
| 文档名 | {{DOC_NAME}} |
| 读者 | {{AUDIENCE}} |
| 字数目标 | {{WORD_TARGET}} |
| 截止 | {{DUE_DATE}} |
| 格式模板 | {{FORMAT_TEMPLATE}} |

## 目录地图

```
source/                唯一内容源（可编辑的 md 章节文件）
export/                导出产物（docx/pdf，只生成不手改）
docs/                  口径与术语、CHANGELOG
delivery-checklist.md  交付核验清单（checker 维护）
.agent/                协作规则：角色、流程、任务卡
```

## 铁律（源自真实项目教训：8 个 docx 变体互不知道谁是终稿）

1. **单一权威源**：`source/*.md` 是唯一可编辑的内容；`export/` 里是导出产物，**禁止直接手改**——手改的内容下次导出就会丢失，且无人知道它存在
2. **改稿必须回源**：任何修改意见都落到 source/ 对应章节，再重新导出；禁止"直接在 docx 上改"
3. **版本进 git**：导出文件名固定为 `{{DOC_NAME}}.docx/pdf`，禁 `-v2` / `-降重版` / `-final` / `-副本` 后缀；历史靠 git 与 `docs/CHANGELOG.md`
4. **不发明事实**：所有事实、数字、引用只允许来自用户提供的资料或 source/ 已确认内容；写手拿不准 → 标 ⚠ 提问，禁止编造或"合理推测"
5. **口径集中**：术语、字数口径、格式要求、人称时态统一记在 `docs/口径与术语.md`，禁止散落各章（口径冲突是返工首因）
6. **发现骨架问题就登记**：规则缺失/冲突造成返工、同类摩擦 ≥2 次、或缺 skill/MCP 时，在 `.agent/improvements.md` 登记一行（门槛见该文件头部）；试点改动只落本项目，晋升本体走 evolve 审核

## 工作方式

- 从零写 → `.agent/workflows/doc-from-scratch.md`
- 改稿 → `.agent/workflows/revision.md`
- 交付前 → checker 按 `delivery-checklist.md` 逐项核验，全 ✅ 才能交付
