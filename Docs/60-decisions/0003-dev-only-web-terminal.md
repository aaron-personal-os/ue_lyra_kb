---
id: 60-decisions/0003-dev-only-web-terminal
type: adr
status: proposed
language: zh
owner: human
decided_at: 2026-05-20
decided_by: robert
anchors: []
supersedes: []
superseded_by: []
related:
  - "[[60-decisions/0001-knowledge-base-web-app]]"
  - "[[60-decisions/0002-web-app-ui-enhancements]]"
sources: []
last_synced: 2026-05-20
last_verified: 2026-05-20
tags: [adr, web-app, terminal, xterm, node-pty, claude-code, dev-only]
---

# ADR-0003：Web 应用嵌入式开发终端（dev-only）

> 在 web-app 教程页底部嵌入 VSCode 风格终端面板，通过独立 dev-only 进程桥接本机 PTY，运行 Claude Code CLI 对知识库提问；该能力不进发布包。

## 背景 (Context)

ADR-0001 / ADR-0002 已交付了一个纯静态的 Astro 知识库 Web 应用，发布形态是 `lyra-kb-YYYYMMDD.tar.gz` 解压即用。在实际阅读教程时出现新的诉求：

1. **边读边问**：阅读 `30-tutorials/` 时希望直接在页面内向 Claude Code 提问关于当前教程的内容，不希望切到另一个终端窗口打断阅读流
2. **本地 Agent 上下文**：Claude Code 的 Agent / MCP / `.claude/` 配置在仓库根目录，提问需要在项目根目录下发起，才能让 Agent 自动读取知识库
3. **跨平台**：开发者同时在 macOS 和 Windows 上使用
4. **不污染发布物**：终端是给本地开发者用的工具，对外分发的知识库包必须维持现有"零运行时依赖、解压即用"的形态，否则破坏 ADR-0001 的「一键化」承诺

ADR-0001 Phase 2 已为此预留 "Web Terminal（xterm.js + node-pty + WebSocket）— Astro SSR 模式支持"，但当时未明确实现路径与发布隔离策略。本 ADR 收敛这两件事。

## 决策 (Decision)

### 一、总体架构：能力层与 UI 层解耦

```text
浏览器 (http://localhost:4321)
  ┌─────────────────────────────────────────────┐
  │ Astro 静态页 + xterm.js Island              │
  │   <TerminalPanel client:idle />             │
  │      ⇅  WebSocket (ws://127.0.0.1:4322)     │
  └─────────────────────────────────────────────┘
                       │
                       ▼
  ┌─────────────────────────────────────────────┐
  │ terminal-server  (dev-only, Node 进程)      │
  │   ws + node-pty  →  spawn shell             │
  │   cwd = <repo root>                         │
  │   token 校验 + Origin 校验                  │
  └─────────────────────────────────────────────┘
```

- **能力层**：`web-app/terminal-server/` 是**完全独立的 Node 进程**，监听 `127.0.0.1:4322`，负责 PTY + WebSocket 桥接
- **UI 层**：`<TerminalPanel />` 是 React Island，挂在 `TutorialLayout.astro` 底部
- 两层只通过 WebSocket 通信，能力层进程不存在时 UI 自动隐藏入口

### 二、UI 形态：嵌入式底部面板（VSCode 风格）

固定挂在教程页底部，与正文共存：

```text
┌──────────────────────────────────────────┐
│ Hero / Tutorial Content                  │
│                                          │
├──────────────────────────────────────────┤
│ ▼ Terminal   [+ new tab] [─ min] [✕]    │  ← 可拖拽调整高度
│ $ claude "解释一下 GAS 的 GE 生命周期"   │
│ ...                                      │
└──────────────────────────────────────────┘
```

- **位置**：`position: fixed; bottom: 0`，默认高度 30vh，记忆上次拖动高度（localStorage）
- **快捷键**：`Ctrl+J`（macOS 与 Windows 一致）切换显隐；`Ctrl+Shift+J` 新建 tab。  
  之所以从 VSCode 默认的 `Ctrl+`` ` 改为 `Ctrl+J`：项目目标用户主要在 macOS 下使用，反引号在 mac 中文/拼音输入法下不易触达；同时 `Ctrl+J` 也是 VSCode 内置的"切换面板"快捷键，肌肉记忆相通。
- **多 tab**：每个 tab 独立 PTY 会话
- **状态持久化**：显隐、高度、tab 列表写 localStorage
- **首次打开行为**：spawn shell 后自动 `cd <repo root>` 即停（不自动启动 `claude` 会话，避免无意义消耗 Claude 配额；用户需要时自行敲 `claude`）
- **拒绝形态**：独立 `/terminal` 路由（不能边读边问）、浮动悬浮窗（与开发者工具定位不符）

