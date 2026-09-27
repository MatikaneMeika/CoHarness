# 流程：new-feature（新功能全流程，spec-kit 版）

## 步骤总览

```
/speckit-specify → /speckit-clarify → /speckit-plan【门禁1】 → /speckit-tasks
  → pm 转卡 → 并行实现 → reviewer 门禁 → tester 回归【门禁2】 → integrator 收尾
```

## 步骤明细

### 1. 规格化（pm 主导，spec-kit 承载）
- `/speckit-specify`：需求 → 规格（含目标 / **非目标** / 验收标准）
- `/speckit-clarify`：歧义清零；仍有读不准的 → 问用户，禁止按猜测推进
- `/speckit-plan` 【门禁 1：用户批准】→ 技术方案落档

### 2. pm 拆卡（spec-kit 产出 → Backlog 卡）
- 按 `.agent/roles/pm.md` 桥接规则逐条转卡：粒度半天、allowed_paths 互斥、依赖标注
- architect 同步：ARCHITECTURE.md 更新、ADR、每卡"技术口径"与"边界"节核定

### 3. 并行实现
- 各 harness 按 `.agent/workflows/parallel-protocol.md`：pull → 认领（进 main）→ `git-wt` 开 worktree → 实现
- 前置卡（如接口定义卡）done 后，依赖它的卡才能开工
- 提交过 pre-commit（check.py 强制）

### 4. reviewer 门禁（逐卡）
- 按 `.agent/roles/reviewer.md` 清单；fail 退回 `doing`，pass 置 `review`

### 5. tester 集成回归【门禁 2】
- 全量测试 + 主链路冒烟 → 回归报告；`scripts/check.py` 全绿
- 任何一项不过 = 门禁 2 未过，禁止合并

### 6. integrator 收尾
- 合并（串行化）、`git-wt remove` 清理、核对 CHANGELOG
- 向用户报告：本次功能包含哪些卡、验证结论、遗留事项

## 反模式（出现过就要停）

- 门禁 1 未批就开工；跳过 /speckit-clarify 直接拆卡
- 两张卡改同一个文件（allowed_paths 交集）
- reviewer 由同轮实现者兼任
- 回归失败硬合并（"先合了再修"）
