#!/usr/bin/env python
"""
ue_python.py - UE Editor Python Remote Execution 桥接脚本

向运行中的 UE Editor 发送 Python 代码并返回执行结果。
基于 UE 内置的 Remote Execution 协议（UDP 发现 + TCP 执行）。

用法：
    python ue_python.py "import unreal; print(unreal.SystemLibrary.get_engine_version())"

退出码：0=成功, 1=执行错误, 2=连接失败

前置条件：
    1. UE Editor 已启用 Python Editor Script Plugin
    2. Editor Preferences > Python > Remote Execution 已开启
    3. 设置环境变量 UE_ENGINE_ROOT 指向引擎根目录
       set UE_ENGINE_ROOT=C:\\Program Files\\Epic Games\\UE_5.5\\Engine
"""
import sys
import os
import time
import platform

# 通过环境变量 UE_ENGINE_ROOT 指定引擎路径
ENGINE_ROOT = os.environ.get('UE_ENGINE_ROOT', '')

def _multicast_bind_address():
    """macOS 上 Remote Execution 发现通常需要 0.0.0.0，Windows 默认 127.0.0.1。"""
    override = os.environ.get('UE_PY_MULTICAST_BIND', '').strip()
    if override:
        return override
    if platform.system() == 'Darwin':
        return '0.0.0.0'
    return '127.0.0.1'

_RE_MODULE_PATH = os.path.join(ENGINE_ROOT, 'Plugins', 'Experimental',
                               'PythonScriptPlugin', 'Content', 'Python')

if not os.path.isfile(os.path.join(_RE_MODULE_PATH, 'remote_execution.py')):
    print("Error: cannot find UE's remote_execution.py", file=sys.stderr)
    print(f"  Searched: {_RE_MODULE_PATH}", file=sys.stderr)
    print("  Fix: set env UE_ENGINE_ROOT to your engine root path", file=sys.stderr)
    print("  Example: set UE_ENGINE_ROOT=C:\\Program Files\\Epic Games\\UE_5.5\\Engine", file=sys.stderr)
    sys.exit(2)

sys.path.insert(0, _RE_MODULE_PATH)
import remote_execution


def connect(timeout=6):
    """通过 UDP 发现运行中的 UE Editor 并建立 TCP 命令连接"""
    config = remote_execution.RemoteExecutionConfig()
    config.multicast_bind_address = _multicast_bind_address()
    re = remote_execution.RemoteExecution(config)
    re.start()
    deadline = time.time() + timeout
    while time.time() < deadline:
        if re.remote_nodes:
            break
        time.sleep(0.3)
    if not re.remote_nodes:
        re.stop()
        return None, "No UE Editor found. Is Remote Execution enabled?"
    re.open_command_connection(re.remote_nodes[0]['node_id'])
    return re, None


def run(re, code):
    """在 UE Editor 中执行代码，返回 (success: bool, output: str)"""
    result = re.run_command(code, unattended=True, exec_mode=remote_execution.MODE_EXEC_FILE)
    success = result.get('success', False)

    lines = []
    for entry in result.get('output', []):
        typ = entry.get('type', 'Info')
        txt = entry.get('output', '')
        if typ == 'Warning':
            if 'DeprecationWarning' in txt:
                continue
            lines.append('[WARN] ' + txt)
        elif typ == 'Error':
            lines.append('[ERROR] ' + txt)
        else:
            lines.append(txt)

    # 执行失败时，错误信息（traceback）在 result 字段
    cmd_result = result.get('result', '')
    if not success and cmd_result:
        lines.append(cmd_result)

    return success, '\n'.join(lines)


if __name__ == '__main__':
    if len(sys.argv) < 2 or len(sys.argv) > 3:
        print('Usage: python ue_python.py "<python_code>" [timeout_seconds]', file=sys.stderr)
        sys.exit(2)

    code = sys.argv[1]
    timeout = int(sys.argv[2]) if len(sys.argv) == 3 else 6

    re, err = connect(timeout)
    if err:
        print(err, file=sys.stderr)
        sys.exit(2)

    try:
        success, output = run(re, code)
        if output:
            print(output)
        sys.exit(0 if success else 1)
    finally:
        re.close_command_connection()
        re.stop()
