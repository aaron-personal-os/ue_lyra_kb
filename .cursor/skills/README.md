# UE Python Skills（Cursor 项目 Skills）

让 AI Agent 通过 Python Remote Execution 控制运行中的 Unreal Engine Editor。

## 在 Cursor 中使用

Cursor 只识别 **`.cursor/skills/<skill-name>/SKILL.md`** 这一层目录。输入 `/` 后应能看到：

| `/` 命令 | 用途 |
|----------|------|
| `ue-py-init` | 首次配置（知识库、`.ue-py-config.json`、验证 Editor 连接） |
| `ue-py-run` | 在 Editor 内远程执行 Python |
| `ue-py-extend` | Python API 不够时，按流程写 C++ 扩展 |
| `ue-py-evolve` | 把踩过的坑沉淀到知识库 |

若 `/` 菜单里仍看不到，重载 Cursor 窗口（Command Palette → **Developer: Reload Window**）。

## 快速开始

1. 启动 UE Editor，确认 **Preferences → Python → Remote Execution** 已开启
2. 在 Cursor 输入 `/ue-py-init` 完成首次配置
3. 之后用 `/ue-py-run` 或直接描述要在 Editor 里做的事

## 目录结构

```
.cursor/skills/
├── ue-py-init/
│   ├── SKILL.md
│   └── templates/knowledge-base.md
├── ue-py-run/
│   ├── SKILL.md
│   └── scripts/ue_python.py
├── ue-py-extend/
│   ├── SKILL.md
│   └── references/extension-spec.md
└── ue-py-evolve/
    └── SKILL.md
```

## 工作原理

```
Agent → 读知识库 → 写代码 → ue_python.py → UDP/TCP → Editor 执行 → 返回结果
```

## 兼容性

- UE 5.0+（需 PythonScriptPlugin）
- 原仓库为 Windows/PowerShell 示例；macOS 可用项目根目录 `get_engine_root.sh` 解析引擎路径
- Cursor Agent Skills 格式（`.cursor/skills/`）
