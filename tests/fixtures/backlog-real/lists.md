---
id: T-104
title: Multi Assignees and Labels
status: todo
assignee:
  - '@alice'
  - '@bob'
created_date: '2026-10-02 09:44'
labels:
  - frontend
  - backend
  - urgent
dependencies:
  - T-101
  - T-102
ordinal: 4000
---

## 需求
测试真实 CLI 生成的多 assignee、多 labels、多 dependencies 块列表缩进

## 边界
allowed_paths:
  - docs/
forbidden_paths:
  - AGENTS.md

## 验收清单
- [ ] 解析结果与预言机一致