### 三、PTY 启动策略

| 项 | macOS | Windows |
|---|---|---|
| Shell | `/bin/zsh -l`（login shell，自动加载用户 PATH） | `pwsh.exe` 优先，回退 `powershell.exe` |
| **cwd** | **仓库根目录**（`web-app/` 的父目录） | 同左 |
| 环境变量 | 继承 `process.env` | 同左，PTY 启动后先发 `chcp 65001` 强制 UTF-8 |
| 终端尺寸 | 由前端 `fit-addon` 计算后通过 ws 控制消息同步 | 同左 |

**为什么 cwd 设为仓库根目录**：Claude Code 的 Agent 配置、`.claude/`、MCP 服务、知识库索引都挂在仓库根；只有从根目录启动 `claude` 才能正确加载这些配置完成"对知识库提问"。

### 四、与教程页的上下文联动

嵌入式形态独有的红利，UI 层实现，后端无感知：

- TerminalPanel 读取当前教程页的 `data-lesson-path`
- 终端 header 显示一行只读提示：`# Reading: 30-tutorials/01-gas/03-...md`
- 提供按钮「问 Claude 关于本页」→ 自动在输入行预填 `claude -p "请基于 Docs/30-tutorials/01-gas/03-...md 回答："`，用户补充问题后回车

### 五、安全模型

| 措施 | 说明 |
|---|---|
| 仅本机监听 | WebSocket 强制 bind `127.0.0.1`，禁止 `0.0.0.0` |
| Origin 校验 | ws upgrade 时校验 Origin = `http://localhost:4321` / `http://127.0.0.1:4321` |
| 子协议校验 | 必须协商 `Sec-WebSocket-Protocol: lyra-terminal-v1`（防止 WebSocket 跨源 CSRF 形式的随机连接） |
| 端口冲突 | 4322 被占用时直接退出（保持配置可预测，避免前端连错端口） |
| 文档警示 | terminal-server/README.md 明确："本地开发工具，禁止公网暴露、禁止反向代理" |

**不使用 Token**：单用户本地开发场景下，loopback bind + Origin 校验已经构成完整的访问闸；token 仅在共享主机/团队开发机等场景才有意义。如未来需要，可在 `index.mjs` 的 upgrade 处理中加回 `Sec-WebSocket-Protocol` token 校验，前端通过 `window.__LYRA_TERMINAL_TOKEN` 注入即可，UI 层无侵入。

不做的事：命令白名单、CWD 沙箱、用户权限隔离 —— 因为目标用户是开发者本人，过度限制会让 Claude Code 无法正常工作。

### 六、发布隔离（三道闸）

1. **代码隔离**：`terminal-server/` 与 `src/` 同级但不被 Astro 扫描；独立 `package.json`
2. **依赖隔离**：`node-pty` / `ws` 只出现在 `terminal-server/package.json`，**不进 `web-app/package.json`**
3. **构建期剔除**：UI 挂载用 `import.meta.env.DEV` 守卫，`astro build` 时整个组件被 tree-shake

```astro
---
// TutorialLayout.astro
import TerminalPanel from '@components/interactive/TerminalPanel';
---
{import.meta.env.DEV && <TerminalPanel client:idle />}
```

**验证**：`pnpm build` 后 `grep -r "xterm" dist/` 应为空；`dist/` 体积变化 ≤ 1KB。

### 七、文件清单

#### 新增

```
web-app/terminal-server/
  package.json                  (ws ^8, node-pty ^1)
  index.mjs                     ws server + PTY spawn + Origin 校验
  README.md                     安全声明 + 故障排查

web-app/src/components/interactive/
  TerminalPanel.tsx             xterm.js Island，固定连 ws://127.0.0.1:4322

web-app/src/styles/
  terminal.css                  VSCode 风格面板 + 拖拽手柄
```

前端不再依赖 Astro API endpoint 获取连接信息（不需要 SSR / hybrid 模式），整套体系仍是纯静态 + 旁路服务。

#### 修改

```
web-app/src/layouts/TutorialLayout.astro     底部挂 <TerminalPanel> + DEV 守卫
web-app/start.sh / start.bat                 并行启动 astro dev + terminal-server
web-app/setup.sh / setup.bat                 追加 cd terminal-server && pnpm install
```

#### 不修改

```
web-app/package.json          保持纯净
web-app/build.sh / build.bat  发布流程零变化
web-app/astro.config.mjs      不切 SSR，不加 adapter
```

### 八、依赖与版本

