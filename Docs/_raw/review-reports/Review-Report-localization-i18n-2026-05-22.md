# Review 报告：UE 本地化与国际化从理论到实践

> 审查日期：2026-05-22
> 审查模式：Full Review
> 审查篇数：7 篇（00-overview ~ 06-lyra-localization-practice）

---

## 评分摘要

| 维度 | 得分 | 评级 | 说明 |
|------|------|------|------|
| 专业性与准确性 | 7/10 | ⭐⭐⭐ | 有 C++ 语法错误和 API 准确性问题 |
| 教学设计 | 8/10 | ⭐⭐⭐⭐ | 三层结构清晰，由浅入深合理 |
| 系列结构 | 7/10 | ⭐⭐⭐ | prerequisites 格式有误，nav 有跨系列错误 |
| 格式规范 | 6/10 | ⭐⭐⭐ | frontmatter 有非标准字段，wikilink 转义错误 |
| 内容完备性 | 8/10 | ⭐⭐⭐⭐ | 覆盖文本/资产/运行时/案例，较为完整 |
| **综合** | **7.2/10** | **⭐⭐⭐** | **良好，有明确改进方向** |

---

## 🔴 Critical 问题（必须修复）

| # | 检查项 | 影响文件 | 问题描述 | 建议修复方式 |
|---|--------|---------|---------|------------|
| 1 | F9 / F2 | 全套 7 篇 | `prerequisites` frontmatter 格式错误：写了 YAML 对象结构（`series:` / `minimum:`），应改为纯字符串数组 `[[id]]` 格式 | 统一改为 `prerequisites: ["[[30-tutorials/localization-i18n/XX]]"]` |
| 2 | F9 | `06-lyra-localization-practice.md` L379 | nav 块尾部错误引用了 `camera-system` 系列（`[[30-tutorials/camera-system/00-overview\|00-overview]]`），是明显的复制粘贴错误 | 改为 `[[index\|↑ index]]` 或移除该处引用 |
| 3 | A3 | `02-text-localization.md` L71 | C++ 代码 `#define LOCTEXT_NAMESPACE` 拼写错误，写为 `#define LOCTEXT_NAMESPACE`（少了 `d`） | 修正为 `#define LOCTEXT_NAMESPACE` |
| 4 | A3 | `05-runtime-language-switch.md` L119 | `GGameUserSettingsIni` 拼写错误，应为 `GGameUserSettingsIni`（少了 `i`） | 修正变量名 |
| 5 | A3 | `05-runtime-language-switch.md` L164 | `BindDynamic` 用法错误——`BindDynamic` 是蓝图宏，C++ 中应用 `BindUObject` 或 `TBaseDelegate`，且 `TextBlock_Health->TextDelegate.BindDynamic(...)` 语法不正确 | 修正为正确的 C++ 委托绑定语法，或改为蓝图节点说明 |

---

## 🟡 Major 问题（建议修复）

| # | 检查项 | 影响文件 | 问题描述 | 建议修复方式 |
|---|--------|---------|---------|------------|
| 1 | F9 | 全套 7 篇 | Related Pages 的 wikilink 写法有问题：渲染后出现了 `\[[` 这样的转义字符（如 `\[[30-tutorials/...]]`），说明 markdown 渲染时方括号被转义了 | 检查 wikilink 语法，确保是 `[[id\|label]]` 而非 `\[[id\|label]]` |
| 2 | P7 | `01-i18n-vs-l10n.md` | 有 mermaid 图，但核心机制页的 mermaid 图信息量偏低 | 在核心机制页（02、03、05）增加 1-2 个 Sequence Diagram |
| 3 | S7 / P5 | `00-overview.md` | 声称 Lyra 支持 "13 种语言"，但表格列出了 14 种（`en` + 13 其他 = 14 行，含 `es-419`） | 核实 Lyra 实际支持语言数，统一表述 |
| 4 | A6 | `02-text-localization.md` L155 | `FStringTableRegistry::Get().FindStringTable(...)` —— `FStringTableRegistry` 在 UE 5.x 中已被 `UStringTable` 直接加载取代，该 API 可能已废弃 | 验证 UE 5.7 中 String Table 的 C++ 访问方式，更新代码示例 |
| 5 | F1 | `00-overview.md` | `keywords` 不是 `wiki-schema.md` 定义的 frontmatter 标准字段（标准字段是 `tags`） | 移除 `keywords` 字段，或确认 schema 是否允许扩展 |
| 6 | S3 | `index.md` | `lesson_index: 99` 不符合系列内序号连续性（`_series.yaml` 定义 00-06），index.md 作为导航页不应占用 lesson_index | 将 index.md 的 `type` 改为 `guide` 并移除 `lesson_index`，或设为 `-1` |

