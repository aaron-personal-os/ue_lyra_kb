/**
 * Lyra Wiki — Dev-only Terminal Server
 *
 * WebSocket + node-pty bridge for the embedded terminal in the knowledge-base
 * web app. Intended ONLY for local development; launched by start.sh /
 * start.bat, NOT shipped in the published static bundle.
 *
 * Security model (see ADR-0003):
 *  - Binds 127.0.0.1 only (refuses public exposure).
 *  - Origin must be http://localhost:<dev-port> or http://127.0.0.1:<dev-port>.
 *  - No token: single-user local dev, the loopback bind + Origin check
 *    already suffice. Do NOT expose this port via tunnels/reverse proxies.
 */

import { WebSocketServer } from 'ws';
import * as pty from 'node-pty';
import { createServer } from 'node:http';
import { existsSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import os from 'node:os';

const __dirname = dirname(fileURLToPath(import.meta.url));

// web-app/ root (parent of terminal-server/)
const WEB_APP_ROOT = resolve(__dirname, '..');
// Repository root (parent of web-app/) — PTY default cwd, per ADR-0003
const REPO_ROOT = resolve(WEB_APP_ROOT, '..');

const PORT = Number(process.env.LYRA_TERMINAL_PORT) || 4322;
const HOST = '127.0.0.1';
const DEV_PORT = Number(process.env.LYRA_DEV_PORT) || 4321;
const ALLOWED_ORIGINS = new Set([
  `http://localhost:${DEV_PORT}`,
  `http://127.0.0.1:${DEV_PORT}`,
]);
const WS_PROTOCOL = 'lyra-terminal-v1';

// ---------- Shell selection ----------

/**
 * Resolve a Git Bash executable path on Windows.
 * Looks at $LYRA_TERMINAL_SHELL when an absolute path is given, then
 * %ProgramFiles%, %ProgramFiles(x86)%, %LocalAppData% and PATH for a
 * standard "Git for Windows" install.
 */
function findGitBash() {
  // 1) Standard install paths
  const candidatePaths = [];
  for (const base of [
    process.env['ProgramFiles'],
    process.env['ProgramFiles(x86)'],
    process.env.LOCALAPPDATA && `${process.env.LOCALAPPDATA}\\Programs`,
  ]) {
    if (!base) continue;
    candidatePaths.push(`${base}\\Git\\bin\\bash.exe`);
    candidatePaths.push(`${base}\\Git\\usr\\bin\\bash.exe`);
  }
  for (const p of candidatePaths) {
    if (existsSync(p)) return p;
  }
  // 2) Fall back to PATH (sometimes user puts Git\bin in PATH)
  const onPath = which('bash.exe');
  if (onPath) return onPath;
  return null;
}

function pickShellCandidates() {
  // Optional explicit override applies to BOTH platforms.
  // Accepted values:
  //   - "powershell" / "pwsh"    → Windows: prefer PowerShell 7 then 5
  //   - "cmd"                    → Windows: prefer cmd.exe
  //   - "gitbash" / "bash"       → Windows: prefer Git Bash
  //   - "/abs/path/to/shell"     → use that shell verbatim
  // Unknown values fall through to the platform default chain.
  const override = (process.env.LYRA_TERMINAL_SHELL || '').trim();

  if (process.platform === 'win32') {
    const list = [];

    const tryAdd = (file, args = []) => {
      if (file && existsSync(file) && !list.find((c) => c.file === file)) {
        list.push({ file, args });
      }
    };

    // Helper: PowerShell 7 then Windows PowerShell.
    const addPowerShell = () => {
      const pwsh = which('pwsh.exe') || which('pwsh');
      if (pwsh) tryAdd(pwsh, []);
      tryAdd('powershell.exe', ['-NoLogo']);
    };
    const addCmd = () => {
      if (process.env.COMSPEC) tryAdd(process.env.COMSPEC, []);
    };
    const addGitBash = () => {
      const bash = findGitBash();
      if (bash) {
        // -i for interactive (loads ~/.bashrc); avoid -l so Git Bash starts
        // fast — login shell on Windows pulls in /etc/profile chain.
        tryAdd(bash, ['-i']);
      }
    };

    // Apply override first (preferred slot).
    switch (override.toLowerCase()) {
      case '': break;
      case 'powershell':
      case 'pwsh':
        addPowerShell();
        break;
      case 'cmd':
        addCmd();
        break;
      case 'gitbash':
      case 'bash':
        addGitBash();
        break;
      default:
        // Treat as an explicit path. Args left to the user's responsibility.
        if (existsSync(override)) tryAdd(override, []);
        break;
    }

    // Then the default fallback chain so the user always gets *something*.
    addPowerShell();
    addCmd();
    addGitBash(); // last resort: use Git Bash if installed and PS missing
    return list;
  }

  // ---- Unix ----
  // Prefer NON-login interactive shell to keep startup fast.
  // Login shells run extra files (.zprofile, /etc/zprofile) that often pull
  // in slow tools like pyenv-virtualenv with multi-second rehash locks.
  // Set LYRA_TERMINAL_LOGIN_SHELL=1 to opt back in if your PATH truly lives
  // in login-only files.
  const wantLogin = process.env.LYRA_TERMINAL_LOGIN_SHELL === '1';
  const args = wantLogin ? ['-l'] : ['-i'];
  const list = [];

  // Explicit override path (Unix users may e.g. point at fish / nu)
  if (override && existsSync(override)) {
    list.push({ file: override, args });
  }

  const envShell = process.env.SHELL;
  if (envShell && existsSync(envShell) && !list.find((c) => c.file === envShell)) {
    list.push({ file: envShell, args });
  }
  for (const fallback of ['/bin/zsh', '/bin/bash', '/bin/sh']) {
    if (existsSync(fallback) && !list.find((c) => c.file === fallback)) {
      list.push({
        file: fallback,
        args: fallback === '/bin/sh' ? [] : args,
      });
    }
  }
  return list;
}

function which(cmd) {
  const sep = process.platform === 'win32' ? ';' : ':';
  const exts = process.platform === 'win32'
    ? (process.env.PATHEXT || '.EXE;.CMD;.BAT').split(';')
    : [''];
  const dirs = (process.env.PATH || '').split(sep);
  for (const dir of dirs) {
    if (!dir) continue;
    for (const ext of exts) {
      const candidate = resolve(dir, cmd + ext);
      try {
        if (existsSync(candidate)) return candidate;
      } catch {}
    }
  }
  return null;
}

// ---------- HTTP server (used only to upgrade to WS) ----------

const httpServer = createServer((req, res) => {
  if (req.url === '/__terminal/health') {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ ok: true, version: '0.2.0' }));
    return;
  }
  res.writeHead(404);
  res.end();
});

