---
id: T-105
title: Empty Fields Task
status: todo
assignee: []
created_date: '2026-10-02 09:44'
labels: []
dependencies: []
ordinal: 5000
---

## 需求
测试真实 CLI 生成的空列表留空结构（assignee: []、labels: [] 等）

## 边界
allowed_paths:
  - docs/
forbidden_paths:
  - AGENTS.md

## 验收清单
- [ ] 解析结果与预言机一致
