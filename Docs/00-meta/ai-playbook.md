# AI 协作手册

> **所有 AI Agent 必读**。本文档定义 AI 在本技术学习知识库中协作的规则与约束。

## 知识库定位

本知识库是 **UE 技术学习知识库**，不是项目开发文档：

- **不写业务代码** — AI 不负责为 Lyra 项目开发新功能
- **写教学文档** — AI 基于示例项目 + 引擎源码 + 外部资料，生产系统化技术教程
- **辅助学习** — AI 通过对话向用户教学，并将有价值的知识沉淀为文档

## 核心原则

1. **源码为信源** — 所有技术断言必须以源码为最终依据（见下方详细约束）
2. **教学为本** — 所有产出以"帮助用户理解技术"为目标
3. **先读后写** — 任何任务前，先检索知识库已有内容
4. **由浅入深** — 文档和回答都遵循渐进式结构
5. **标注来源** — 引用知识库页面、标注引擎源码路径
6. **保持健康** — 及时标记 `status`，维护 wikilink 完整性

## 源码为信源（所有工作流的通用约束）

> **本节是所有产出内容（init 和 lint 除外的全部工作流）必须遵守的信源准则。**

### 为什么需要这条准则

AI 的训练数据存在版本滞后和不精确的问题。UE 引擎版本迭代快（5.0→5.7 API 变化巨大），凭记忆写出的教程可能：
- 函数签名已经变化
- 调用链已经重构
- 新增了关键参数或弃用了旧接口

**源码是唯一不会"幻觉"的信源。**

### 信源优先级

| 优先级 | 信源 | 用途 |
|--------|------|------|
| **1（最高）** | Lyra 项目源码（`Source/LyraGame/`） | Lyra 实现分析的唯一依据 |
| **2** | UE 引擎源码（本地源码构建） | 引擎机制分析的主要依据 |
| **3** | UE 官方文档（docs.unrealengine.com） | 概念定义、API 说明的补充 |
| **4** | Context7 / 权威技术文档 | 最佳实践、设计理念的参考 |
| **5（最低）** | AI 训练数据 / 社区博客 | **仅用于构建初始假设，必须用 1-4 验证后才能写入知识库** |

### 源码路径（本项目环境）

本项目使用 **UE 5.7 源码构建**，引擎源码与项目源码均可直接读取：

| 信源 | 根路径 | 说明 |
|------|--------|------|
| **Lyra 项目源码** | `Source/LyraGame/` （项目内相对路径） | 直接读取，无需额外配置 |
| **UE 引擎源码** | 由根目录脚本动态解析（见下） | 不同机器路径不同，**禁止硬编码** |

#### 获取引擎根路径（脚本化）

> **AI 必须执行项目根目录的脚本获取引擎路径，不要在文档/代码中硬编码绝对路径。**

| 平台 | 命令 | 输出 |
|---|---|---|
| Windows | `powershell -NoProfile -ExecutionPolicy Bypass -File ./get_engine_root.ps1 -Json` | JSON |
| Windows (CMD) | `get_engine_root.bat --json` | JSON |
| macOS / Linux | `./get_engine_root.sh --json` | JSON |

**JSON 输出字段**（AI 解析这一份即可）：

```json
{
  "ok": true,
  "uproject": "...\\LyraStarterGame.uproject",
  "engineAssociation": "5.7",
  "associationType": "installed",        // installed | source-build
  "engineRoot": "F:\\UE_5.7",
  "engineSource": "F:\\UE_5.7\\Engine\\Source",
  "enginePlugins": "F:\\UE_5.7\\Engine\\Plugins"
}
```

**脚本工作原理简述**（无需理解细节）：

1. 读取 `LyraStarterGame.uproject` 的 `EngineAssociation` 字段
2. 若为版本号（`"5.7"`）→ 查 Windows 注册表 `HKLM\SOFTWARE\EpicGames\Unreal Engine\<Ver>\InstalledDirectory`
3. 若为 GUID（`"{...}"`）→ 查 `HKCU\SOFTWARE\Epic Games\Unreal Engine\Builds`（Windows）或 `~/Library/Application Support/Epic/UnrealEngine/Install.ini`（macOS / Linux）
4. 拼装并返回 `engineRoot / engineSource / enginePlugins`

