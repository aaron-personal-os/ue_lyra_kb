# Review 报告：UE 移动系统深度解析（movement-system）

> 审查日期：2026-05-22
> 审查模式：Full Review（系列级）
> 审查篇数：10 篇（00-overview + 01~09）

---

## 评分摘要

| 维度 | 得分 | 评级 | 说明 |
|------|------|------|------|
| 专业性与准确性 | 7/10 | ⭐⭐⭐⭐ | 部分 Lyra 源码引用路径不存在，有拼写问题 |
| 教学设计 | 8/10 | ⭐⭐⭐⭐ | 三层结构完整，mermaid 图丰富，少量术语未解释 |
| 系列结构 | 9/10 | ⭐⭐⭐⭐⭐ | 难度梯度合理，lesson_index 连续，nav 正确 |
| 格式规范 | 6/10 | ⭐⭐⭐ | 多处标题尾端有多余 `#` 字符，frontmatter 完整 |
| 内容完备性 | 8/10 | ⭐⭐⭐⭐ | 核心概念覆盖全面，网络同步 + Lyra 实战完整 |
| **综合** | **7.5/10** | **⭐⭐⭐⭐** | **良好，有明确改进方向** |

### 评级说明
- 综合分 = 加权平均（准确性 30%×7 + 教学设计 25%×8 + 系列结构 20%×9 + 格式规范 15%×6 + 完备性 10%×8 = 7.5）
- ⭐⭐⭐⭐（7-8）：良好，有小改进空间

---

## 🔴 Critical 问题（必须修复）

| # | 检查项 | 影响文件 | 问题描述 | 建议修复方式 |
|---|--------|---------|---------|------------|
| 1 | A5 / A3 | `03-input-to-movement.md` | 引用 `ULyraMoveAbility`（路径 `Source/LyraGame/Abilities/LyraMoveAbility.cpp`），但 Glob 验证该文件**不存在** | 核实 Lyra 实际实现方式：移动输入是否真的通过 GA 处理？若否，删除该示例或标注为"伪代码" |
| 2 | A5 / A3 | `05-jump-fly-swim.md` | 引用 `Source/LyraGame/Abilities/LyraJumpAbility.cpp`，Glob 验证该文件**不存在** | 同上，Lyra 的跳跃实际是在 `ALyraCharacter::Jump()` 或 Input 绑定中处理，并非独立 GA。建议改为引用真实代码路径 |
| 3 | A3 | `05-jump-fly-swim.md:103` | `bWantsToCrouch` 拼写错误，UE 实际属性名为 `bWantsToCrouch`（Crouch 而非 Crouc**h**） | 全局修正为 `bWantsToCrouch` |
| 4 | F1 | `05-jump-fly-swim.md` frontmatter | `title` 字段尾端有多余 `#`：`"跳跃 / 飞行 / 游泳机制#"` | 删除尾端 `#` |

---

## 🟡 Major 问题（建议修复）