const wss = new WebSocketServer({ noServer: true });

httpServer.on('upgrade', (req, socket, head) => {
  // Disable Nagle so single-byte writes (e.g. lone Esc, Ctrl-C) leave the
  // socket immediately. This matters in interactive sessions: vim's
  // `ttimeoutlen` is short (often 10-50ms) and Nagle can delay an Esc
  // packet enough to make the user think they have to press it twice.
  try { socket.setNoDelay(true); } catch {}
  // Origin check — refuse anything not coming from the dev server.
  const origin = req.headers.origin;
  if (!origin || !ALLOWED_ORIGINS.has(origin)) {
    socket.write('HTTP/1.1 403 Forbidden\r\n\r\n');
    socket.destroy();
    return;
  }
  // Subprotocol negotiation: accept only the project-specific protocol.
  const protocols = (req.headers['sec-websocket-protocol'] || '')
    .split(',')
    .map((s) => s.trim())
    .filter(Boolean);
  if (!protocols.includes(WS_PROTOCOL)) {
    socket.write('HTTP/1.1 400 Bad Request\r\n\r\n');
    socket.destroy();
    return;
  }
  wss.handleUpgrade(req, socket, head, (ws) => {
    wss.emit('connection', ws, req);
  });
});

// ---------- WebSocket / PTY bridge ----------