**使用要点**：

- **首次需要引擎源码时执行一次**，把 `engineRoot` 缓存到当前会话上下文
- `associationType` 说明引擎类型（`installed` = Launcher 安装版，`source-build` = 自编译版），二者均可读源码；如需修改并重编译引擎本体，必须是 `source-build`
- 标注源码路径时使用 `Engine/Source/...` 相对形式（省略机器特定前缀），保持文档可移植


### 各工作流的验证要求

| 工作流 | 验证要求 |
|--------|---------|
| **create-series** | Phase 1 必须做深度源码调研（推荐 SubAgent），每篇教程的技术断言必须有源码引用 |
| **evolve-series** | 更新/补充教程时，必须重新读取对应源码确认内容仍然准确 |
| **teach** | 回答技术问题时，关键结论应引用源码或已有教程（教程本身已经过源码验证） |
| **source-trace** | 天然基于源码，输出必须标注文件路径和关键行号 |
| **ingest** | 消化外部资料时，技术性内容必须与项目源码交叉验证后再写入 |
| **crystallize** | 沉淀当前对话时，技术结论必须标注源码依据（文件路径或教程引用） |
| **digest** | 综合分析时，跨页引用的技术事实必须一致；发现矛盾时以源码为准 |
| **query** | 只读工作流，但回答中引用的教程内容如果存疑，应标注"待源码验证" |
| **review-series** | 审查教程质量时，必须抽样验证关键技术断言的源码引用是否有效 |

### 验证操作指南

```bash
# 验证 Lyra 源码中某个类/函数
rg -n 'ClassName' Source/LyraGame/ --include='*.h' --include='*.cpp'

# 验证引擎源码（相对路径，推荐）
rg -n 'FunctionName' ../UnrealEngine/Engine/Source/ --include='*.h' --include='*.cpp'

# 引擎 GAS 插件源码
rg -n 'UGameplayAbility' ../UnrealEngine/Engine/Plugins/Runtime/GameplayAbilities/ --include='*.h' --include='*.cpp'

# 使用 LSP 追踪定义和调用（如果 IDE 支持）
# goToDefinition / findReferences / incomingCalls

# 如果相对路径失败，使用绝对路径
rg -n 'FunctionName' /Users/robert/Documents/UECode/UnrealEngine/Engine/Source/ --include='*.h' --include='*.cpp'
```

### 标注规范

所有写入知识库的技术内容，必须标注信源层级：

```markdown
<!-- 已用源码验证 -->
`UGameplayAbility::ActivateAbility()` 在激活时会先调用 `CanActivateAbility()` 检查条件。
（源码：`Engine/Plugins/Runtime/GameplayAbilities/.../GameplayAbility.cpp` L234）

<!-- 基于官方文档，未逐行验证源码 -->
GAS 系统支持网络预测，客户端可以在等待服务器确认前先行激活能力。
（参考：[UE 官方 GAS 文档](https://docs.unrealengine.com/...)）

<!-- 待验证 -->
> ⚠️ 以下内容基于 AI 推断，尚未经过源码验证：
> GameplayCue 在 Dedicated Server 上默认不执行表现逻辑。
```

## 检索优先级

AI 在回答技术问题时的检索顺序：

1. `Docs/index.md` → 快速定位相关教程/页面
2. `Docs/30-tutorials/` → 查找系统化教程内容
3. `Docs/20-modules/cpp/` → 查找 Lyra 模块文档
4. frontmatter tag/related grep → 扩展搜索
5. 全文搜索（`rg`）→ 查找具体内容
6. 源代码 → 作为教学素材读取

**禁止**：
- 不经过检索直接回答技术问题
- 引用 `status: stale` / `deprecated` 的页面而不警告
- 跳过教程直接贴大段源码不解释

## 教学表达约束

