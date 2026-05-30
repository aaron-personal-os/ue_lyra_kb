# 知识图谱标签与概念页规范

> 配合 [ue-py-evolve/SKILL.md](SKILL.md) 使用

## 三层结构

| 层 | 目录 | 内容 |
|----|------|------|
| 入口 | `knowledge-base.md` | 必读陷阱 + 指向 concepts / modules |
| 概念 | `concepts/*.md` | 稳定定义、简单例子、误判、双向链接 |
| 案例 | `modules/*.md` | 完整现象→根因→修复→预防 |

**原则**：案例写过程与证据；概念写可复用判断方法。API 细节由 `ue-py-run` / 源码查询，概念页只列关键 API 名与脚本名。

## YAML frontmatter

模块 / 概念页顶部：

```yaml
---
kb_type: module | concept
domain: ue | general
tags:
  - concept:AnimNotify
  - pitfall:AuditOKNotL4
  - api:WaitGameplayEvent
  - script:audit_skill_test_arena
  - gate:L4PIE
related_concepts:
  - ../concepts/anim-notify-gas-damage-timing.md
---
```

概念页可用 `related_modules` 代替部分 `related_concepts`。

## 标签前缀

| 前缀 | 用途 | 示例 |
|------|------|------|
| `concept:` | 稳定 UE/GAS 概念 | `concept:EnhancedInput` |
| `pitfall:` | 高频误判 | `pitfall:AuditOKNotL4` |
| `api:` | 关键 API（无路径） | `api:WaitGameplayEvent` |
| `script:` | 长期 L3 脚本（无路径） | `script:audit_skill_test_arena` |
| `gate:` | 质量门禁 / 流程 | `gate:PlanLock` |
| `asset:` | 仅稳定资产名 | `asset:GA_BasicAttack` |

**禁止标签化**：时间戳、session id、一次性探针路径、单次运行统计、调试日志片段。

## 概念页模板

路径：`docs/ue-agent-knowledge/concepts/<slug>.md`

```markdown
---
kb_type: concept
domain: ue
tags:
  - concept:...
related_modules:
  - ../modules/....md
---

# 标题

## 核心概念
## 本项目正确用法
## 简单例子
## 常见误判
## 关联案例
## 相关 API / 脚本
```

## 双向引用

落库时**同时**维护：

1. 概念页「关联案例」→ 链到 `modules/` 章节或文件
2. 案例章节下「相关概念」→ 链到 `concepts/*.md`
3. `concepts/index.md` 表格含新概念一行
4. 模块 frontmatter 的 `related_concepts` 含新概念路径

## 何时新建概念页

满足**全部**时再建（避免概念爆炸）：

- 已在 ≥2 次任务或 ≥2 个案例中反复出现
- 删掉后下一个 Agent 容易走弯路
- 现有概念页无法覆盖（不是同义词重复）

否则只给现有案例 / 模块加 `tags` 与链接。

## 校验

```powershell
python ".cursor\skills\ue-py-evolve\scripts\knowledge_graph_check.py" --check --strict
python ".cursor\skills\ue-py-evolve\scripts\knowledge_graph_check.py" --inventory
python ".cursor\skills\ue-py-evolve\scripts\knowledge_graph_check.py" --print-tags
```

## 存量整理检查清单（整库合规）

复制勾选，完成一项勾一项：

- [ ] `knowledge-base.md` 有 `kb_type: entry` + 链到 `concepts/index.md`
- [ ] `modules/*.md` 均有 frontmatter（`kb_type: module`）+ `tags` + `related_concepts`
- [ ] `concepts/*.md`（除 index）符合六段模板 + `related_modules` 或「关联案例」
- [ ] `concepts/index.md` 概念表 + **模块索引表** 已更新
- [ ] `knowledge-base.md` §5 各子表有「概念 / 案例」引导行
- [ ] `--inventory` 已生成 `concepts/inventory.generated.json`
- [ ] `--check --strict` 0 error、0 warning
