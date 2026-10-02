---
id: T-108
title: 'Fix user''s issue #123'
status: todo
assignee:
  - '@developer-01'
created_date: '2026-10-02 09:44'
labels: []
dependencies: []
ordinal: 8000
---

## 需求
测试真实 CLI 面对单引号/撇号时的转义写法（YAML 标准 '' 转义），揭示当前解析器 _strip_comment 的截断缺陷

## 边界
allowed_paths:
  - docs/
forbidden_paths:
  - AGENTS.md

## 验收清单
- [ ] 记录解析截断事实与缺陷坐标