### 文档编写原则

1. **由浅入深** — 每篇先给概念直觉（"是什么、为什么"），再给技术细节（"怎么实现"）
2. **先总后分** — 先给系统全景图，再逐个拆解子模块
3. **理论+实践双线**：
   - 每个引擎概念 → 对应 Lyra 项目中的实际使用
   - 每个 Lyra 实现 → 追溯到引擎层的设计理由
4. **渐进式代码展示**：
   - 先展示关键 3-5 行（核心逻辑）
   - 再展示完整函数（上下文理解）
   - 最后展示调用链（系统理解）
5. **图示辅助** — 关键架构/流程必须提供 mermaid 图示

### 教学问答（teach 工作流）

AI 回答技术问题时遵循**三层回答结构**：

| 层次 | 内容 | 目的 |
|------|------|------|
| 第一层 | 概念直觉（一句话 + 类比） | 10 秒理解"是什么" |
| 第二层 | 技术机制（关键代码 + 流程图） | 理解"怎么工作" |
| 第三层 | Lyra 实例（项目真实代码） | 落地"怎么用" |

规则：
- 每个技术点标注 `(详见 [[教程页]])`
- 发现知识库未覆盖的领域 → 主动建议创建新教程
- 回答应引导用户到完整教程页深入学习

### 教程系列组织原则

- 每个教程系列在 `30-tutorials/<slug>/` 下
- 有 `_series.yaml` 定义学习路径、难度、前置条件
- 系列内文档按序号编排（`00` = 概览，`01`-`NN` = 具体课时）
- 每篇教程页必须标注前置知识（`prerequisites` 字段）
- Lyra 案例分析推荐放在系列末尾

## 写 Wiki 规范

### 创建新页面

1. 检查是否已存在类似页面（70% 重合 → 更新，否则创建）
2. 选择合适的目录（参见 `.wiki-schema.md`）
3. 必须包含完整的 frontmatter（**含 `last_synced` 和 `last_verified`，创建时填当天日期**）
4. 教程类型（`tutorial` / `guide` / `reference` / `case-study`）不要求 anchors
5. Lyra 模块类型（`module` / `subsystem`）必须有 anchors
6. 更新 `Docs/index.md` 和 `Docs/log.md`

### Frontmatter 规范

**通用字段**（所有 wiki 页）：

```yaml
---
id: 30-tutorials/gas/02-ga-execution-flow  # 等于文件路径（去前后缀）
type: tutorial                              # 见 type 枚举
status: current                             # current | draft | stale | deprecated
language: zh
owner: ai                                   # ai | human | mixed
last_synced: 2026-05-17
tags: [GAS, GameplayAbility]
---
```

**教程额外字段**（`30-tutorials/` 下）：

```yaml
titile: GE属性捕获（UE5.7)      #文章标题
series: gas                    # 所属系列 slug
lesson_index: 2                # 系列内序号
difficulty: intermediate       # beginner | intermediate | advanced
prerequisites:                 # 前置知识
  - "[[30-tutorials/gas/01-GA简介与配置]]"
engine_sources:                # 引擎源码参考路径
  - path: Engine/Plugins/Runtime/GameplayAbilities/...
    description: GA 执行核心
lyra_sources:                  # Lyra 项目源码路径
  - path: Source/LyraGame/AbilitySystem/...
    description: Lyra 的 GA 扩展
```

**Type 枚举**：

| type | 用途 | 目录 |
|------|------|------|
| `tutorial` | 教程课时 | `30-tutorials/` |
| `guide` | 概览/导航 | `30-tutorials/*/00-overview` |
| `case-study` | Lyra 案例分析 | `30-tutorials/*/XX-lyra-*` |
| `module` | Lyra 类文档 | `20-modules/` |
| `subsystem` | Lyra 子系统 | `10-architecture/subsystems/` |
| `runbook` | 操作手册 | `40-runbooks/` |
| `reference` | 外部参考 | `50-references/` |
| `adr` | 决策记录 | `60-decisions/` |
| `topic` | 横切主题 | `70-topics/` |
| `gotcha` | 已知坑 | `80-gotchas/` |