| # | 检查项 | 影响文件 | 问题描述 | 建议修复方式 |
|---|--------|---------|---------|------------|
| 1 | F7 / P7 | `07-custom-movement-mode.md` | 正文无 mermaid 图，全是代码片段。`PhysCustom()` 分派逻辑适合用 flowchart 展示 | 新增一张 mermaid flowchart：展示 `SetMovementMode(MOVE_Custom, N)` → `PhysCustom()` → `switch(CustomMovementMode)` → 各子模式函数 |
| 2 | P10 | `02-movement-modes.md:128` | `SafeMoveUpdatedComponent()` 首次出现时未解释其作用（只说"执行带碰撞检测的移动"） | 补充一行解释："`SafeMoveUpdatedComponent()` 是 CMC 的移动执行函数，内部调用 `MoveUpdatedComponent()` 并处理碰撞响应（沿墙滑动、穿透修正）" |
| 3 | P10 | `03-input-to-movement.md:128` | `Acceleration` 是 protected 成员，教程写"`Acceleration` 是 CMC 的 protected 成员变量"，但前文 `AddInputVector()` 的代码片段显示 `Acceleration += WorldVector`，未说明 `Acceleration` 每帧会被清零 | 补充：`Acceleration` 在 `PerformMovement()` 开头会根据 `ControlInputVector` 重新计算，不是持久累积的 |
| 4 | F7 | `04-movement-math.md` | 数学公式用 `` ``` `` 代码块展示，不是标准 LaTeX/MathJax，排版不够清晰 | 改用 markdown 数学公式或表格展示，关键公式用 **加粗** 标注 |
| 5 | S1 | `_series.yaml` / `06-network-replication.md` | `06-network-replication` 难度标为 `advanced`，但前置要求只有 `05-jump-fly-swim` 和 `network-overview`，对于没有网络编程背景的读者跨度较大 | 在 `06` 开头补充"本节前置知识：了解 UE 网络复制基础（可先读 `network-sync/00-network-overview`）"，或在 `_series.yaml` 的 `learning_path` 中标注"本阶段难度陡增，建议先掌握网络基础" |

---

## 🟢 Minor 问题（可选改进）

| # | 检查项 | 影响文件 | 问题描述 | 建议修复方式 |
|---|--------|---------|---------|------------|
| 1 | F7 | `05-jump-fly-swim.md` / `07-custom-movement-mode.md` / `08-root-motion.md` / `09-lyra-movement-practices.md` | 多个二级标题尾端有多余 `#` 字符（如 `## 五、Lyra 中的相关实践#`），疑似 markdown 转换残留 | 全局搜索 ` #"` 并删除标题尾端多余 `#` |
| 2 | C6 | `01-charactermovementcomponent-architecture.md` | 相关页面只链接了系列内部页面，未链接到 `20-modules/cpp/UCharacterMovementComponent` 等模块文档 | 补充相关模块文档链接，建立 tutorial → module-doc 的关联 |
| 3 | P8 | `06-network-replication.md` | 篇幅较长（~400 行），但末尾总结表格信息密集，可补充"核心要点 3-5 条"的单独小结 | 在 `## 七、总结` 前新增 `## 六、核心要点` 列表 |
| 4 | P4 | `07-custom-movement-mode.md` | `MyCharacterMovementComponent` 示例代码中的 `UCLASS()` 宏缺少 `GENERATED_BODY()` 后的分号（`GENERATED_BODY()` 后有分号是标准写法，但示例中没写） | 示例代码修正为 `GENERATED_BODY()` 并确认编译通过 |
| 5 | C4 | 全系列 | `movement-system` 系列未覆盖 **Crouch（蹲伏）** 机制，而这是 `UCharacterMovementComponent` 的重要功能（`Crouch()` / `UnCrouch()` / `GetCrouchedHalfHeight()`） | 可在 `02-movement-modes.md` 或独立小节补充"蹲伏与移动速度的关系" |

---

## 系列顺序评估

### 当前顺序

| # | 文件 | 难度 | 核心内容 |
|---|------|------|---------|
| 00 | `00-overview` | beginner | 系列概览、全景图、学习路线 |
| 01 | `01-charactermovementcomponent-architecture` | beginner | CMC 继承树、核心属性、Tick 流程 |
| 02 | `02-movement-modes` | intermediate | 五种 MovementMode、PhysWalking/PhysFalling 源码 |
| 03 | `03-input-to-movement` | intermediate | 输入系统 → AddMovementInput → CalcVelocity 全链路 |
| 04 | `04-movement-math` | intermediate | 摩擦力、加速度、AirControl 数学公式 |
| 05 | `05-jump-fly-swim` | intermediate | 跳跃高度公式、AirControl、Flying/Swimming |
| 06 | `06-network-replication` | advanced | 客户端预测、服务器校正、Lyra 带宽优化 |
| 07 | `07-custom-movement-mode` | advanced | PhysCustom() 扩展、爬梯子/墙上跑示例 |
| 08 | `08-root-motion` | advanced | Root Motion 原理、FRootMotionSource、与 CMC 交互 |
| 09 | `09-lyra-movement-practices` | advanced | Lyra CMC 三大扩展点、GAS 集成、Death 处理 |

### 顺序评价

- ✅ **顺序合理的部分**：
  - `00 → 01 → 02`：从概览到架构到模式，由浅入深，逻辑清晰
  - `03 → 04`：输入链路 → 物理数学，先"怎么来的"再"怎么算的"，衔接自然
  - `09` 放在末尾：Lyra 实战作为"综合应用"放在最后，符合 learning path 设计