---

## 🟢 Minor 问题（可选改进）

| # | 检查项 | 影响文件 | 问题描述 | 建议修复方式 |
|---|--------|---------|---------|------------|
| 1 | P6 | `02-text-localization.md` | 单个代码块最长约 30 行，符合规范（≤40），但部分代码块缺少 `[N]` 编号注释 | 在关键代码行增加 `[1]` `[2]` 编号 |
| 2 | P8 | `01-i18n-vs-l10n.md` | 每篇末尾有总结要点表格，但 `01-i18n-vs-l10n.md` 的总结偏短（5 条），可再充实 | 补充 1-2 条要点 |
| 3 | C5 | 全套 | 性能考量提及较少（仅 `02` 提到循环中的 FText 创建），可在 `05-runtime-language-switch.md` 中补充切换语言的性能影响说明 | 增加 "性能考量" 小节 |
| 4 | P10 | `04-asset-localization.md` | `EFlowDirectionPreference` 首次出现无解释（RTL 相关），`FlowDirectionPreference` 是 UMG 枚举 | 首次出现时加括号说明或链接到 glossary |
| 5 | F10 | 全套 | 外部链接用了 `[text](url)` 格式（正确），但 `00-overview.md` 的 UE 官方文档链接 URL 域名是 `dev.epicgames.com`（需核实是否为文档实际域名） | 核实 URL 有效性 |

---

## 系列顺序评估

### 当前顺序

| # | 文件 | 难度 | 核心内容 |
|---|------|------|---------|
| 00 | 00-overview | beginner | 全景图、系列导航 |
| 01 | 01-i18n-vs-l10n | beginner | I18n/L10n 概念区别 |
| 02 | 02-text-localization | intermediate | FText、String Table |
| 03 | 03-localization-dashboard | intermediate | 仪表盘、Gather Text |
| 04 | 04-asset-localization | intermediate | 音频/纹理本地化 |
| 05 | 05-runtime-language-switch | intermediate | 动态切换语言 |
| 06 | 06-lyra-localization-practice | intermediate | Lyra 完整案例分析 |

### 顺序评价

- ✅ **顺序合理的部分**：
  - 00 → 01：先概览再讲概念，符合认知顺序
  - 01 → 02：先理解概念再学 FText 技术细节，合理
  - 02 → 03：先学 FText 再学工具链，符合"先懂机制再学工具"的原则
  - 05 → 06：先讲运行时切换理论，再用 Lyra 案例巩固，合理

- ⚠️ **顺序待商榷的部分**：
  - `04-asset-localization`（资产本地化）放在 `05-runtime-language-switch`（运行时切换）之前是合理的（资产切换需要重启，运行时切换是高级话题），但读者可能会觉得 04 偏"冷门"，建议在教学设计中强调"资产本地化是大部分游戏的实际需求"

### 建议调整

无需调整顺序，当前顺序合理。

---

## 改进优先级

按 ROI（改进收益/工作量）排序：

| 优先级 | 改进项 | 预估工作量 | 预期收益 | 执行方式 |
|--------|--------|-----------|---------|---------|
| **P0** | 修复 `prerequisites` frontmatter 格式（全套） | 小（批量编辑） | 高（lint 才能通过） | evolve-series 模式 B |
| **P0** | 修复 `06` nav 块中的 camera-system 引用错误 | 极小（单行编辑） | 高（避免读者困惑） | evolve-series 模式 B |
| **P1** | 修复 C++ 代码中的拼写错误（3 处） | 小 | 高（专业性） | evolve-series 模式 B |
| **P1** | 修复 wikilink 转义问题（全套 Related Pages） | 中 | 高（链接可用性） | evolve-series 模式 B |
| **P2** | 验证 `FStringTableRegistry` API 准确性（UE 5.7） | 中（需查源码） | 中（准确性） | evolve-series 模式 B |
| **P2** | 统一 Lyra 支持语言数的表述 | 小 | 中（一致性） | evolve-series 模式 B |
| **P3** | 增加性能考量小节 | 中 | 中（完备性） | evolve-series 模式 A |

---

## 总结

该系列整体质量良好：
- **优点**：三层教学结构清晰（概念 → 机制 → Lyra 实例），mermaid 图用量充足，每篇有总结要点，Lyra 代码引用较丰富
- **主要问题**：frontmatter 格式不规范（`prerequisites` 写法错误、有非标准字段），少量 C++ 代码有拼写错误，nav 块有复制粘贴错误
- **建议**：优先修复 P0/P1 问题，再考虑 P2/P3 的内容改进