### 更新现有页面

1. 读取现有页面内容
2. 在合适的位置添加/修改内容
3. 更新 `last_synced` 和 `last_verified`
4. 重大变更考虑标记旧版 `stale` 并创建新版
5. 更新 `Docs/log.md`

## Log 规范

> **任何写入知识库的操作完成后，必须在 `/Docs/log.md` 追加记录。**

- **文件路径**：固定为 `/Docs/log.md`（**不允许**写到其他路径，如 `Docs/00-meta/log.md`）
- **写入方式**：append-only，新条目追加到文件末尾
- **标题格式**：`## [YYYY-MM-DD] <action-type> | 简短描述 → [[<wikilink>]]`
  - `action-type`：`create-series` | `evolve-series` | `ingest` | `crystallize` | `digest` | `lint` | `fix`
- **正文格式**：markdown 无序列表，常见字段：
  - `- **系列篇数**：N 篇`（教程系列适用）
  - `- **调研模式**：🚀 快速模式 / 🔬 深度解析模式`（create-series 适用）
  - `- **来源素材**：...`
  - `- **摘要**：1-2 句话`
  - `- **文件列表**：...`
  - `- **关联更新**：...`（index.md、learning-paths.md 等）
  - `- **关键技术要点**：...`
  - `- **lint 验证**：0 errors`
- **分隔**：条目之间保留一个空行；文件末尾保留 `---` 分隔线

## 工作流路由

| 用户意图 | 工作流 |
|---------|--------|
| "XX 是什么"、"帮我理解 XX" | **teach** |
| "分析 XX 源码"、"trace 调用链" | **source-trace** |
| "创建 XX 技术专题" | **create-series** |
| "review XX 系列"、"审查教程质量" | **review-series** |
| "项目里 X 在哪" | **query** |
| 给 URL / 外部文章 / "消化这篇" | **ingest** |
| "把这次对话沉淀进 wiki" | **crystallize** |
| "深度分析 X"、"对比 X 和 Y" | **digest** |
| "check 知识库" | **lint** |

## Stale 处理

### 何时标记为 Stale

- 引擎版本升级后，文档描述的 API 已变化
- Lyra 代码重构后，anchor 指向的文件已变化（`anchor-changed` lint 检测）
- `last_synced` 超过 180 天未更新

### 处理流程

1. 标记 `status: stale`
2. 在页面顶部添加警告
3. 通知用户需要 re-verify
4. 确认不再适用 → 标记 `deprecated`

## 应急流程

| 问题 | 处理 |
|------|------|
| 断链 | 检查拼写 → 建新页 or 修 link → 更新 index |
| 孤儿页 | 检查是否归类错误 → 补 inbound link or 合并 |
| 内容与代码矛盾 | 以代码为准 → 更新 wiki → 标注变更原因 |
| 重复页面 | 合并到更完整的那页 → 旧页标 `deprecated` |

## 图示规范

- **必须**优先 `mermaid` 代码块
- **禁止**新增 ASCII art（树 / 框 / 流程箭头）
- 已知例外：目录树 / 真实日志输出 / 4 行内极简流程
- 详见 [[00-meta/conventions]] §9

## 提交规范

- Commit message 中文为主，遵循 Conventional Commits 格式
- `type` 用英文（`feat` / `fix` / `docs` / `refactor` / `chore`）
- `scope` 用英文 slug（`wiki` / `tutorial` / `lint`）
- `subject` 用中文
- 固定术语保留英文：ADR / lint / commit / branch 等
- 详见 [[00-meta/conventions]]

## 相关页面

- [[.wiki-schema]] - 知识库 schema（目录、命名、字段定义）
- [[00-meta/learning-paths]] - 学习路线总览
- [[00-meta/conventions]] - 项目约定
- [[00-meta/glossary]] - 项目术语表

---
> 最后更新：2026-05-19（引擎路径解析改为脚本化：根目录 `get_engine_root.{ps1,bat,sh}`）
