# terminal-server (dev-only)

WebSocket + PTY 桥接进程，为 `web-app` 教程页底部的嵌入式终端面板提供本机 shell 能力。  
**仅用于本地开发**。`astro build` 不会打包它，发布包 (`lyra-kb-*.tar.gz`) 不包含本目录任何代码。

详细决策见：[`Docs/60-decisions/0003-dev-only-web-terminal.md`](../../Docs/60-decisions/0003-dev-only-web-terminal.md)

---

## 工作机制

```
浏览器 (http://localhost:4321)
    │
    │  ws://127.0.0.1:4322  (Origin 校验，无 token)
    ▼
terminal-server (本进程)
    │
    │  node-pty spawn shell, cwd = <repo root>
    ▼
zsh -l  /  pwsh
```

- macOS / Linux：默认 `$SHELL -i`（interactive，非 login，启动更快）；设 `LYRA_TERMINAL_LOGIN_SHELL=1` 切回 login。
- Windows：默认 `pwsh.exe` → `powershell.exe`。可通过 `LYRA_TERMINAL_SHELL` 切到 Git Bash 或 cmd（见下方）。
- PTY 默认工作目录为**仓库根目录**（`web-app/` 的父目录），便于 Claude Code 读取 `.claude/`、MCP 配置与 `Docs/` 知识库。

### 切换 shell（不修改代码）

通过环境变量 `LYRA_TERMINAL_SHELL` 可指定 shell，**默认依然是 PowerShell**：

| 值 | 对应 shell |
|---|---|
| 未设置（默认） | Windows: PowerShell；Unix: `$SHELL` |
| `powershell` / `pwsh` | Windows PowerShell（pwsh 优先） |
| `cmd` | Windows cmd.exe |
| `gitbash` / `bash` | Git Bash（自动从 Program Files / PATH 检测） |
| 绝对路径（如 `C:\msys64\usr\bin\bash.exe`） | 直接使用该可执行文件 |

启动时临时切：

```powershell
# Windows PowerShell
$env:LYRA_TERMINAL_SHELL = "gitbash"; .\start.bat
```

```bash
# macOS / Linux 用 fish 之类
LYRA_TERMINAL_SHELL=/opt/homebrew/bin/fish ./start.sh
```

永久切（Windows 示例）：在 `start.bat` 第 1 行后加 `set LYRA_TERMINAL_SHELL=gitbash`。

如果指定的 shell 找不到，会**自动回退**到默认 PowerShell 链，不会启动失败。

## 启动

通常由 `web-app/start.sh` / `start.bat` 自动并行启动，无需手动操作。

如需独立调试：

```bash
cd web-app/terminal-server
pnpm install        # 仅首次需要，会拉 node-pty 的 prebuild
pnpm start
```

控制台会打印：

```
[terminal-server] ready on ws://127.0.0.1:4322  (cwd=<repo root>, platform=darwin)
```

## 安全声明

服务**不使用 token**，依赖以下两道闸做单用户本地开发场景的访问控制：

- 仅监听 `127.0.0.1`，不接受外网/局域网连接
- 校验 `Origin` 必须为 `http://localhost:<dev port>` 或 `http://127.0.0.1:<dev port>`

**禁止以下做法**：

- 用 `--host 0.0.0.0` 或反向代理把 4322 暴露到公网/局域网
- 在多用户/共享主机上长期保留进程
- 通过浏览器扩展 / 第三方页面发起跨源请求时，刻意伪造 Origin 头

如需更严格的访问控制（团队共享开发机等），可重新启用 token 校验：在 `index.mjs` 的 upgrade 处理里加回 `Sec-WebSocket-Protocol` 校验。

## 端口

- 默认 `4322`（环境变量 `LYRA_TERMINAL_PORT` 可覆盖）
- 端口被占用时直接退出（不再自动 +1，避免前端连不上）
- Astro dev 端口默认 `4321`（环境变量 `LYRA_DEV_PORT` 可覆盖）

## 故障排查

| 现象 | 处理 |
|---|---|
| `pnpm install` 卡在 `node-pty` | 切镜像 `pnpm config set registry https://registry.npmmirror.com`，或用 `npm_config_node_pty_binary_host_mirror` 指定 prebuild 镜像 |
| Windows 终端中文乱码 | 已在连接建立后自动 `chcp 65001`，仍乱码请检查 PowerShell 字体 |
| `claude` 命令找不到 | 在系统终端确认 `which claude` / `where claude`，并确保安装路径在登录 shell 的 PATH 中 |
| 端口 4322 被占用 | 关闭占用进程，或 `LYRA_TERMINAL_PORT=4323 ./start.sh`，并通过 `window.__LYRA_TERMINAL_WS = 'ws://127.0.0.1:4323'` 让前端跟随 |
| 前端 overlay 显示"连接失败" | terminal-server 未启动；执行 `cd web-app/terminal-server && pnpm start` 看错误 |
