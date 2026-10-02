---
id: T-106
title: Role Labeled Task
status: todo
assignee:
  - '@tester-01'
created_date: '2026-10-02 09:44'
labels:
  - 'role:tester'
  - 'scope:cli'
dependencies: []
ordinal: 6000
---

## 需求
测试真实 CLI 生成的含冒号 labels（自动单引号项，如 role:tester）

## 边界
allowed_paths:
  - docs/
forbidden_paths:
  - AGENTS.md

## 验收清单
- [ ] 解析结果与预言机一致