wss.on('connection', (ws) => {
  const candidates = pickShellCandidates();
  const cols = 100;
  const rows = 30;

  let term = null;
  let usedShell = null;
  const errors = [];

  for (const c of candidates) {
    try {
      term = pty.spawn(c.file, c.args, {
        name: 'xterm-256color',
        cols,
        rows,
        cwd: REPO_ROOT,
        env: {
          ...process.env,
          TERM: 'xterm-256color',
          COLORTERM: 'truecolor',
          LYRA_WIKI_TERMINAL: '1',
        },
      });
      usedShell = c;
      break;
    } catch (err) {
      errors.push(
        `  - ${c.file} ${c.args.join(' ')}  →  ${
          err && err.message ? err.message : String(err)
        }${err && err.code ? ` (code=${err.code})` : ''}`
      );
    }
  }

  if (!term) {
    const msg =
      'Failed to spawn shell. Tried:\n' +
      (errors.length ? errors.join('\n') : '  (no candidates)') +
      `\nplatform=${process.platform} arch=${process.arch} node=${process.version} SHELL=${process.env.SHELL || '(unset)'}`;
    console.error('[terminal-server]', msg);
    try {
      ws.send(JSON.stringify({ type: 'error', message: msg }));
    } catch {}
    ws.close();
    return;
  }

  console.log(
    `[terminal-server] spawned ${usedShell.file} ${usedShell.args.join(' ')} (cwd=${REPO_ROOT})`
  );

  ws.send(
    JSON.stringify({
      type: 'ready',
      cwd: REPO_ROOT,
      shell: usedShell.file,
      platform: process.platform,
    })
  );

  if (process.platform === 'win32') {
    term.write('chcp 65001 > $null\r');
  }

  term.onData((data) => {
    if (ws.readyState === ws.OPEN) ws.send(data);
  });

  term.onExit(({ exitCode, signal }) => {
    if (ws.readyState === ws.OPEN) {
      ws.send(JSON.stringify({ type: 'exit', exitCode, signal: signal ?? null }));
      ws.close();
    }
  });

  ws.on('message', (data, isBinary) => {
    if (isBinary) {
      term.write(data);
      return;
    }
    const text = data.toString('utf8');
    if (text.startsWith('{')) {
      try {
        const msg = JSON.parse(text);
        if (msg.type === 'resize' && Number.isFinite(msg.cols) && Number.isFinite(msg.rows)) {
          try { term.resize(Math.max(1, msg.cols | 0), Math.max(1, msg.rows | 0)); } catch {}
          return;
        }
        if (msg.type === 'input' && typeof msg.data === 'string') {
          term.write(msg.data);
          return;
        }
      } catch {
        // fall through to raw write
      }
    }
    term.write(text);
  });

  ws.on('close', () => {
    try { term.kill(); } catch {}
  });
});

// ---------- Listen ----------

httpServer.on('error', (err) => {
  if (err && err.code === 'EADDRINUSE') {
    console.error(
      `[terminal-server] port ${PORT} is already in use. ` +
      `Set LYRA_TERMINAL_PORT to override.`
    );
  } else {
    console.error('[terminal-server] http error:', err);
  }
  process.exit(1);
});

httpServer.listen(PORT, HOST, () => {
  console.log(
    `[terminal-server] ready on ws://${HOST}:${PORT}  (cwd=${REPO_ROOT}, platform=${os.platform()})`
  );
});

// ---------- Graceful shutdown ----------

['SIGINT', 'SIGTERM', 'SIGHUP'].forEach((sig) => {
  process.on(sig, () => process.exit(0));
});
