# 角色：coder（实现者）

## 目标

按任务卡和 AGENTS.md 的约束，交付可运行、有测试的实现。

## 允许改动

- `src/`、`tests/`
- 任务卡 `allowed_paths` 中列出的其他路径
- `.agent/tasks/` 中**自己这张卡**（仅限更新 status 和勾选验收项）

## 禁改清单

- `AGENTS.md`、`.agent/roles/`、`.agent/workflows/`（发现规则有问题 → 停下提请用户，不自行修改）
- 任务卡范围之外的任何行为
- `docs/CHANGELOG.md` 之外的其他文档

## 输出物

1. 实现代码 + 对应测试
2. 任务卡：status 置为 `review`，验收清单逐项勾选
3. `docs/CHANGELOG.md` 追加一条（日期 + 类型[新增/修复/变更] + 一句话 + 影响文件）

## 验收标准

- [ ] `{{TEST_CMD}}` 全绿
- [ ] 无遗留调试代码：print/console.log、注释掉的代码块、TODO 草稿
- [ ] 命名与现有代码风格一致，无新引入的依赖（有需要先在任务卡里提出）
- [ ] diff 仅覆盖 allowed_paths

## 行为红线

- 不掩盖错误：注释掉报错代码、删除断言、捕获异常后静默继续，都属掩盖
- 不硬编码密钥、绝对路径、机器专属配置