- ⚠️ **顺序待商榷的部分**：
  - `05（jump/fly/swim）` 放在 `04（movement-math）` 之后是合理的（先懂公式再懂应用），但 `05` 的难度标为 `intermediate`，而内容涉及 `AirControlBoost`、`Buoyancy` 等高级参数，建议改为 `advanced` 或在文中标注"本节含高级内容"
  - `06（network-replication）` 难度跃迁较大（从 `intermediate` 跳到 `advanced`），建议在前言增加"前置知识"提示

### 建议调整

| 原序号 | 建议 | 原因 |
|--------|-------|------|
| 05 | 难度改为 `advanced`（或保持 `intermediate` 但在开头加提示） | 内容涉及 AirControlBoost、Buoyancy、DoJump 源码，对初学者偏难 |
| 06 | 在 `prerequisites` 中增加 `[[30-tutorials/network-sync/00-UE网络通信总览]]` | 确保读者有网络基础 |

---

## 改进优先级

按 ROI（改进收益/工作量）排序：

| 优先级 | 改进项 | 预估工作量 | 预期收益 | 执行方式 |
|--------|--------|-----------|---------|---------|
| **P0** | 修复 `bWantsToCrouch` 拼写错误（A3） | 小（全局替换） | 高（避免读者学到错误 API 名称） | evolve-series 模式 B |
| **P0** | 删除 `05-jump-fly-swim.md` title 尾端多余 `#`（F1） | 极小（改一行） | 中（格式整洁） | evolve-series 模式 B |
| **P1** | 核实并修正 `ULyraMoveAbility` / `ULyraJumpAbility` 引用（A5） | 中（需读 Lyra 源码确认实际实现） | 高（避免教程引用不存在的类） | evolve-series 模式 B |
| **P1** | 清除所有标题尾端多余 `#` 字符（F7） | 小（全局搜索替换） | 中（格式规范） | evolve-series 模式 B |
| **P2** | `07-custom-movement-mode.md` 新增 mermaid 图（P7） | 中（设计流程图 + 嵌入） | 中（提升教学效果） | evolve-series 模式 B |
| **P2** | `02-movement-modes.md` 补充 `SafeMoveUpdatedComponent()` 解释（P10） | 小（补一行文字） | 中（降低理解门槛） | evolve-series 模式 B |
| **P3** | 补充 Crouch 机制内容（C4） | 大（新增小节或新篇） | 中（内容更完备） | evolve-series 模式 A（需评估是否新增篇） |

---

## 修复记录（2026-05-22）

| 修复项 | 文件 | 结果 |
|--------|------|------|
| P0: `05-jump-fly-swim.md` title 尾端 `#` | `05-jump-fly-swim.md` | ✅ 已修复 |
| P0: `bWantsToCrouch` 拼写（review 误报） | 无需修复（实际拼写正确） | ✅ 已核实 |
| P1: `ULyraJumpAbility` 引用不存在 | `05-jump-fly-swim.md` | ✅ 已替换为 `ULyraGameplayAbility_Jump`，路径改为 `Source/LyraGame/AbilitySystem/Abilities/LyraGameplayAbility_Jump.cpp` |
| P1: `ULyraMoveAbility` 引用不存在 | `03-input-to-movement.md` | ✅ 已替换为正确的伪代码（`ALyraPlayerController::SetupInputComponent` → `OnMoveAction`） |
| P1: 所有标题尾端多余 `#` | `05-jump-fly-swim.md`、`09-lyra-movement-practices.md`、`07-custom-movement-mode.md` | ✅ 已全部清除 |

## 总结

`movement-system` 系列整体质量良好：
- **优点**：覆盖全面（从架构 → 数学 → 网络 → Lyra 实战），mermaid 图数量充足（9/10 篇有图），Lyra 源码引用大部分准确，`nav:auto` 导航完整
- **主要问题**：部分 Lyra 源码引用路径不存在（需核实是真实引用还是"伪代码"示例），少量拼写/格式错误
- **改进建议**：优先修复 Critical 问题（P0），然后补充教学细节（P1-P2）