- `xterm` ^5.5 + `@xterm/addon-fit` + `@xterm/addon-web-links`
- `node-pty` ^1.0（含 macOS/Windows/Linux prebuild，无需本地编译）
- `ws` ^8.18

## 备选方案 (Alternatives)

### 方案 A：独立 `/terminal` 路由页面

- **优点**：实现最简单，全屏体验好，与教程页零耦合
- **缺点**：必须离开当前教程才能用终端，违背"边读边问"核心诉求
- **拒绝理由**：无法满足主场景；但保留为未来可选副形态（一行代码挂载即可）

### 方案 B：浮动悬浮窗（类似在线客服气泡）

- **优点**：不占阅读宽度，移动端友好
- **缺点**：窗口偏小、长输出体验差、气泡气质与"开发者终端"违和
- **拒绝理由**：定位不符

### 方案 C：把 web-app 切换为 SSR + 一体化部署

- **优点**：终端能力作为 web-app 一等公民，单进程启动
- **缺点**：发布包必须含 Node.js 运行时 + `node-pty` native 模块，包体积从 MB 级膨胀到 100MB+；GitHub Pages 等静态托管失效；安全模型恶化
- **拒绝理由**：破坏 ADR-0001 "一键化、零依赖"承诺；为本地开发工具付出对外分发的代价不合理

### 方案 D：浏览器内"假终端"（纯前端命令解析器）

- **优点**：零后端、零跨平台问题
- **缺点**：无法运行真实的 `claude` CLI，等于没满足需求
- **拒绝理由**：与需求直接冲突

## 后果 (Consequences)

### 正面

- 阅读教程时可直接调用 Claude Code 对知识库提问，上下文不切换
- terminal-server 完全 dev-only，发布包形态、体积、运行依赖、安全模型零变化
- xterm.js 代码在生产构建中被 tree-shake，`dist/` 干净
- UI 与后端解耦，未来可平滑增加副形态（`/terminal` 独立页、悬浮窗）而无需改后端
- 多 tab + 持久化让终端使用习惯接近 VSCode，零学习成本

### 负面 / 代价

- 新增一个常驻 Node 进程（dev 模式下与 Astro dev server 并行），需要在启动脚本里管理两个进程的生命周期
- 引入 `node-pty` native 模块依赖，初次 `pnpm install` 时可能因镜像问题拉不到 prebuild（需在 README 给出 fallback）
- 安全责任转移给开发者：必须避免把 4322 端口暴露到公网（README 警示 + 默认绑 127.0.0.1）
- 新增约 1-2 天开发量

### 中性影响

- 项目首次出现一个"非静态"的本地服务进程，未来 Phase 2 的其他后端能力（如知识图谱实时查询）可复用这套 dev-only 进程范式
- start/setup 脚本从"单进程"变为"双进程"模式，需要在 README 同步说明

## 验证 (Validation)

- ✅ **嵌入挂载**：教程页底部出现可拖拽折叠的终端面板，`Ctrl+`` ` 切换显隐
- ✅ **PTY cwd**：终端启动后 `pwd` / `cd` 显示仓库根目录
- ✅ **Claude 调用**：`claude "本仓库有哪些教程系列"` 能正常输出，证明 Agent 配置被加载
- ✅ **跨平台**：macOS（zsh）+ Windows（pwsh）均能启动 PTY，中文/Emoji 显示正常
- ✅ **多 tab**：开 2 个 tab 互不干扰，关闭 tab 后对应 PTY 进程被回收
- ✅ **上下文联动**：在 `30-tutorials/01-gas/...` 教程页打开终端，header 显示当前教程路径
- ✅ **发布隔离**：
  - `pnpm build` 产物 `grep -r "xterm\|node-pty\|TerminalPanel" dist/` 结果为空
  - `dist/` 体积变化 ≤ 1KB
  - 解压发布包 `tar.gz` 后 `serve.sh` 启动，浏览页面看不到终端入口
- ✅ **安全**：从局域网另一台机器访问 `ws://<dev机IP>:4322` 应被拒绝（Origin / bind 校验）
- **Review 时机**：MVP 完成后实际使用 1 周，评估是否需要补充会话恢复（断线重连后恢复历史输出）、是否需要副形态 `/terminal`

## 相关页面

- [[60-decisions/0001-knowledge-base-web-app]] — Web 应用基础架构（已规划 Web Terminal）
- [[60-decisions/0002-web-app-ui-enhancements]] — UI 美化与演示模式

---
> 最后更新：2026-05-20

<!-- nav:auto -->

---

**导航**: ← [[60-decisions/0002-web-app-ui-enhancements|0002-web-app-ui-enhancements]] · [[60-decisions/0004-knowledge-graph-query|0004-knowledge-graph-query]] →

<!-- /nav:auto -->
