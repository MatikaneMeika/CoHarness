# 流程：assignment（作业全流程）

## 步骤总览

```
提取要求[门禁1] → 拆任务卡 → 编码实验 → 报告撰写 → 逐项自检[门禁2] → 打包交付
```

## 步骤明细

### 1. 提取要求（requirement-analyst）【门禁 1】
- 产出 `docs/requirements-checklist.md`
- 读不准的条目可借 `/speckit-clarify` 的追问方式收敛，但**逐字摘录与 ⚠ 门禁不变**
- **用户确认清单后才能开工**——这一步省下的纠正成本最多

### 2. 拆任务卡（可选，多任务/多人分工时用）
- 单交付物小作业可跳过建卡，直接按后续步骤走
- 用卡时：每个交付物一张卡，`backlog task create`（格式见 `.agent/tasks/CARD-CONVENTION.md`）
- 卡的 labels 标注对应清单条目编号（REQ-x），验收清单逐条引用，保证闭环

### 3. 编码与实验（coder）
- 按 `.agent/roles/coder.md` 的可复现性要求执行
- 实验数据落 `deliverables/data/`，失败也如实记录

### 4. 报告撰写（report-writer）
- 数据齐了才动笔；图表先用真实数据画，不画"示意图"冒充结果
- 中途发现实验设计撑不起结论 → 回到步骤 3 补实验，**不改数据凑结论**

### 5. 逐项自检（self-checker）【门禁 2】
- 清单全 ✅（⚠ 项经用户确认）才能进步骤 6

### 6. 打包交付
- 按 AGENTS.md 命名规则输出最终文件到指定提交位置
- `git commit` 留存交付快照；CHANGELOG 或 docs/notes.md 记一行"已交付 + 提交内容清单"
