---
name: ue-py-evolve
description: "回顾并改进知识体系文档。在 ue-py-run 或 ue-py-extend 完成后手动调用，将新发现的陷阱、规则、模式沉淀到知识库。触发关键词：文档改进、知识沉淀、更新知识库、evolve、ue-py-evolve。"
disable-model-invocation: true
---

# 知识自进化

根据刚才的工作历史，回顾遇到的问题，改进知识库文档。

## 何时调用

- `ue-py-run` 执行中踩了知识库里没写的坑 → 调用 evolve 补进去
- `ue-py-extend` 打通了新模块 → 调用 evolve 检查文档质量
- 发现知识库里的内容过时或错误 → 调用 evolve 修正
- **REACT Test** 发现 validation-checklist 未覆盖的新坑 → 建议 evolve 沉淀

> 这是手动触发的 skill，不会自动运行。

## 知识库位置

从 `.ue-py-config.json` 读取。首次使用前必须先运行 `ue-py-init`。

典型结构：

```
<用户指定的路径>/
├── knowledge-base.md        通用规则（每次会话必读）
├── concepts/                概念层（标签 + 简单例子 + 双向链接）
│   ├── index.md
│   └── *.md
└── modules/
    ├── development-quality-gates.md
    └── ...
```

标签与概念页规范见 [tagging.md](tagging.md)。

## 执行方式

1. 从当前目录向上查找 `.ue-py-config.json`，读取知识库路径
   - 找不到？→ 提示用户先运行 `ue-py-init`
2. 读取 `knowledge-base.md` 与 `concepts/index.md`（若存在）
3. 列出 `modules/`、`concepts/`，读取与本次工作相关的文档
4. **汇报已读文档** — 向用户列出你读了哪些文件
5. 回顾上下文历史，对照知识库找出可改进的点
6. 按文件分组列出建议：**改什么、为什么、改成什么**（含推荐 `tags` / `related_concepts`）
7. 等待用户确认后写入
8. **落库后**运行知识图谱校验（见下「图谱维护」）

## 图谱维护（写入时必做）

用户确认写入后，除改 `knowledge-base.md` / `modules/` 外：

1. 若涉及稳定概念 → 更新或新建 `concepts/<slug>.md`（用 [tagging.md](tagging.md) 模板）
2. 更新 `concepts/index.md` 表格行
3. 在案例章节下补相关概念链接；概念页补「关联案例」
4. 模块 frontmatter：`tags`、`related_concepts` 与正文一致
5. 运行校验：

```powershell
python ".cursor\skills\ue-py-evolve\scripts\knowledge_graph_check.py" --check --strict
python ".cursor\skills\ue-py-evolve\scripts\knowledge_graph_check.py" --inventory
```

校验路径由 `.ue-py-config.json` 中 `knowledge_base` 字段自动推断知识库根目录；也可用 `--root` 指定。

失败则修复断链/孤立概念，再向用户汇报校验结果。

## 初始化（首次使用）

如果知识库目录下文件为空或刚从模板创建：

1. 回顾当前会话的执行记录
2. 提取遇到的所有错误和解决方式
3. 将高频规则写入 `knowledge-base.md` 对应章节
4. 如果打通了新模块，创建 `modules/<module>.md`

## 改进原则

- **只沉淀通用知识**——不写入当前任务的具体资产名、统计数、一次性脚本路径
- **遇到 2 次以上的问题才沉淀**——或者 1 次就导致严重后果的陷阱
- **保持精炼**——上下文填到 40% 以上 Agent 注意力开始分散，宁可少写几条高频的，不要堆一堆低频的
- **反问判据**：这段删掉后，下一个 Agent 会不会走弯路？不会 → 不写

## 输出格式

建议以如下格式提交改进：

```markdown
## 建议修改

### knowledge-base.md §5 已知陷阱

**新增陷阱 N：**
- 现象：<Agent 遇到了什么>
- 原因：<为什么会这样>
- 解决：<怎么避免或修复>

### modules/gas-skill-test-arena.md

**修改验收清单第 X 行：**
- 原内容：...
- 改为：...
- 原因：<实测发现>

### concepts/anim-notify-gas-damage-timing.md（新建或更新）

- 新增「常见误判」一行
- tags: `concept:AnimNotify`, `pitfall:...`
- 关联案例链到 modules
```

## 附加资源

- [tagging.md](tagging.md) — 标签前缀、概念页模板、禁止标签化
- `scripts/knowledge_graph_check.py` — `--check` / `--print-tags` / `--inventory`
