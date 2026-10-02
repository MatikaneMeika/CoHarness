---
id: T-103
title: 'Fix issue #42 and #99'
status: todo
assignee:
  - '@developer-01'
created_date: '2026-10-02 09:44'
labels:
  - bug
dependencies: []
ordinal: 3000
---

## 需求
测试真实 CLI 生成的标题含 # 符号（自动单引号包裹，非注释）

## 边界
allowed_paths:
  - docs/
forbidden_paths:
  - AGENTS.md

## 验收清单
- [ ] 解析结果与预言机一致
