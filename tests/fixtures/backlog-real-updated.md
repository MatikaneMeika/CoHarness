---
id: T-107
title: Task with Updated Date
status: doing
assignee:
  - '@developer-01'
created_date: '2026-10-02 09:44'
updated_date: '2026-10-02 09:44'
labels: []
dependencies: []
ordinal: 7000
---

## 需求
测试真实 CLI 执行 task edit 后生成的 updated_date 字段与 doing 状态

## 边界
allowed_paths:
  - docs/
forbidden_paths:
  - AGENTS.md

## 验收清单
- [ ] 解析结果与预言机一致
