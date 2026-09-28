---
id: T-000-board
title: 看板与登记常驻卡（改卡或登记前先认领它）
status: todo
assignee: []
labels: []
created_date: 2026-09-28
updated_date: 2026-09-28 09:00
---

## 需求
看板状态流转与 `.agent/improvements.md` 登记这两类提交，在执法面里没有授权通道：
`backlog/` 与 `.agent/` 是每张卡 `forbidden_paths` 的默认值，而卡自己的改动又必须"挂到某张卡的
`allowed_paths` 上"才放行。协议却要求认领动作直接提交进 main（parallel-protocol），登记改进是
全局禁令第 7 条（AGENTS.md）。这张常驻卡就是那条通道：把 `backlog/` 与 `.agent/improvements.md`
列进它自己的 `allowed_paths`。

## 技术口径
不动代码。只动看板文件与登记表；代码改动一律另开实现卡，按实现卡的边界走。

## 边界
allowed_paths:
  - backlog/
  - .agent/improvements.md
forbidden_paths:
  - AGENTS.md
  - .agent/roles/
  - .agent/workflows/
  - .agent/tasks/

## 验收清单
- [ ] 认领与退回都提交进 main（`backlog task edit` + commit + push）
- [ ] 持本卡期间，同一 assignee 不再持其他 doing 卡（"一 harness 一张 doing 卡"是硬门禁）
- [ ] 登记表新增行的编号自 I-001 递增，状态列填"登记"

## 交接说明
这是**绕行**，不是设计意图。缺口已登记 I-001；等同类摩擦攒够第二次或经 evolve 审核后，
放行规则会写进 check.py 的本体，届时删除本卡。
