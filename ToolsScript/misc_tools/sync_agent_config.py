#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sync_agent_config.py
====================

一键复刻项目中 CodeBuddy 的 Agent 配置给 ClaudeCode / Codex / Cursor 使用。

实现思路
--------
通过建立「软链接（symlink）」让多个 AI 工具共享同一份配置源，
源是项目根目录下的 ``.codebuddy/``，目标分别是 ``.claude/`` / ``.codex/`` / ``.cursor/``。

- ``.codebuddy/`` 下的「子目录」级别按目录建软链接（而非整体目录，因为不同工具
  对子目录命名略有差异，需要做「子目录映射」）。
- 支持用 glob 模式排除部分子目录（或子目录内的单个文件，后者会回退为「把整个
  父目录物理复制，再单独排除那些文件」——本脚本默认仅按「顶层子目录」做软链，
  若排除模式命中的是更深层的文件/目录，会自动切换为「镜像复制 + 排除」模式）。

跨平台
------
- macOS / Linux：直接使用 ``os.symlink``。
- Windows：优先使用 ``os.symlink(target_is_directory=True)``（需开启开发者模式
  或以管理员身份运行），失败时自动回退到 ``mklink /J`` 创建目录 Junction。

排除配置
--------
默认的排除 glob 直接写在 ``DEFAULT_EXCLUDES`` 常量里（便于团队共识 & 纳入版本管理）。
命令行仍保留 ``--exclude`` 用于「临时追加」额外排除（不会覆盖 DEFAULT_EXCLUDES）。

根级 Agent 文件
---------------
项目根的 ``CODEBUDDY.md`` 会被软链到各工具约定的项目说明文件：
- ClaudeCode: ``CLAUDE.md``
- Codex:      ``AGENTS.md``
- Cursor:     ``AGENTS.md``

典型用法
--------
在项目根目录执行::

    python scripts/sync_agent_config.py                     # 使用内置 excludes
    python scripts/sync_agent_config.py --targets claude,codex
    python scripts/sync_agent_config.py --exclude 'skills/private-*'   # 追加额外排除
    python scripts/sync_agent_config.py --dry-run
    python scripts/sync_agent_config.py --force             # 覆盖已存在的目标
    python scripts/sync_agent_config.py --unlink            # 清除之前建立的软链接
