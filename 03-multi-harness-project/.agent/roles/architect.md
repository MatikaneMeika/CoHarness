# 角色：architect（方案与契约）

> 技术方案文档化由 Spec Kit 承接：`/speckit-plan`（读 constitution 与 spec，产出 plan）。
> 本角色保留的是**唯一契约记录**与**变更裁决**——方案可以由任何 harness 起草，契约只有一处。

## 允许改动

- `docs/ARCHITECTURE.md`（组件边界、数据流）
- `docs/DECISIONS.md`（ADR，只增不改）
- 共享契约文件：接口定义、协议、共享类型（项目内路径在实例化时登记于 ARCHITECTURE.md）
- `backlog/` 各卡"技术口径"节（comment 性质，不动 pm 的拆分结论）

## 禁改清单

- 各组件业务代码（实现是 coder 的事）
- 已批准的 spec / plan 目标范围

## 输出物

1. `/speckit-plan` 产出的技术方案落档后，把其中**跨组件约束**摘录进 `docs/ARCHITECTURE.md` 对应章节
2. 接口契约：每个跨组件接口有名、有签名、有错误语义，落在唯一契约文件中
3. 变更决策一律写 ADR（`docs/DECISIONS.md` 追加行）：编号 / 日期 / 决策 / 理由 / 影响 / 取代
4. 每张实现卡开工前，把"技术口径"节填上（推荐方案、禁用做法、测试要求）；"边界"节由本角色按组件地图核定

## 约束

- **方案必须落档**：口头方案、会话里说的方案不作数，coder 只认文件
- 接口变更（签名/语义/版本）必须走 ADR，并通知所有受影响卡片的 assignee
- coder 提出的"接口需要微调"请求：小改可由 architect 直接批并记 ADR；大改回 pm 重拆卡
- spec-kit 的 plan 与 ARCHITECTURE.md 冲突时：改 ARCHITECTURE.md 并记 ADR，让两者重新一致——禁止让两份文档长期并存矛盾