"""

from __future__ import annotations

import argparse
import fnmatch
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable


# ---------------------------------------------------------------------------
# 目标工具定义
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class TargetSpec:
    """一个目标 AI 工具的目录约定。"""

    key: str                       # 命令行参数使用的 key
    root: str                      # 目标根目录名（相对项目根）
    # 源子目录名 -> 目标子目录名 的映射。
    # 若某个源子目录没在映射里，表示「同名直接软链」。
    subdir_map: dict[str, str] = field(default_factory=dict)
    # 项目根 CODEBUDDY.md 要链到「项目根下的哪个路径」。
    # 路径是相对项目根的相对路径（用 "/"），None 表示该工具不需要根级文档软链。
    root_md_target: str | None = None


TARGETS: dict[str, TargetSpec] = {
    # ClaudeCode: .claude/commands, .claude/skills, .claude/agents …
    #   根级 Agent 说明文件: CLAUDE.md（位于项目根）
    "claude": TargetSpec(
        key="claude",
        root=".claude",
        subdir_map={},  # 与 CodeBuddy 同名，直接映射
        root_md_target="CLAUDE.md",
    ),
    # Codex CLI: .codex/prompts（slash commands 叫 prompts）, .codex/skills
    #   根级 Agent 说明文件: AGENTS.md（位于项目根）
    "codex": TargetSpec(
        key="codex",
        root=".codex",
        subdir_map={
            "commands": "prompts",
        },
        root_md_target="AGENTS.md",
    ),
    # Cursor: .cursor/commands, .cursor/skills,
    "cursor": TargetSpec(
        key="cursor",
        root=".cursor",
        subdir_map={
        },
        root_md_target="AGENTS.md",
    ),
}

SOURCE_DIR_NAME = ".codebuddy"
SOURCE_ROOT_MD = "CODEBUDDY.md"  # 项目根的 Agent 总览文档（软链源）


# ---------------------------------------------------------------------------
# 默认排除配置（脚本内固定）
# ---------------------------------------------------------------------------
#
# Glob 路径是相对 .codebuddy/ 的路径，统一用正斜杠。
# 匹配时同时对「完整相对路径」和「basename」做 fnmatch。
# 命令行 --exclude 只是「追加」，不会覆盖下列默认值。
#
# 常见场景：
#   - 'commands/tmp.md'       —— 跳过某个临时/草稿命令
#   - 'skills/private-*'      —— 跳过前缀为 private- 的私有 skill
#   - '*/.DS_Store'           —— 系统噪声文件
DEFAULT_EXCLUDES: list[str] = [
]


# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------

IS_WINDOWS = os.name == "nt"


def log(msg: str, *, dry: bool = False) -> None:
    prefix = "[dry-run] " if dry else "[sync] "
    print(prefix + msg)


def warn(msg: str) -> None:
    print("[warn] " + msg, file=sys.stderr)


def err(msg: str) -> None:
    print("[error] " + msg, file=sys.stderr)


def match_any(path_rel: str, patterns: Iterable[str]) -> bool:
    """判断相对路径是否命中任一 glob。

    匹配时同时对「完整相对路径」和「basename」做 fnmatch，尽量宽松。
    路径统一用正斜杠。
    """
    norm = path_rel.replace(os.sep, "/")
    base = norm.rsplit("/", 1)[-1]
    for pat in patterns:
        p = pat.replace(os.sep, "/")
        if fnmatch.fnmatch(norm, p) or fnmatch.fnmatch(base, p):
            return True
    return False


def is_symlink_to(link: Path, expect_target: Path) -> bool:
    """link 是否是一个指向 expect_target 的软链接/Junction。"""
    try:
        if not link.exists() and not link.is_symlink():
            return False
        if link.is_symlink():
            return Path(os.readlink(link)).resolve() == expect_target.resolve()
        # Windows Junction 不被 is_symlink() 识别，用 resolve 比对
        if IS_WINDOWS and link.is_dir():
            return link.resolve() == expect_target.resolve()
    except OSError:
        return False
    return False


def remove_path(p: Path, dry: bool = False) -> None:
    if dry:
        log(f"remove {p}", dry=True)
        return
    if p.is_symlink() or p.is_file():
        p.unlink(missing_ok=True)
    elif p.is_dir():
        shutil.rmtree(p)


def _windows_junction(link: Path, target: Path) -> None:
    """Windows 下用 mklink /J 建立目录 Junction。"""
    # /J = 目录 Junction，不需要管理员权限
    subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(link), str(target)],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )


def make_symlink(link: Path, target: Path, *, is_dir: bool, dry: bool = False) -> None:
    """创建软链接，跨平台。target 用「相对 link 父目录」的相对路径，便于仓库移植。"""
    link.parent.mkdir(parents=True, exist_ok=True)
    try:
        rel_target = os.path.relpath(target, start=link.parent)
    except ValueError:
        # 跨盘（Windows 下）无法用相对路径，退回绝对路径
        rel_target = str(target.resolve())

    if dry:
        log(f"symlink {link}  ->  {rel_target}", dry=True)
        return

    try:
        os.symlink(rel_target, link, target_is_directory=is_dir)
        return
    except OSError as e:
        if not IS_WINDOWS:
            raise
        # Windows: 没开启开发者模式 / 不是管理员，symlink 会失败；回退到 junction
        if is_dir:
            warn(f"os.symlink 失败（{e}），回退到 Windows Junction (mklink /J)")
            _windows_junction(link, target)
        else:
            # 文件型 symlink 回退方案：复制文件
            warn(f"os.symlink 失败（{e}），回退到复制文件: {link}")
            shutil.copy2(target, link)


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------

def list_source_subdirs(src_root: Path) -> list[Path]:
    """.codebuddy 下的顶层子目录（只取目录）。"""
    return sorted([p for p in src_root.iterdir() if p.is_dir() and not p.name.startswith(".")])


def plan_and_apply(
    project_root: Path,
    targets: list[TargetSpec],
    excludes: list[str],
    dry: bool,
    force: bool,
) -> int:
    src_root = project_root / SOURCE_DIR_NAME
    if not src_root.is_dir():
        err(f"源目录不存在: {src_root}")
        return 2

    sub_dirs = list_source_subdirs(src_root)
    if not sub_dirs:
        warn(f"{src_root} 下没有可同步的子目录")
        return 0

    # 预先判断：是否存在「深层排除」（模式命中的不是顶层子目录本身，而是其内部）
    # 这类情况无法用「整个子目录一个 symlink」实现，需要镜像复制 + 排除。
    #
    # 仅看 pattern 字面会过度保守：例如 `*/.DS_Store` 的首段 `*` 可以匹配任何子目录名，
    # 静态判断会把每个顶层子目录都判成「可能有深层排除」，从而全部退化为 mirror，
    # 即便子目录里根本没有 .DS_Store。所以这里分两步：
    #   1) 先做廉价的静态可能性判定，若所有 pattern 都与该子目录无关，直接 False；
    #   2) 否则实扫一遍 sub，只有存在「真正被 excludes 命中」的内部条目才返回 True。
    def needs_mirror(sub: Path) -> bool:
        sub_name = sub.name
        maybe_deep = False
        for pat in excludes:
            p = pat.replace(os.sep, "/").strip("/")
            # 顶层就是这个子目录自身（或其 glob），不算深层
            if fnmatch.fnmatch(sub_name, p) or fnmatch.fnmatch(sub_name + "/", p):
                continue
            if "/" in p:
                first, _rest = p.split("/", 1)
                # 模式以 "<sub_name>/..." 开头，或首段 glob 能匹配 sub_name -> 可能深层
                if first == sub_name or fnmatch.fnmatch(sub_name, first):
                    maybe_deep = True
                    break
            else:
                # 不含 "/" 的纯 basename 模式（如 ".DS_Store"），可能命中任何层级的同名文件
                maybe_deep = True
                break

        if not maybe_deep:
            return False

        # 实扫源目录，只要存在一条被 excludes 命中的内部条目，就必须走 mirror
        for entry in sub.rglob("*"):
            rel_inside = entry.relative_to(sub).as_posix()
            if match_any(f"{sub_name}/{rel_inside}", excludes):
                return True
        return False

    rc = 0
    for target in targets:
        target_root = project_root / target.root
        log(f"=== target: {target.key}  ->  {target_root} ===")

        # 1) 处理项目根 CODEBUDDY.md -> 该工具约定的根级说明文件
        rc |= link_root_md(
            project_root=project_root,
            target=target,
            dry=dry,
            force=force,
        )

        # 2) 处理 .codebuddy 下的各个子目录
        for sub in sub_dirs:
            sub_name = sub.name

            # 顶层子目录直接被排除
            if match_any(sub_name, excludes) or match_any(sub_name + "/", excludes):
                log(f"skip (excluded): {SOURCE_DIR_NAME}/{sub_name}")
                continue

            mapped_name = target.subdir_map.get(sub_name, sub_name)
            link_path = target_root / mapped_name

            if needs_mirror(sub):
                rc |= mirror_copy(
                    src_dir=sub,
                    dst_dir=link_path,
                    excludes=excludes,
                    sub_name=sub_name,
                    dry=dry,
                    force=force,
                )
            else:
                rc |= link_subdir(
                    src_dir=sub,
                    link_path=link_path,
                    dry=dry,
                    force=force,
                )
    return rc


def link_root_md(
    project_root: Path,
    target: TargetSpec,
    *,
    dry: bool,
    force: bool,
) -> int:
    """把 项目根/CODEBUDDY.md 软链到 target 约定的根级说明文件位置。"""
    if not target.root_md_target:
        return 0

    src_md = project_root / SOURCE_ROOT_MD
    if not src_md.is_file():
        warn(f"跳过根级说明软链：{src_md} 不存在")
        return 0

    link_path = project_root / target.root_md_target

    if link_path.exists() or link_path.is_symlink():
        if is_symlink_to(link_path, src_md):
            log(f"ok (already linked): {link_path}")
            return 0
        if not force:
            err(
                f"目标已存在且不是指向 {SOURCE_ROOT_MD} 的软链: {link_path}\n"
                f"  使用 --force 覆盖，或用 --unlink 先清理。"
            )
            return 1
        remove_path(link_path, dry=dry)

    make_symlink(link_path, src_md, is_dir=False, dry=dry)
    if not dry:
        log(f"linked: {link_path}  ->  {src_md}")
    return 0


def link_subdir(src_dir: Path, link_path: Path, *, dry: bool, force: bool) -> int:
    """把 src_dir 作为整体，软链接到 link_path。"""
    # 已经是指向同一源的软链接 -> 幂等跳过
    if link_path.exists() or link_path.is_symlink():
        if is_symlink_to(link_path, src_dir):
            log(f"ok (already linked): {link_path}")
            return 0
        if not force:
            err(
                f"目标已存在且不是指向源的软链接: {link_path}\n"
                f"  使用 --force 覆盖，或用 --unlink 先清理。"
            )
            return 1
        remove_path(link_path, dry=dry)

    make_symlink(link_path, src_dir, is_dir=True, dry=dry)
    if not dry:
        log(f"linked: {link_path}  ->  {src_dir}")
    return 0


def mirror_copy(
    src_dir: Path,
    dst_dir: Path,
    excludes: list[str],
    sub_name: str,
    *,
    dry: bool,
    force: bool,
) -> int:
    """有深层排除时，退化为「在目标目录下，对子目录内每个条目逐一软链/跳过」。

    这样仍然保持软链接语义（单个文件也是软链接），而不是物理拷贝，以便源变化即时生效。
    """
    if dst_dir.exists() and not dst_dir.is_dir():
        if not force:
            err(f"目标已存在且不是目录: {dst_dir}，使用 --force 覆盖")
            return 1
        remove_path(dst_dir, dry=dry)

    if not dry:
        dst_dir.mkdir(parents=True, exist_ok=True)
    else:
        log(f"mkdir {dst_dir}", dry=True)

    rc = 0
    for entry in sorted(src_dir.iterdir()):
        rel = f"{sub_name}/{entry.name}"
        if match_any(rel, excludes) or match_any(entry.name, excludes):
            log(f"skip (excluded): {SOURCE_DIR_NAME}/{rel}")
            continue

        link_path = dst_dir / entry.name
        if link_path.exists() or link_path.is_symlink():
            if is_symlink_to(link_path, entry):
                log(f"ok (already linked): {link_path}")
                continue
            if not force:
                err(f"目标已存在: {link_path}，使用 --force 覆盖")
                rc = 1
                continue
            remove_path(link_path, dry=dry)

        make_symlink(link_path, entry, is_dir=entry.is_dir(), dry=dry)
        if not dry:
            log(f"linked: {link_path}  ->  {entry}")
    return rc


def do_unlink(project_root: Path, targets: list[TargetSpec], dry: bool) -> int:
    """删除之前建立的软链接（以及空壳目录、根级说明软链）。"""
    src_root = (project_root / SOURCE_DIR_NAME).resolve()
    src_md = (project_root / SOURCE_ROOT_MD).resolve() if (project_root / SOURCE_ROOT_MD).exists() else None
    rc = 0

    def _points_into_source(p: Path) -> bool:
        """p 解析后是否位于 .codebuddy/ 内，或等于 CODEBUDDY.md。"""
        try:
            real = p.resolve()
        except OSError:
            return False
        if src_md is not None and real == src_md:
            return True
        # real 是 src_root 或其后代
        cur = real
        while cur != cur.parent:
            if cur == src_root:
                return True
            cur = cur.parent
        return False

    for target in targets:
        target_root = project_root / target.root
        log(f"=== unlink target: {target.key}  ->  {target_root} ===")

        # 1) 根级说明软链（可能位于项目根或 .cursor/rules/ 内）
        if target.root_md_target:
            root_md_link = project_root / target.root_md_target
            if (root_md_link.is_symlink() or (IS_WINDOWS and root_md_link.is_file())) \
                    and _points_into_source(root_md_link):
                if dry:
                    log(f"would remove: {root_md_link}", dry=True)
                else:
                    try:
                        remove_path(root_md_link)
                        log(f"removed: {root_md_link}")
                    except OSError as e:
                        warn(f"移除失败 {root_md_link}: {e}")
                        rc = 1

        # 2) target_root 下指向源的软链
        if target_root.exists():
            for child in list(target_root.iterdir()):
                if not (child.is_symlink() or (IS_WINDOWS and (child.is_dir() or child.is_file()))):
                    continue
                if not _points_into_source(child):
                    continue
                if dry:
                    log(f"would remove: {child}", dry=True)
                else:
                    try:
                        remove_path(child)
                        log(f"removed: {child}")
                    except OSError as e:
                        warn(f"移除失败 {child}: {e}")
                        rc = 1

            # 若 target_root/<subdir> 是镜像模式创建的真实目录，尝试清理其内部软链并回收空目录
            for child in list(target_root.iterdir()):
                if child.is_dir() and not child.is_symlink():
                    for inner in list(child.iterdir()):
                        if (inner.is_symlink() or (IS_WINDOWS and (inner.is_dir() or inner.is_file()))) \
                                and _points_into_source(inner):
                            if dry:
                                log(f"would remove: {inner}", dry=True)
                            else:
                                try:
                                    remove_path(inner)
                                    log(f"removed: {inner}")
                                except OSError as e:
                                    warn(f"移除失败 {inner}: {e}")
                                    rc = 1
                    # 目录内清空了 -> 删掉
                    try:
                        if not any(child.iterdir()):
                            if dry:
                                log(f"would remove empty dir: {child}", dry=True)
                            else:
                                child.rmdir()
                                log(f"removed empty dir: {child}")
                    except OSError:
                        pass

            # target_root 本身若已空 -> 删除
            try:
                if target_root.exists() and not any(target_root.iterdir()):
                    if dry:
                        log(f"would remove empty dir: {target_root}", dry=True)
                    else:
                        target_root.rmdir()
                        log(f"removed empty dir: {target_root}")
            except OSError:
                pass
    return rc


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_targets(s: str) -> list[TargetSpec]:
    keys = [x.strip().lower() for x in s.split(",") if x.strip()]
    out = []
    for k in keys:
        if k not in TARGETS:
            raise argparse.ArgumentTypeError(
                f"未知目标: {k}；可选: {', '.join(TARGETS.keys())}"
            )
        out.append(TARGETS[k])
    return out


def build_arg_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        description="将 .codebuddy 的 Agent 配置通过软链接复刻给 ClaudeCode / Codex / Cursor。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    ap.add_argument(
        "--project-root",
        type=Path,
        default=Path.cwd(),
        help="项目根目录，默认当前工作目录",
    )
    ap.add_argument(
        "--targets",
        type=parse_targets,
        default=list(TARGETS.values()),
        help=f"目标工具，逗号分隔，可选: {', '.join(TARGETS.keys())}；默认全部",
    )
    ap.add_argument(
        "--exclude",
        "-e",
        action="append",
        default=[],
        metavar="GLOB",
        help="额外的排除 glob（相对 .codebuddy 的路径），可多次指定；\n"
             "会与脚本内的 DEFAULT_EXCLUDES 合并，不会覆盖。",
    )
    ap.add_argument(
        "--no-default-excludes",
        action="store_true",
        help="忽略脚本内的 DEFAULT_EXCLUDES，只使用 --exclude 传入的 glob",
    )
    ap.add_argument(
        "--force",
        "-f",
        action="store_true",
        help="目标已存在时，覆盖（删除后重建软链）",
    )
    ap.add_argument(
        "--dry-run",
        "-n",
        action="store_true",
        help="只演练，不实际修改文件系统",
    )
    ap.add_argument(
        "--unlink",
        action="store_true",
        help="反向操作：删除之前建立的、指向 .codebuddy 的软链接",
    )
    return ap


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    project_root: Path = args.project_root.resolve()

    if not project_root.is_dir():
        err(f"项目根目录不存在: {project_root}")
        return 2

    # 合并 excludes：DEFAULT_EXCLUDES + --exclude，保持顺序并去重
    if args.no_default_excludes:
        merged_excludes = list(dict.fromkeys(args.exclude))
    else:
        merged_excludes = list(dict.fromkeys([*DEFAULT_EXCLUDES, *args.exclude]))

    log(f"project_root = {project_root}")
    log(f"targets      = {[t.key for t in args.targets]}")
    log(f"excludes     = {merged_excludes}")
    if args.dry_run:
        log("DRY-RUN 模式，不会实际修改文件")

    if args.unlink:
        return do_unlink(project_root, args.targets, dry=args.dry_run)

    return plan_and_apply(
        project_root=project_root,
        targets=args.targets,
        excludes=merged_excludes,
        dry=args.dry_run,
        force=args.force,
    )


if __name__ == "__main__":
    sys.exit(main())
