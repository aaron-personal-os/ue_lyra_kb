#!/usr/bin/env python3
"""wiki_lint.py — 项目知识库 + Variant 隔离 lint v1.0

离线脚本,纯 Python 3.9+ stdlib,无外部依赖。可在任意 Python / CI / pre-commit 环境运行。

检查项(v1.0)
==============

ERROR(必须修复,pre-commit 拦截)
  1. broken-link       wiki [[xxx]] 引用不存在的页
  2. missing-fm        缺 frontmatter 必填字段
  3. bad-anchor        anchors: 路径在文件系统不存在
  4. variant-include   Source/ue_ai_demo/Variant_X/ 下的 .cpp/.h 含跨 Variant include
  5. id-mismatch       frontmatter id 与文件路径不匹配
  6. menu-config-invalid ★v0.3★ menu_config.json 语法或结构错(JSON 解析失败 / 缺 main_menu)
  7. menu-label-mismatch ★★v0.5 升级★★ 同一 action 在 menu_config.json 多挂载点 label 不一致(v0.3 引入 warn,v0.5 升 error: 团队达成"零容忍"共识,因为 R17 已证实是真用户体验事故源)
  8. log-fragment-required ★★★v0.7★★★ log.d/log-<owner>.md 段头 或主 log.md ROLLUP 区块段头 缺 <owner> 字段(v0.7 强制 per-human 分文件,owner 不可省)
  9. tutorial-fm       ★★★v1.0★★★ 30-tutorials/ 教程文件 frontmatter 规范(type/series/lesson_index/difficulty/title/description/prerequisites)
 10. tutorial-ext-ref  ★★★v1.3★★★ 30-tutorials/ 教程**正文** wikilink 引外部页 → WARN(降级,详见 [[60-decisions/0005-tutorial-cross-link-policy]]);frontmatter related/prereq/sources 豁免(图谱性引用,由 web-app 渲染期降级处理)

WARN(建议修复,不拦截 commit)
  8. ascii-art         代码块出现 ASCII 制表 / box-drawing 字符(违反 conventions §9)
                       ★v0.6 收紧★ block 内含 markdown 表格 separator 行 (|---|---|) 时豁免
  9. asymm-link        A 在 related 引了 B,B 没回引(双向链不闭环;target 无 fm 时豁免)
 10. stale             status: stale 的页面(提示 re-verify)
 11. anchor-changed    ★v0.2★ anchor 文件 sha256 已变(cache 不一致)→ wiki 可能漂移
 12. version-drift     ★v0.2★ wiki 页提到的 UE / Python 版本号 ≠ project-versions.md 权威值
 13. bat-non-ascii-before-chcp ★v0.4★ .bat 文件 `chcp 65001` 之前的行含非 ASCII 字符(R13 真实事故)
 14. bat-missing-chcp ★v0.4★ .bat 含非 ASCII 字符但缺 `chcp 65001`(cmd 默认 codepage mojibake 风险)
 15. last-synced-stale ★v0.4★ wiki 页 last_synced > 180 天,建议 re-verify
 16. duplicate-entity ★v0.4★ 同一标题 / 同 anchor 在多个 wiki 页出现(容易引起认知混乱)
 17. prerequisites-mismatch ★v0.5★ frontmatter `prerequisites:` 引用的 wiki 页不存在 / status=stale|deprecated
 19. log-order        ★v0.6★ Docs/log.md 中 R<n> 编号段落非递增(R23→R22→R21 倒序事故,R24 沉淀;v0.7 起 baseline 区块内豁免)
 20. related-mismatch ★v0.6★ frontmatter `related:` 类型错 / 引用页 status=stale|deprecated(broken-link 不覆盖 status)
 21. log-fragment-mergeable ★★★v0.7★★★ log.d/log-<X>.md 段头 owner ≠ <X>(文件名 owner)→ rollup 时会以文件名为准,但 review 易混乱
 22. log-md-rollup-needed ★★★v0.7★★★ log.d/ 有比主 log.md 新的分文件 → 提示跑 log_rollup.py --apply
 23. log-orphan-wiki-touched ★★★v0.7★★★ log.d/ 段提到的 [[wiki-page]] 实际不存在(类似 broken-link 但限定 log.d/ 内)

INFO(仅提示)
 24. orphan            无任何 inbound link(除 index/overview/00-meta)
 25. draft             status: draft 计数
 26. deprecated        status: deprecated 计数 + 是否仍被引用
 27. cache-init        ★v0.2★ 首次建立 anchor sha256 cache

用法
====

    # 全检查（默认）
    python wiki_lint.py

    # 仅 ERROR 级别（pre-commit 用，速度快）
    python wiki_lint.py --check

    # 仅扫指定 scope
    python wiki_lint.py --scope wiki        # 只查 Docs/
    python wiki_lint.py --scope source      # 只查 Source/Variant_*/
    python wiki_lint.py --scope all         # 默认，全扫

    # JSON 输出（CI / 进一步处理）
    python wiki_lint.py --json

    # 指定项目根
    python wiki_lint.py --project-root /path/to/repo

    # 自动修复（仅安全项：补 last_synced / status: draft / index 漏录）
    python wiki_lint.py --fix

    # ★v0.2★ 重算所有 anchor sha256 → 写到 cache（用户审过 wiki 后跑这个固化）
    python wiki_lint.py --update-cache

    # ★v0.2★ 打印 cache 概况
    python wiki_lint.py --show-cache

退出码
======

    0  无 ERROR（可能有 WARN/INFO）
    1  有 WARN 但无 ERROR（--check 模式仍返回 0）
    2  有 ERROR
    3  脚本本身报错（IOError / 配置错）
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime, date
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# 配置：路径、要求字段、白名单
# ---------------------------------------------------------------------------

DOCS_DIR = "Docs"
SOURCE_VARIANT_GLOB = "Source/ue_ai_demo/Variant_*/"

# frontmatter 必填字段（所有非 meta 类页）
REQUIRED_FM = ["id", "type", "status", "language", "owner", "last_synced"]

# 这些 type 可不写 anchors
ANCHORS_OPTIONAL_TYPES = {"topic", "adr", "meta", "tutorial", "guide", "reference", "case-study"}

# 这些路径不算 wiki 页（不参与 broken-link、orphan 等检查）
# ★v0.7★ log.d/ 是 per-human append-only 日志分片，由 log_rollup.py 处理
# 不参与常规 wiki 检查（frontmatter / index / broken-link），改由 check_log_fragment_v07 专门检查
EXCLUDE_PATH_PREFIXES = ("_raw/", ".obsidian/", "log.d/", "log-archive/")

# 这些文件即便在 Docs/ 下也不参与"必须有 frontmatter"检查
META_FILES = {"index.md", "log.md", "overview.md", "README.md", ".wiki-schema.md"}

# 这些目录前缀下的页也不强制 frontmatter（meta 类元文档）
META_DIR_PREFIXES = ("00-meta/",)

# 这些路径前缀下的 anchor 是"运行期生成 / 个人开发"，缺失只 warn 不 error
# 也不参与 sha256 cache（每次跑都会变 / 不在 git）
SOFT_ANCHOR_PREFIXES = (
    "Intermediate/", "Saved/", "Binaries/", "Build/", "DerivedDataCache/",
    "Content/Python/LocalDevelop", "Content/Python/.tools/", "Content/Python/.venv",
    "Content/Python/ThirdParty/",
)

# ★v0.2★ anchor sha256 cache 文件（commit 进 git，让多人协作可检测漂移）
ANCHOR_CACHE_REL = ".codebuddy/skills/project-wiki/.cache/anchors.json"
ANCHOR_CACHE_VERSION = 1

# ★v0.3★ menu_config 一致性检测扫描的目标文件
# 共享菜单（必扫，纳入 git）+ local（个人菜单，存在才扫，不算关键）
MENU_CONFIG_FILES = (
    "Content/Python/Config/menu_config.json",
)
MENU_CONFIG_LOCAL_FILES = (
    "Content/Python/LocalDevelop/Config/local_menu_config.json",
)

# ★v0.4★ .bat chcp 检测：扫描时跳过的目录前缀（运行期生成 / 第三方）
BAT_SCAN_EXCLUDE_PREFIXES = (
    ".venv/", "Intermediate/", "Saved/", "Binaries/", "Build/",
    "DerivedDataCache/", "ThirdParty/", "node_modules/",
    "Content/Python/.venv/", "Content/Python/ThirdParty/",
)

# ★v0.4★ last_synced 过期阈值（天数）。> 此值报 last-synced-stale warn
LAST_SYNCED_STALE_DAYS = 180

# ★v0.4★ duplicate-entity 检测：豁免目录（这些页就是设计为"重复出现某些标题"）
DUPLICATE_ENTITY_EXEMPT_PREFIXES = (
    "00-meta/",  # 元页常常列其他页标题做导航
    "index",
    "log",
    "overview",
    "60-decisions/0000-template",
    "60-decisions/0001-project-knowledge-base",  # 设计文档，结构性引用
)
# 短标题不报（避免误报）：标题字符数 < 此值时跳过
DUPLICATE_ENTITY_MIN_TITLE_LEN = 4
# 单个 anchor 文件超过此尺寸不算 sha256（避免对 unreal.py 50MB 这种文件慢爆）
ANCHOR_MAX_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB

# ★v0.2★ 版本漂移检测：哪些页面豁免（讨论历史版本属正常）
VERSION_DRIFT_EXEMPT_PREFIXES = (
    "60-decisions/",          # ADR 经常讨论"从 X 升到 Y"
    "_raw/",                  # 原始素材
    "90-snapshots/",          # 快照本来就是历史
    "log",                    # 时间线
    "00-meta/project-versions",  # 这就是权威源本身
)

# 已知"占位 wikilink 宿主"——其内 [[xxx]] 是 schema 示例而非真链接
PLACEHOLDER_HOSTS = {
    "Docs/00-meta/ai-playbook.md",
    "Docs/60-decisions/0000-template.md",
    "Docs/40-runbooks/use-project-wiki.md",
    "Docs/.wiki-schema.md",
    "Docs/log.md",
    "Docs/00-meta/glossary.md",
    "Docs/index.md",
    "Docs/70-topics/skill-memory-vs-wiki.md",  # 内含 [[Docs/...]] 占位
}

# orphan 检查白名单（这些页本来就没人 wikilink 它们）
ORPHAN_ALLOWLIST_PREFIXES = ("00-meta/", "index", "overview", "log", "README", ".wiki-schema")

# ASCII art 检测：box-drawing + 简化制表
ASCII_BOX_CHARS = set("─│┌┐└┘├┤┬┴┼━┃┏┓┗┛┣┫┳┻╋")
ASCII_FALLBACK_PATTERNS = [
    re.compile(r"^\s*\+[-=]{3,}\+"),       # +---+ 顶/底
    re.compile(r"^\s*\|.{2,}\|\s*$"),      # |  ...  |
    re.compile(r"^\s*[├└][─━]"),           # 树状
    re.compile(r"^\s*\+[-=+]+$"),          # 全是 +/=/-
]

# ★v0.6★ markdown 表格 separator 行识别(豁免 ASCII art 误报)
# 形如 `|---|---|` / `| --- | --- |` / `|:---|:---:|---:|` 的 markdown 表格分隔行
# 出现这种行说明整个 block 是 markdown table 不是 ASCII art
MARKDOWN_TABLE_SEP_RE = re.compile(r"^\s*\|?(\s*:?-{3,}:?\s*\|)+\s*:?-{3,}:?\s*\|?\s*$")

# 代码块 ASCII art 白名单语言（这些块允许 ASCII 制表，不告警）
ASCII_ALLOWED_LANGS = {"text", "tree", "log", "console", "ini", "shell", "bash", "sh", "cmd",
                       "powershell", "ps1", "json", "yaml", "yml", "toml",
                       "python", "py", "cpp", "c", "rust", "go", "ts", "js", "tsx", "jsx",
                       "sql", "html", "css", "diff", "mermaid",
                       "code-ref"}  # ★R22★ Cursor agent 风格的 startLine:endLine:filepath 引用块


# ---------------------------------------------------------------------------
# 数据结构
# ---------------------------------------------------------------------------

@dataclass
class Issue:
    code: str            # broken-link / missing-fm / ...
    severity: str        # error / warn / info
    file: str            # repo-relative path
    line: int = 0        # 0 = 整页
    detail: str = ""

    def fmt(self) -> str:
        loc = f"{self.file}" + (f":{self.line}" if self.line else "")
        return f"  [{self.code:<16}] {loc}  {self.detail}"


@dataclass
class WikiPage:
    path: Path                       # absolute
    rel: str                         # repo-relative ("Docs/...")
    page_id: str                     # "60-topics/foo"
    text: str                        # full file content
    fm: dict = field(default_factory=dict)
    fm_lines: int = 0                # 0 if no frontmatter
    inbound_count: int = 0           # filled later

    @property
    def is_meta_file(self) -> bool:
        name = self.path.name
        if name in META_FILES:
            return True
        return any(self.page_id.startswith(pref) for pref in META_DIR_PREFIXES)

    @property
    def has_fm(self) -> bool:
        return self.fm_lines > 0


# ---------------------------------------------------------------------------
# Frontmatter 解析（mini YAML，仅认我们用的字段形态）
# ---------------------------------------------------------------------------

def parse_frontmatter(text: str) -> tuple[dict, int]:
    """返回 (fm_dict, fm_占用行数)。无 frontmatter 时返回 ({}, 0)。"""
    if not text.startswith("---\n") and not text.startswith("---\r\n"):
        return {}, 0
    lines = text.splitlines()
    if lines[0].strip() != "---":
        return {}, 0
    end = -1
    for i in range(1, min(len(lines), 200)):
        if lines[i].strip() == "---":
            end = i
            break
    if end < 0:
        return {}, 0

    fm: dict = {}
    cur_key: Optional[str] = None
    list_items: list[str] = []
    for raw in lines[1:end]:
        line = raw.rstrip()
        if not line.strip():
            continue
        # list item ("  - xxx" 或 "  - 'xxx'" 或 '  - "[[xxx]]"')
        m = re.match(r"^\s*-\s*(.*)$", line)
        if m and cur_key is not None:
            val = m.group(1).strip()
            # strip 引号
            if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
                val = val[1:-1]
            # nested key: value (anchors 是 list of dict)
            inner = re.match(r"^([\w-]+):\s*(.*)$", val)
            if inner:
                list_items.append({inner.group(1): inner.group(2).strip()})
            else:
                list_items.append(val)
            continue
        # key: value 形式
        m = re.match(r"^([\w-]+):\s*(.*)$", line)
        if m:
            # 上一个 list 收尾
            if cur_key is not None and list_items:
                fm[cur_key] = list_items
                list_items = []
            cur_key = m.group(1)
            val = m.group(2).strip()
            if val == "":
                # 后续可能是 list
                continue
            # 单值
            if val.startswith("[") and val.endswith("]"):
                # inline list "[a, b, c]"
                inner = val[1:-1]
                fm[cur_key] = [x.strip().strip("'\"") for x in inner.split(",") if x.strip()]
            else:
                if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
                    val = val[1:-1]
                fm[cur_key] = val
            cur_key = None  # 单值模式，避免后续 list 错误归并
        # 其他形态（注释 / 续行）忽略
    # 收尾
    if cur_key is not None and list_items:
        fm[cur_key] = list_items

    return fm, end + 1


# ---------------------------------------------------------------------------
# 工具：扫描 Docs/
# ---------------------------------------------------------------------------

def collect_pages(docs_root: Path) -> list[WikiPage]:
    pages: list[WikiPage] = []
    if not docs_root.is_dir():
        return pages
    for p in sorted(docs_root.rglob("*.md")):
        rel = p.relative_to(docs_root.parent).as_posix()
        # 排除 _raw/ 与 .obsidian/
        rel_inside = rel[len(DOCS_DIR) + 1:]
        if rel_inside.startswith(EXCLUDE_PATH_PREFIXES):
            continue
        text = p.read_text(encoding="utf-8")
        fm, fm_lines = parse_frontmatter(text)
        page_id = rel_inside.removesuffix(".md")
        pages.append(WikiPage(path=p, rel=rel, page_id=page_id, text=text, fm=fm, fm_lines=fm_lines))
    return pages


# ---------------------------------------------------------------------------
# 检查 1: broken wikilinks
# ---------------------------------------------------------------------------

WIKILINK_RE = re.compile(r"\[\[([^\]|#]+)(?:[#|][^\]]*)?\]\]")
INLINE_CODE_RE = re.compile(r"`[^`\n]*`")
FENCE_BLOCK_RE = re.compile(r"```[\s\S]*?```", re.MULTILINE)


def strip_code(text: str) -> str:
    """去掉 fenced code block + inline code 后的文本（用于'真'wikilink 提取）。"""
    text = FENCE_BLOCK_RE.sub("", text)
    text = INLINE_CODE_RE.sub("", text)
    return text


def collect_raw_ids(docs_root: Path) -> set[str]:
    """收集 Docs/_raw/ 下实际存在的 .md 文件作为合法 wikilink target。

    ★R30★ schema 明文允许 `[[_raw/specs/xxx]]` / `[[_raw/chats/xxx]]` 引用 raw 素材
    (见 .wiki-schema.md §交叉引用 + crystallize.md §4)。collect_pages 排除了 _raw/，
    但 broken-link 检查必须能识别这些合法 target。其他检查（frontmatter / orphan /
    anchor 等）不动，raw 文件仍然是"AI 只读、不参与 wiki 检查"的素材。
    """
    raw_ids: set[str] = set()
    raw_root = docs_root / "_raw"
    if not raw_root.is_dir():
        return raw_ids
    for p in raw_root.rglob("*.md"):
        rel_inside = p.relative_to(docs_root).as_posix()
        raw_ids.add(rel_inside.removesuffix(".md"))
    return raw_ids


def check_broken_links(pages: list[WikiPage], docs_root: Path) -> list[Issue]:
    page_ids = {p.page_id for p in pages} | collect_raw_ids(docs_root)
    issues: list[Issue] = []
    for page in pages:
        # placeholder 宿主：不报告 broken（schema 示例占位）
        if page.rel in PLACEHOLDER_HOSTS:
            continue
        clean = strip_code(page.text)
        for m in WIKILINK_RE.finditer(clean):
            target = m.group(1).strip()
            if target in page_ids:
                continue
            # 行号定位（在原文里找）
            line_no = page.text[:page.text.find(m.group(0))].count("\n") + 1 if m.group(0) in page.text else 0
            issues.append(Issue(
                code="broken-link",
                severity="error",
                file=page.rel,
                line=line_no,
                detail=f"[[{target}]] 不存在",
            ))
    return issues


# ---------------------------------------------------------------------------
# 检查 2: frontmatter 完整性
# ---------------------------------------------------------------------------

def check_frontmatter(pages: list[WikiPage]) -> list[Issue]:
    issues: list[Issue] = []
    for page in pages:
        if page.is_meta_file:
            continue
        if not page.has_fm:
            issues.append(Issue("missing-fm", "error", page.rel, 1,
                                "整页缺 frontmatter（应以 --- 开始）"))
            continue
        for fld in REQUIRED_FM:
            if fld not in page.fm or page.fm.get(fld) in (None, "", []):
                issues.append(Issue("missing-fm", "error", page.rel, 1,
                                    f"缺必填字段 '{fld}'"))
        ptype = page.fm.get("type", "")
        if ptype not in ANCHORS_OPTIONAL_TYPES:
            anchors = page.fm.get("anchors")
            if not anchors or not isinstance(anchors, list):
                issues.append(Issue("missing-fm", "error", page.rel, 1,
                                    f"type={ptype!r} 必须有 anchors（≥1）"))

        # id 必须等于路径
        page_id = page.fm.get("id", "")
        if page_id and page_id != page.page_id:
            issues.append(Issue("id-mismatch", "error", page.rel, 1,
                                f"frontmatter id={page_id!r} 不等于路径推导的 {page.page_id!r}"))
    return issues


# ---------------------------------------------------------------------------
# 检查 3: anchors 路径存在性
# ---------------------------------------------------------------------------

def check_anchors(pages: list[WikiPage], project_root: Path) -> list[Issue]:
    issues: list[Issue] = []
    for page in pages:
        if not page.has_fm:
            continue
        anchors = page.fm.get("anchors", [])
        if not isinstance(anchors, list):
            continue
        for a in anchors:
            ap = a.get("path") if isinstance(a, dict) else (a if isinstance(a, str) else None)
            if not ap:
                continue
            target = (project_root / ap).resolve()
            if not target.exists():
                # 运行期生成 / 个人开发 / 三方依赖 → 降级 warn
                soft = any(ap.startswith(pref) for pref in SOFT_ANCHOR_PREFIXES)
                sev = "warn" if soft else "error"
                detail = f"anchor 路径不存在: {ap}"
                if soft:
                    detail += "（运行期生成或个人目录，可能尚未生成）"
                issues.append(Issue("bad-anchor", sev, page.rel, 1, detail))
    return issues


# ---------------------------------------------------------------------------
# 检查 4: Variant 跨包 include
# ---------------------------------------------------------------------------

VARIANT_INCLUDE_RE = re.compile(r'^\s*#\s*include\s+["<]([^">]+)[">]', re.MULTILINE)


def check_variant_includes(project_root: Path) -> list[Issue]:
    issues: list[Issue] = []
    src = project_root / "Source" / "ue_ai_demo"
    if not src.is_dir():
        return issues
    variants = sorted([p.name for p in src.iterdir() if p.is_dir() and p.name.startswith("Variant_")])
    if len(variants) < 2:
        return issues

    for v in variants:
        vroot = src / v
        for ext in ("*.cpp", "*.h"):
            for f in vroot.rglob(ext):
                rel = f.relative_to(project_root).as_posix()
                text = f.read_text(encoding="utf-8", errors="replace")
                for m in VARIANT_INCLUDE_RE.finditer(text):
                    inc = m.group(1)
                    line_no = text[:m.start()].count("\n") + 1
                    # 检查是否引了"别的 Variant_X/..."
                    for other in variants:
                        if other == v:
                            continue
                        # 长形式：includes "Variant_OtherX/..." 或 "../Variant_OtherX/..."
                        if other + "/" in inc.replace("\\", "/"):
                            issues.append(Issue(
                                code="variant-include",
                                severity="error",
                                file=rel,
                                line=line_no,
                                detail=f"{v} 跨包 include {other!r}: {inc}",
                            ))
                        # 短形式：当前 Variant 的 PublicIncludePaths 让 .cpp 写 "OtherFile.h"
                        # 直接看顶层文件名是否归别的 Variant
                        else:
                            inc_basename = inc.rsplit("/", 1)[-1]
                            # 仅当 basename 和"别的 Variant" prefix 相符（如 Combat*.h vs SideScrolling*.h）
                            other_prefix = other[len("Variant_"):]  # "Combat" / "Platforming" / "SideScrolling"
                            cur_prefix = v[len("Variant_"):]
                            if (
                                inc_basename.startswith(other_prefix)
                                and not inc_basename.startswith(cur_prefix)
                                # 排除 UE 常见前缀冲突（Camera 类等）
                                and not inc_basename.startswith(("Engine", "Core", "GameFramework"))
                            ):
                                # 同时确认那个 .h 真的属于别的 Variant 而不是 UE 引擎类
                                src_h = src / other
                                hits = list(src_h.rglob(inc_basename))
                                if hits:
                                    issues.append(Issue(
                                        code="variant-include",
                                        severity="error",
                                        file=rel,
                                        line=line_no,
                                        detail=f"{v} 短形式 include 别的 Variant 文件 ({other}): {inc}",
                                    ))
    return issues


# ---------------------------------------------------------------------------
# 检查 5: ASCII art (代码块内出现制表字符)
# ---------------------------------------------------------------------------

# ★R22★ 放宽 code-fence 识别:支持 Cursor agent 风格的 code reference 块
#  ```startLine:endLine:filepath
# 这种 fence open 含 `:` `/` `.` 等非 \w 字符,旧 regex `[\w-]*` 完全不匹配 →
# 状态机错位:把 reference 块开始当成普通文本,把 reference 块结束符 ``` 误识为
# 新块 fence open(空 lang),把后续 markdown 表格当作 ASCII art 报警(R22 实际事故).
# 修法:fence open 接任何字符,但识别后:
#   - 含 `:` 或 `/` → 视为 code-ref,等同白名单
#   - 否则取 lang 走原逻辑
CODE_FENCE_BEGIN_RE = re.compile(r"^```(.*)$")


def _normalize_block_lang(raw: str) -> str:
    raw = raw.strip().lower()
    if ":" in raw or "/" in raw:
        return "code-ref"
    return raw


def _is_markdown_table_block(buf: list[str]) -> bool:
    """识别 markdown table:block 内含 separator 行 (|---|---|) 即视为表格示例,不算 ASCII art。

    R25(v0.6) false-positive 修复:用户在 wiki 用 ``` ``` 包裹 markdown table 作为示例
    (例如 conventions 页讲表格语法)时,`| col |` 行触发 ASCII_FALLBACK_PATTERNS[1],
    导致 ASCII art 误报。markdown table 必有 `|---|---|` separator 行,以此为特征豁免。
    """
    return any(MARKDOWN_TABLE_SEP_RE.match(line) for line in buf)


def check_ascii_art(pages: list[WikiPage]) -> list[Issue]:
    issues: list[Issue] = []
    for page in pages:
        # README / log / index 这种 meta 页常含 tree 输出，也跳过
        if page.is_meta_file:
            continue
        lines = page.text.splitlines()
        in_block = False
        block_lang = ""
        block_start = 0
        block_buf: list[str] = []
        for i, line in enumerate(lines, 1):
            if not in_block:
                m = CODE_FENCE_BEGIN_RE.match(line)
                if m:
                    in_block = True
                    block_lang = _normalize_block_lang(m.group(1))
                    block_start = i
                    block_buf = []
            else:
                if line.startswith("```"):
                    # 块结束 → 判定
                    if block_lang not in ASCII_ALLOWED_LANGS:
                        # 检测 box-drawing
                        joined = "\n".join(block_buf)
                        has_box = any(ch in ASCII_BOX_CHARS for ch in joined)
                        has_fallback = any(any(p.match(b) for p in ASCII_FALLBACK_PATTERNS) for b in block_buf)
                        # ★v0.6★ block 内含 markdown table separator → 是表格示例不是 ASCII art
                        if (has_box or has_fallback) and not _is_markdown_table_block(block_buf):
                            issues.append(Issue(
                                code="ascii-art",
                                severity="warn",
                                file=page.rel,
                                line=block_start,
                                detail=(
                                    f"代码块（lang={block_lang or '<空>'}）疑似 ASCII art；"
                                    "按 conventions §9 应改用 mermaid 或显式标 lang=text"
                                ),
                            ))
                    in_block = False
                    block_buf = []
                else:
                    block_buf.append(line)
    return issues


# ---------------------------------------------------------------------------
# 检查 6: 双向链不闭环
# ---------------------------------------------------------------------------

def check_bidir_links(pages: list[WikiPage]) -> list[Issue]:
    issues: list[Issue] = []
    related_map: dict[str, set[str]] = {}
    body_links_map: dict[str, set[str]] = {}
    page_ids = {p.page_id for p in pages}
    page_by_id = {p.page_id: p for p in pages}

    for page in pages:
        # frontmatter related
        rel_field = page.fm.get("related", []) if page.has_fm else []
        if isinstance(rel_field, list):
            related: set[str] = set()
            for r in rel_field:
                # r 形如 "[[60-topics/foo]]"
                m = re.match(r"\[\[([^\]]+)\]\]", r if isinstance(r, str) else "")
                if m:
                    target = m.group(1).split("|")[0].split("#")[0]
                    related.add(target)
            related_map[page.page_id] = related
        # body wikilinks
        body_links_map[page.page_id] = {
            m.group(1).split("|")[0].split("#")[0]
            for m in WIKILINK_RE.finditer(strip_code(page.text))
        }

    for src_id, targets in related_map.items():
        for t in targets:
            if t not in page_ids:
                # broken link 已在另一个 check 报告
                continue
            target_page = page_by_id.get(t)
            # 白名单：无 frontmatter 的 meta 类页（00-meta/ai-playbook 等是约定无 fm）
            # 是单向被引的"权威/约定"型节点，不要求回链
            if target_page is not None and not target_page.has_fm:
                continue
            other_related = related_map.get(t, set())
            other_body = body_links_map.get(t, set())
            if src_id not in other_related and src_id not in other_body:
                issues.append(Issue(
                    code="asymm-link",
                    severity="warn",
                    file=f"{DOCS_DIR}/{src_id}.md",
                    line=1,
                    detail=f"related → [[{t}]]，但 [[{t}]] 没回引 [[{src_id}]]",
                ))
    return issues


# ---------------------------------------------------------------------------
# 检查 7: status 状态报告
# ---------------------------------------------------------------------------

def check_status(pages: list[WikiPage]) -> list[Issue]:
    issues: list[Issue] = []
    drafts: list[str] = []
    deprecateds: list[str] = []
    page_ids = {p.page_id for p in pages}
    inbound_for: dict[str, list[str]] = {pid: [] for pid in page_ids}
    for p in pages:
        for m in WIKILINK_RE.finditer(strip_code(p.text)):
            t = m.group(1).split("|")[0].split("#")[0]
            if t in page_ids and t != p.page_id:
                inbound_for[t].append(p.page_id)

    for p in pages:
        st = p.fm.get("status", "") if p.has_fm else ""
        if st == "stale":
            issues.append(Issue("stale", "warn", p.rel, 1, "status: stale，建议 re-verify"))
        elif st == "draft":
            drafts.append(p.page_id)
        elif st == "deprecated":
            deprecateds.append(p.page_id)
            inb = inbound_for.get(p.page_id, [])
            if inb:
                issues.append(Issue(
                    code="deprecated",
                    severity="warn",
                    file=p.rel,
                    line=1,
                    detail=f"已弃用但仍被 {len(inb)} 页引用: {inb[:3]}{'...' if len(inb)>3 else ''}",
                ))
    if drafts:
        issues.append(Issue("draft", "info", "", 0,
                            f"草稿数 {len(drafts)}: {drafts[:5]}{'...' if len(drafts)>5 else ''}"))
    if deprecateds:
        issues.append(Issue("deprecated", "info", "", 0,
                            f"弃用数 {len(deprecateds)}: {deprecateds}"))
    return issues


# ---------------------------------------------------------------------------
# 检查 8: orphan
# ---------------------------------------------------------------------------

def check_orphans(pages: list[WikiPage]) -> list[Issue]:
    page_ids = {p.page_id for p in pages}
    inbound: dict[str, int] = {pid: 0 for pid in page_ids}
    for p in pages:
        for m in WIKILINK_RE.finditer(strip_code(p.text)):
            t = m.group(1).split("|")[0].split("#")[0]
            if t in page_ids and t != p.page_id:
                inbound[t] += 1
    issues: list[Issue] = []
    for p in pages:
        if p.page_id.startswith(ORPHAN_ALLOWLIST_PREFIXES):
            continue
        if p.is_meta_file:
            continue
        if inbound.get(p.page_id, 0) == 0:
            issues.append(Issue("orphan", "info", p.rel, 0, "无任何 inbound wikilink"))
    return issues


# ---------------------------------------------------------------------------
# 检查 9: index.md ↔ 文件系统 diff
# ---------------------------------------------------------------------------

def check_index_consistency(pages: list[WikiPage], docs_root: Path) -> list[Issue]:
    index_path = docs_root / "index.md"
    if not index_path.is_file():
        return [Issue("missing-fm", "error", "Docs/index.md", 0, "index.md 不存在")]
    text = index_path.read_text(encoding="utf-8")
    listed = {m.group(1).split("|")[0].split("#")[0] for m in WIKILINK_RE.finditer(text)}
    # 实际"应该出现在 index"的页：除 _raw/ 与 .wiki-schema 等彻底元元页以外的全部
    EXCLUDE_FROM_INDEX = {"index", "log", "overview", "README", ".wiki-schema"}
    actual = {p.page_id for p in pages
              if not p.page_id.startswith("_raw/")
              and p.page_id not in EXCLUDE_FROM_INDEX}

    issues: list[Issue] = []
    # 实际有但 index 没列
    missing = sorted(actual - listed)
    for m in missing:
        # 排除 templates / 已知不录页
        if m == "templates" or m.startswith(".wiki-schema"):
            continue
        issues.append(Issue("missing-fm", "warn", "Docs/index.md", 0,
                            f"index 漏录页: [[{m}]]"))
    # index 列了但实际没有
    extra = sorted(listed - actual - {"X", "Y", "id", "wiki-id", "other-id"})
    for e in extra:
        # 跳过 broken-link 已报告的（这里只报告"明显是 index 残留"的）
        # 简化：只报告以 60-topics/ 等数字前缀开头的
        if re.match(r"^[0-9]{2}-", e):
            issues.append(Issue("broken-link", "warn", "Docs/index.md", 0,
                                f"index 列了但页不存在: [[{e}]]"))
    return issues


# ---------------------------------------------------------------------------
# ★v0.2★ anchor sha256 cache（commit 进 git，跨机检测 anchor 漂移）
# ---------------------------------------------------------------------------

def _file_sha256(p: Path) -> Optional[str]:
    """计算文件 sha256；目录 / 大文件 / 不可读 → None。"""
    try:
        if not p.is_file():
            return None
        if p.stat().st_size > ANCHOR_MAX_SIZE_BYTES:
            return None
        h = hashlib.sha256()
        with p.open("rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()
    except OSError:
        return None


def _collect_anchor_map(pages: list[WikiPage]) -> dict[str, list[str]]:
    """聚合：anchor 路径 → tracked_pages（哪些 wiki 页引了它）。"""
    m: dict[str, list[str]] = {}
    for page in pages:
        if not page.has_fm:
            continue
        anchors = page.fm.get("anchors", [])
        if not isinstance(anchors, list):
            continue
        for a in anchors:
            ap = a.get("path") if isinstance(a, dict) else (a if isinstance(a, str) else None)
            if not ap:
                continue
            # 跳过运行期生成路径
            if any(ap.startswith(pref) for pref in SOFT_ANCHOR_PREFIXES):
                continue
            m.setdefault(ap, []).append(page.page_id)
    # 排序去重，让 cache 写出确定性
    for k in m:
        m[k] = sorted(set(m[k]))
    return m


def load_anchor_cache(project_root: Path) -> dict:
    cache_file = project_root / ANCHOR_CACHE_REL
    if not cache_file.is_file():
        return {"version": ANCHOR_CACHE_VERSION, "anchors": {}}
    try:
        return json.loads(cache_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"version": ANCHOR_CACHE_VERSION, "anchors": {}}


def save_anchor_cache(project_root: Path, cache: dict) -> Path:
    cache_file = project_root / ANCHOR_CACHE_REL
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    # 排序的 key + 双空格缩进，让 git diff 友好
    cache["version"] = ANCHOR_CACHE_VERSION
    cache["updated_at"] = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    text = json.dumps(cache, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    cache_file.write_text(text, encoding="utf-8")
    return cache_file


def check_anchor_sha256(pages: list[WikiPage], project_root: Path) -> list[Issue]:
    """对比 anchor 文件当前 sha256 与 cache，不一致即 anchor-changed WARN。"""
    issues: list[Issue] = []
    cache = load_anchor_cache(project_root)
    cache_anchors = cache.get("anchors", {})
    anchor_map = _collect_anchor_map(pages)

    if not cache_anchors:
        # 首次跑，提示用户跑 --update-cache 初始化（但本次不报 anchor-changed）
        issues.append(Issue(
            code="cache-init",
            severity="info",
            file="",
            detail=(
                f"未找到 anchor sha256 cache（{ANCHOR_CACHE_REL}）。"
                f"建议跑 `./lint_wiki.sh --update-cache` 初始化（{len(anchor_map)} 个 anchor 待登记）"
            ),
        ))
        return issues

    for ap, tracked in sorted(anchor_map.items()):
        target = (project_root / ap).resolve()
        cur = _file_sha256(target)
        if cur is None:
            # 文件不存在或太大；bad-anchor 已经报过，跳过
            continue
        cached = cache_anchors.get(ap, {})
        cached_sha = cached.get("sha256")
        if not cached_sha:
            # cache 里没这条 → 新 anchor，建议用户 --update-cache
            issues.append(Issue(
                code="anchor-changed",
                severity="warn",
                file=tracked[0] if tracked else "",
                line=1,
                detail=(
                    f"新 anchor 未登记到 cache: {ap}（影响 {len(tracked)} 页：{tracked[:3]}{'...' if len(tracked)>3 else ''}）"
                    f"  → 跑 `./lint_wiki.sh --update-cache` 固化"
                ),
            ))
            continue
        if cur != cached_sha:
            issues.append(Issue(
                code="anchor-changed",
                severity="warn",
                file=tracked[0] if tracked else "",
                line=1,
                detail=(
                    f"anchor 文件已变 (sha256 不符): {ap}"
                    f"  → 影响 {len(tracked)} 页：{tracked[:3]}{'...' if len(tracked)>3 else ''}"
                    f"  → re-verify wiki 后跑 `./lint_wiki.sh --update-cache` 固化"
                ),
            ))
    # 反向：cache 里有但当前 anchor_map 没引用了（页面删了或改 frontmatter 了）
    stale_in_cache = sorted(set(cache_anchors.keys()) - set(anchor_map.keys()))
    if stale_in_cache:
        issues.append(Issue(
            code="cache-init",
            severity="info",
            file="",
            detail=(
                f"cache 里 {len(stale_in_cache)} 条 anchor 已无 wiki 引用: {stale_in_cache[:3]}{'...' if len(stale_in_cache)>3 else ''}"
                f"  → 跑 `./lint_wiki.sh --update-cache` 清理"
            ),
        ))
    return issues


def update_anchor_cache(pages: list[WikiPage], project_root: Path) -> tuple[int, int, int]:
    """重算所有 anchor sha256 写到 cache。返回 (新增, 更新, 删除) 计数。"""
    cache = load_anchor_cache(project_root)
    old = cache.get("anchors", {})
    new: dict[str, dict] = {}
    anchor_map = _collect_anchor_map(pages)

    n_add = 0
    n_upd = 0
    for ap, tracked in sorted(anchor_map.items()):
        target = (project_root / ap).resolve()
        sha = _file_sha256(target)
        if sha is None:
            continue
        try:
            size = target.stat().st_size
        except OSError:
            size = 0
        new[ap] = {"sha256": sha, "size": size, "tracked_pages": tracked}
        if ap not in old:
            n_add += 1
        elif old[ap].get("sha256") != sha:
            n_upd += 1
    n_del = len(set(old.keys()) - set(new.keys()))
    cache["anchors"] = new
    save_anchor_cache(project_root, cache)
    return n_add, n_upd, n_del


def show_anchor_cache(project_root: Path) -> str:
    cache = load_anchor_cache(project_root)
    anchors = cache.get("anchors", {})
    out = [
        f"anchor cache: {ANCHOR_CACHE_REL}",
        f"  version: {cache.get('version', '?')}",
        f"  updated_at: {cache.get('updated_at', '<never>')}",
        f"  entries: {len(anchors)}",
    ]
    if anchors:
        out.append("")
        out.append("  top 10 by tracked-page count:")
        items = sorted(anchors.items(), key=lambda kv: -len(kv[1].get("tracked_pages", [])))
        for ap, e in items[:10]:
            tp = e.get("tracked_pages", [])
            sha = e.get("sha256", "")[:10]
            out.append(f"    {ap}  sha={sha}  pages={len(tp)}")
    return "\n".join(out)


# ---------------------------------------------------------------------------
# ★v0.2★ 版本漂移检测（与 00-meta/project-versions.md 对账）
# ---------------------------------------------------------------------------

# 简单从 project-versions.md 抽提权威 UE / Python 版本
_RE_UE_AUTH = re.compile(r"EngineAssociation\s*\|\s*\*\*([0-9]+\.[0-9]+)\*\*")
_RE_PY_AUTH = re.compile(r"requires-python\`\s*\|\s*`>=\s*([0-9]+\.[0-9]+)")


def _load_authoritative_versions(docs_root: Path) -> dict[str, Optional[str]]:
    """从 00-meta/project-versions.md 抽 UE major.minor 与 Python major.minor。失败时 fallback hardcode。"""
    pv = docs_root / "00-meta" / "project-versions.md"
    ue = None
    py = None
    if pv.is_file():
        text = pv.read_text(encoding="utf-8")
        m = _RE_UE_AUTH.search(text)
        if m:
            ue = m.group(1)
        m = _RE_PY_AUTH.search(text)
        if m:
            py = m.group(1)
    return {"ue": ue or "5.7", "python": py or "3.11"}


# 检测页面里的版本号引用
# 注意：跳过 "X.Y+" 这种"最低版本"声明（带 + 后缀）；只查实指版本
_RE_UE_REF = re.compile(r"UE\s*([0-9]+\.[0-9]+)(?!\+)")
_RE_PY_REF = re.compile(r"[Pp]ython\s*([0-9]+\.[0-9]+)(?:\.[0-9]+)?(?!\+)")


def check_version_drift(pages: list[WikiPage], docs_root: Path) -> list[Issue]:
    auth = _load_authoritative_versions(docs_root)
    issues: list[Issue] = []
    for page in pages:
        if any(page.page_id.startswith(pref) for pref in VERSION_DRIFT_EXEMPT_PREFIXES):
            continue
        text = strip_code(page.text)
        # UE 版本
        for m in _RE_UE_REF.finditer(text):
            v = m.group(1)
            if v != auth["ue"]:
                line = text[:m.start()].count("\n") + 1
                issues.append(Issue(
                    code="version-drift",
                    severity="warn",
                    file=page.rel,
                    line=line,
                    detail=f"提到 UE {v}，权威值 UE {auth['ue']}（00-meta/project-versions.md）",
                ))
        # Python 版本
        for m in _RE_PY_REF.finditer(text):
            v = m.group(1)
            if v != auth["python"]:
                line = text[:m.start()].count("\n") + 1
                issues.append(Issue(
                    code="version-drift",
                    severity="warn",
                    file=page.rel,
                    line=line,
                    detail=f"提到 Python {v}，权威值 Python {auth['python']}",
                ))
    return issues


# ---------------------------------------------------------------------------
# ★v0.3★ 检查 11: menu_config 同 action 同 label 一致性
# ---------------------------------------------------------------------------
#
# 设计原则（来自 R17 真实事故）：
#   同一个 action（如 env.setup）在 menu_config.json 多处挂载时，**所有挂载点
#   的 label 必须完全相同**。否则用户视角下"两个不同 label = 两个不同动作"
#   会误选错路径。R17 修了一次：env.setup 同时被挂在 "Python开发工具/安装/
#   重建虚拟环境" 和 "工具Web平台/安装Web运行环境" → 用户全不知道是同一回事。
#
# 实现：
#   - 扫 MENU_CONFIG_FILES（共享菜单，必扫）+ MENU_CONFIG_LOCAL_FILES（local，
#     存在才扫）
#   - 递归 main_menu.items 收集所有 entry 的 (action, label, mount_path)
#   - 按 action 分组，若 label 集合 size > 1 → 报 menu-label-mismatch (warn)
#   - JSON 解析失败 / 缺 main_menu → 报 menu-config-invalid (error)


def _walk_menu_entries(items, trace, by_action):
    for it in items or []:
        if not isinstance(it, dict):
            continue
        t = it.get("type", "entry")
        label = it.get("label", "")
        name = it.get("name", "")
        cur = trace + [name or label or "?"]
        if t == "submenu":
            _walk_menu_entries(it.get("items", []), cur, by_action)
        elif t == "entry":
            action = it.get("action", "")
            if action:
                mount_path = " / ".join(cur)
                by_action.setdefault(action, []).append((label, name, mount_path))


def check_menu_action_label(project_root: Path) -> list[Issue]:
    """同 action 多挂载点必须同 label（R17 沉淀的设计原则）。"""
    issues: list[Issue] = []
    by_action: dict[str, list[tuple[str, str, str]]] = {}

    files_to_scan = list(MENU_CONFIG_FILES) + [
        f for f in MENU_CONFIG_LOCAL_FILES
        if (project_root / f).is_file()
    ]

    for rel in files_to_scan:
        cfg_path = project_root / rel
        if not cfg_path.is_file():
            if rel in MENU_CONFIG_FILES:
                # 必扫文件缺失 = 配置缺失（不报错，可能是非 UE 项目复用）
                continue
            continue
        try:
            cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            issues.append(Issue(
                code="menu-config-invalid",
                severity="error",
                file=rel,
                line=1,
                detail=f"JSON 解析失败: {e}",
            ))
            continue
        if not isinstance(cfg, dict):
            issues.append(Issue(
                code="menu-config-invalid",
                severity="error",
                file=rel,
                line=1,
                detail="顶层不是 object",
            ))
            continue
        main = cfg.get("main_menu", {})
        if not isinstance(main, dict):
            issues.append(Issue(
                code="menu-config-invalid",
                severity="error",
                file=rel,
                line=1,
                detail="main_menu 不是 object",
            ))
            continue
        root_label = main.get("label", "<root>")
        _walk_menu_entries(main.get("items", []), [root_label], by_action)

    for action, mounts in sorted(by_action.items()):
        labels = {m[0] for m in mounts}
        if len(labels) > 1:
            mount_str = "; ".join(f"[{m[2]}]→{m[0]!r}" for m in mounts)
            # ★v0.5★ 升 error(原 warn): R17 已证实是真用户体验事故源(用户因 label
            # 不一致点错菜单),团队达成"同 action 同 label"零容忍共识 → pre-commit 拦截
            issues.append(Issue(
                code="menu-label-mismatch",
                severity="error",
                file=MENU_CONFIG_FILES[0],
                line=1,
                detail=f"action {action!r} 在 {len(mounts)} 个挂载点 label 不一致: {mount_str}",
            ))

    return issues


# ---------------------------------------------------------------------------
# ★v0.4★ 检查 12: .bat 文件 chcp 之前必须 ASCII-only
# ---------------------------------------------------------------------------
#
# 问题（来自 R13/R14 真实事故，详见 80-gotchas/bat-launcher-bootstrap-pitfalls）：
#   cmd.exe 逐行流式 parse .bat 文件，从第 1 行起就用当前会话的 codepage（默认
#   936/GBK）解析。`chcp 65001` 是 cmd builtin，要等 parser 走到那一行才生效。
#   chcp 之前的行（包括 rem 注释）若含非 ASCII 字符 → cmd 用 GBK 解 UTF-8 字节
#   流 → 多字节字符边界错位 → 后续 ASCII 字符（包括 `&` `|` `(` `)`）可能被
#   吞进高字节，parser 状态错乱，报 "'ools' 不是内部或外部命令" 之类错误。
#
# 实现：
#   - 扫所有项目 .bat（排除 BAT_SCAN_EXCLUDE_PREFIXES 下的运行期生成 / 第三方）
#   - 找第一处 `chcp` 行号
#   - 有 chcp，但前面行有非 ASCII → bat-non-ascii-before-chcp (warn)
#   - 无 chcp，且全文有非 ASCII → bat-missing-chcp (warn)
#   - 全 ASCII（无论有无 chcp）→ 不报警


def check_bat_chcp_ascii(project_root: Path) -> list[Issue]:
    issues: list[Issue] = []
    for p in sorted(project_root.rglob("*.bat")):
        try:
            rel = p.relative_to(project_root).as_posix()
        except ValueError:
            continue
        if any(rel.startswith(x) for x in BAT_SCAN_EXCLUDE_PREFIXES):
            continue
        try:
            raw = p.read_bytes()
        except OSError:
            continue
        has_non_ascii = any(b >= 0x80 for b in raw)
        if not has_non_ascii:
            continue
        try:
            text = raw.decode("utf-8", errors="replace")
        except Exception:
            continue
        chcp_line: Optional[int] = None
        lines = text.splitlines()
        for i, line in enumerate(lines, 1):
            if "chcp" in line.lower():
                chcp_line = i
                break

        if chcp_line is None:
            issues.append(Issue(
                code="bat-missing-chcp",
                severity="warn",
                file=rel,
                line=1,
                detail="文件含非 ASCII 字符但缺 `chcp 65001`，cmd.exe 在默认 codepage 下可能 mojibake 或 parse 失败（详见 80-gotchas/bat-launcher-bootstrap-pitfalls P3）",
            ))
            continue

        for i, line in enumerate(lines[:chcp_line - 1], 1):
            if any(ord(c) >= 0x80 for c in line):
                issues.append(Issue(
                    code="bat-non-ascii-before-chcp",
                    severity="warn",
                    file=rel,
                    line=i,
                    detail=f"`chcp 65001` 在 L{chcp_line}，但本行（L{i}）含非 ASCII 字符 → cmd 用默认 codepage 解析会错位（rem 注释一律 ASCII，中文只允许在 chcp 之后）",
                ))
    return issues


# ---------------------------------------------------------------------------
# ★v0.4★ 检查 13: last_synced 过期警告
# ---------------------------------------------------------------------------
#
# 问题：wiki 页 frontmatter 的 last_synced 字段记录"上次与代码同步"的日期。
# 时间一长，代码可能演化但 wiki 没跟进 → 静默 stale。anchor-changed 检测 sha256
# 漂移有用，但仅覆盖 anchor 文件；纯讨论性 / topic / runbook 类页面没有 anchor
# 也需要定期 re-verify。
#
# 实现：
#   - 跑过 LAST_SYNCED_STALE_DAYS（默认 180 天）阈值的页 → last-synced-stale (warn)
#   - status: stale 已经被 check_status 报 → 这里只关注 status 还是 current 但
#     last_synced 太老的（即"自认为还现行但很久没复核"）
#   - 没 frontmatter 的元页豁免


def _parse_iso_date(s) -> Optional[date]:
    if not s:
        return None
    if isinstance(s, date):
        return s
    if not isinstance(s, str):
        return None
    try:
        return date.fromisoformat(s.strip()[:10])
    except (ValueError, TypeError):
        return None


def check_last_synced_stale(pages: list[WikiPage]) -> list[Issue]:
    issues: list[Issue] = []
    today = date.today()
    for p in pages:
        if not p.has_fm:
            continue
        st = p.fm.get("status", "")
        if st in ("stale", "deprecated", "draft"):
            continue
        last = _parse_iso_date(p.fm.get("last_synced"))
        if last is None:
            continue
        days = (today - last).days
        if days > LAST_SYNCED_STALE_DAYS:
            issues.append(Issue(
                code="last-synced-stale",
                severity="warn",
                file=p.rel,
                line=1,
                detail=f"last_synced={last.isoformat()} 距今 {days} 天 (> {LAST_SYNCED_STALE_DAYS}) → 建议 re-verify 后更新 last_synced/last_verified",
            ))
    return issues


# ---------------------------------------------------------------------------
# ★v0.4★ 检查 14: 同名实体跨页冲突检测
# ---------------------------------------------------------------------------
#
# 问题：相同标题或同 anchor 路径出现在多个 wiki 页 → 用户 / AI 不知道该看哪
# 一个，容易引起认知混乱。例如两页都叫 "## 数据流" 不算冲突（结构性子标题
# 普遍）；但两页都叫 "# 模块: Tools.common.menu_actions" 就冲突。
#
# 实现：
#   - 同 anchor path 在多页 frontmatter 出现 → duplicate-entity (warn)
#   - 同 H1 标题（去掉 #）在多页出现 → duplicate-entity (warn)
#   - 短标题 (< DUPLICATE_ENTITY_MIN_TITLE_LEN) 跳过避免误报
#   - DUPLICATE_ENTITY_EXEMPT_PREFIXES 下的页全跳过（meta / 设计文档结构性引用）


def _extract_h1(text: str) -> Optional[str]:
    body = text
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            body = text[end + 4:]
    for line in body.splitlines():
        s = line.strip()
        if s.startswith("# ") and not s.startswith("## "):
            return s[2:].strip()
        if s.startswith("#") and not s.startswith("##"):
            return s.lstrip("#").strip()
    return None


def check_duplicate_entity(pages: list[WikiPage]) -> list[Issue]:
    issues: list[Issue] = []

    def is_exempt(page_id: str) -> bool:
        return any(page_id.startswith(pref) for pref in DUPLICATE_ENTITY_EXEMPT_PREFIXES)

    title_pages: dict[str, list[str]] = {}
    for p in pages:
        if is_exempt(p.page_id):
            continue
        title = _extract_h1(p.text)
        if title is None or len(title) < DUPLICATE_ENTITY_MIN_TITLE_LEN:
            continue
        norm = title.strip().lower()
        title_pages.setdefault(norm, []).append(p.page_id)

    for title, page_ids in sorted(title_pages.items()):
        if len(page_ids) > 1:
            issues.append(Issue(
                code="duplicate-entity",
                severity="warn",
                file=f"{DOCS_DIR}/{page_ids[0]}.md",
                line=1,
                detail=f"H1 标题 {title!r} 在 {len(page_ids)} 个页面重复: {page_ids}（建议合并或差异化 H1）",
            ))

    # 注：anchor 路径"多页共享"是设计预期（同一代码文件可有模块页 + ADR + gotcha
    # 多视角 anchor），不算冲突。R19 评估实数据：项目里 45 例 anchor 重复全是
    # 健康的"多视角覆盖"，0 例真冲突 → 不检测 anchor 重复。
    # 真出现"两个不同模块页讲同一个文件"会被 H1 标题重复抓住（更准）。

    return issues


# ---------------------------------------------------------------------------
# ★v0.5★ 检查 15: prerequisites 字段一致性
# ---------------------------------------------------------------------------
#
# 设计意图:
#   frontmatter 的 prerequisites: 字段当前都是自然语言描述(工具版本 / 外部
#   条件 / 已读文档等),但有些"已读 X 文档"的描述如果用 [[wiki-id]] 形式引用
#   就能被工具校验"目标页是否存在 + 是否还现行"。本检查不强制改写现有自然
#   语言条目,但只要某条目里包含 [[id]] wikilink,就 verify:
#     - 目标页必须存在(broken-link 已覆盖正文,这里覆盖 frontmatter)
#     - 目标页 status 不能是 stale/deprecated(否则 prereq 引了过期文档)
#
# 同时校验 prerequisites 字段类型:
#   - 必须是 list(YAML 数组),不能是 str / dict / null
#   - list 中每项必须是 str
#
# 实现:
#   - 跑过 frontmatter 提取 prereq list
#   - 字段类型不对 → prerequisites-mismatch (warn) "字段类型应为 list of str"
#   - 每项中 re.findall [[id]],对每个 id:
#     - 不在 page_set → prerequisites-mismatch (warn) "引用 [[X]] 不存在"
#     - target.status in (stale, deprecated) → prerequisites-mismatch (warn)
#       "引用 [[X]] 已 stale/deprecated"


def check_prerequisites(pages: list[WikiPage]) -> list[Issue]:
    issues: list[Issue] = []
    page_index = {p.page_id: p for p in pages}

    for p in pages:
        if not p.has_fm:
            continue
        prereq = p.fm.get("prerequisites")
        if prereq is None:
            continue
        if not isinstance(prereq, list):
            issues.append(Issue(
                code="prerequisites-mismatch",
                severity="warn",
                file=p.rel,
                line=1,
                detail=f"prerequisites 字段类型应为 list of str,实际为 {type(prereq).__name__}",
            ))
            continue
        for idx, item in enumerate(prereq, 1):
            if not isinstance(item, str):
                issues.append(Issue(
                    code="prerequisites-mismatch",
                    severity="warn",
                    file=p.rel,
                    line=1,
                    detail=f"prerequisites[{idx}] 类型应为 str,实际为 {type(item).__name__}",
                ))
                continue
            for m in re.finditer(r"\[\[([^\]]+)\]\]", item):
                target_id = m.group(1).split("|")[0].split("#")[0].strip()
                if not target_id:
                    continue
                target = page_index.get(target_id)
                if target is None:
                    issues.append(Issue(
                        code="prerequisites-mismatch",
                        severity="warn",
                        file=p.rel,
                        line=1,
                        detail=f"prerequisites[{idx}] 引用的 [[{target_id}]] 不存在",
                    ))
                    continue
                target_status = target.fm.get("status", "") if target.has_fm else ""
                if target_status in ("stale", "deprecated"):
                    issues.append(Issue(
                        code="prerequisites-mismatch",
                        severity="warn",
                        file=p.rel,
                        line=1,
                        detail=f"prerequisites[{idx}] 引用的 [[{target_id}]] status={target_status},不应作为前置(应先升级该页或换引用)",
                    ))
    return issues


# ---------------------------------------------------------------------------
# ★v0.6★ 检查 18: Docs/log.md R<n> 编号段落顺序
# ---------------------------------------------------------------------------
#
# 问题(R23/R24 真实事故):
#   连续 N 次 crystallize 段用 StrReplace 以"下一段段头"作 anchor 在它前面插入,
#   导致顺序倒置(R20 后变 R23 → R22 → R21)。用户从顶部顺读以为最近的没写。
#
# 设计:
#   只在 Docs/log.md 检查,解析所有 `## [YYYY-MM-DD] <action> | R<n>:` 段头,
#   按文件出现顺序提取 R 编号列表,相邻对若 prev > cur(逆序)即报 warn。
#   不要求 R 编号连续(允许跳号 R20 → R23,只要单调递增)。
#   单段 / 0 段 / 文件不存在 → 不报。
#
# 校验对象:
#   只校验单调性(R<n> 段),非 R 编号段(如 init / verify 类)不参与排序判定。
#   见 Docs/00-meta/ai-playbook §2.4.1


LOG_ORDER_RE = re.compile(r"^##\s+\[\d{4}-\d{2}-\d{2}\][^|]*\|\s*R(\d+)\b")


def check_log_order(docs_root: Path) -> list[Issue]:
    issues: list[Issue] = []
    log_path = docs_root / "log.md"
    if not log_path.is_file():
        return issues
    try:
        text = log_path.read_text(encoding="utf-8")
    except OSError:
        return issues

    # ★v0.7★ pre-v0.7-baseline 区块的 R 顺序错乱视作历史遗产，不报
    baseline_begin = text.find("<!-- pre-v0.7-baseline:begin -->")
    baseline_end = text.find("<!-- pre-v0.7-baseline:end -->")

    entries: list[tuple[int, int]] = []  # (line_no, R_num)
    for i, line in enumerate(text.splitlines(), 1):
        m = LOG_ORDER_RE.match(line)
        if m:
            offset = sum(len(ln) + 1 for ln in text.splitlines()[:i - 1])
            if baseline_begin >= 0 and baseline_end >= 0 and baseline_begin < offset < baseline_end:
                continue
            entries.append((i, int(m.group(1))))

    if len(entries) < 2:
        return issues

    for (prev_line, prev_n), (cur_line, cur_n) in zip(entries, entries[1:]):
        if cur_n < prev_n:
            issues.append(Issue(
                code="log-order",
                severity="warn",
                file="Docs/log.md",
                line=cur_line,
                detail=(
                    f"R{cur_n} 段(L{cur_line})出现在 R{prev_n} 段(L{prev_line})之后,但 R 编号倒序。"
                    f"应按 R 编号递增 append(见 ai-playbook §2.4.1)"
                ),
            ))
    return issues


# ---------------------------------------------------------------------------
# ★★★v0.7★★★ log.d/ 多人 append + rollup 规则
# ---------------------------------------------------------------------------
#
# 设计意图（参考 ADR-0006 + ai-playbook §2.4.1 v0.7 改写）：
#
#   v0.7 起，新 log 段 must 写到 Docs/log.d/log-<git-user>.md（per-human 分文件，
#   零并发冲突），主 Docs/log.md 只由 log_rollup.py 写。本组规则确保团队不会回退到
#   "所有人都 append log.md → merge 冲突 / R 编号撞车"的老路。
#
# 4 条规则：
#
#   18. log-fragment-required    ERROR
#       v0.7+ 段头必须有 <owner> 字段，例 "## [2026-05-15 14:30] alice crystallize | R32 ..."
#       覆盖范围：log.d/log-*.md 所有段 + 主 log.md ROLLUP_MARK 区块内段
#       豁免：BASELINE_MARK 区块内（pre-v0.7 历史段）
#
#   19. log-fragment-mergeable   WARN
#       log.d/log-<X>.md 段头 owner 字段 ≠ <X>（文件名 owner）
#       触发原因：copy-paste 段头时忘改 owner；或脚本 / hook 误写
#
#   20. log-md-rollup-needed     WARN
#       log.d/log-*.md 文件 mtime > 主 log.md mtime → 提示跑 log_rollup.py --apply
#       豁免：log.d/ 全空（无段）/ log.md 没有 BASELINE_MARK（还没首次 rollup）
#
#   21. log-orphan-wiki-touched  WARN
#       log.d/ 段正文里出现的 [[wiki-page-id]] 在 wiki 实际不存在（broken-link 类似
#       但作用域限定在 log.d/）。常见原因：段里写了"修改了 X" 但 X page_id 写错。
#       这条比 broken-link 范围窄，仅检查 log.d/，因为 log.d/ 可能引未来还没建的页
#       （未来段），所以只 WARN，提示 review。

LOG_FRAGMENT_HEADER_RE = re.compile(
    r"^##\s+\[(\d{4}-\d{2}-\d{2})(?:\s+\d{2}:\d{2})?\]\s+(.+)$",
    re.MULTILINE,
)
LOG_OWNER_ACTION_KEYWORDS = {
    "crystallize", "ingest", "verify", "lint", "init", "digest", "rollup",
    "design", "refactor", "fix", "feat", "docs",
}
WIKILINK_IN_LOG_RE = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]*)?(?:\|[^\]]*)?\]\]")


def _split_log_md_by_marks(text: str) -> tuple[str, str, str]:
    """返回 (preamble, baseline_block, rollup_block)。任何块不存在则返回 ""。"""
    bm_begin = text.find("<!-- pre-v0.7-baseline:begin -->")
    bm_end = text.find("<!-- pre-v0.7-baseline:end -->")
    rm_begin = text.find("<!-- rollup:begin -->")
    rm_end = text.find("<!-- rollup:end -->")
    baseline = ""
    rollup = ""
    if bm_begin >= 0 and bm_end >= 0:
        baseline = text[bm_begin:bm_end + len("<!-- pre-v0.7-baseline:end -->")]
    if rm_begin >= 0 and rm_end >= 0:
        rollup = text[rm_begin:rm_end + len("<!-- rollup:end -->")]
    first_mark = min((x for x in [bm_begin, rm_begin] if x >= 0), default=len(text))
    preamble = text[:first_mark]
    return preamble, baseline, rollup


def _parse_log_segments(text: str, source_file: str) -> list[dict]:
    """返回 [{date, header, owner, body, line, source}]。"""
    out = []
    lines = text.splitlines()
    cur = None
    for i, ln in enumerate(lines, 1):
        m = LOG_FRAGMENT_HEADER_RE.match(ln)
        if m:
            if cur:
                out.append(cur)
            head = m.group(2).strip()
            owner = ""
            parts = head.split()
            if len(parts) >= 2 and parts[1].lower() in LOG_OWNER_ACTION_KEYWORDS:
                owner = parts[0]
            cur = {
                "date": m.group(1),
                "header": head,
                "owner": owner,
                "body": [],
                "line": i,
                "source": source_file,
            }
        elif cur is not None:
            cur["body"].append(ln)
    if cur:
        out.append(cur)
    for seg in out:
        seg["body"] = "\n".join(seg["body"])
    return out


def check_log_fragment_v07(pages: list[WikiPage], docs_root: Path) -> list[Issue]:
    """v0.7 四条 log 规则合并实现。"""
    issues: list[Issue] = []
    log_md = docs_root / "log.md"
    log_d = docs_root / "log.d"

    page_ids = {p.page_id for p in pages} | collect_raw_ids(docs_root)

    # —— 规则 20: rollup-needed ——
    if log_md.is_file() and log_d.is_dir():
        try:
            log_md_text = log_md.read_text(encoding="utf-8")
        except OSError:
            log_md_text = ""
        log_d_files = list(log_d.glob("log-*.md"))
        if log_d_files and "<!-- pre-v0.7-baseline:begin -->" in log_md_text:
            log_md_mtime = log_md.stat().st_mtime
            newer = [p for p in log_d_files if p.stat().st_mtime > log_md_mtime]
            if newer:
                issues.append(Issue(
                    code="log-md-rollup-needed",
                    severity="warn",
                    file="Docs/log.md",
                    line=0,
                    detail=(
                        f"log.d/ 有 {len(newer)} 个分文件比 log.md 新，"
                        f"建议跑 `python .codebuddy/skills/project-wiki/scripts/log_rollup.py --apply` 合并。"
                        f"新于 log.md 的: {', '.join(p.name for p in newer[:3])}"
                        + (f" 等 {len(newer)} 个" if len(newer) > 3 else "")
                    ),
                ))

    # —— 规则 18 + 19 + 21: 解析 log.d/ 每个文件 ——
    if log_d.is_dir():
        for fp in sorted(log_d.glob("log-*.md")):
            try:
                txt = fp.read_text(encoding="utf-8")
            except OSError:
                continue
            file_owner = fp.stem.removeprefix("log-")
            rel = f"Docs/log.d/{fp.name}"
            segs = _parse_log_segments(txt, source_file=rel)
            for seg in segs:
                if not seg["owner"]:
                    issues.append(Issue(
                        code="log-fragment-required",
                        severity="error",
                        file=rel, line=seg["line"],
                        detail=(
                            f"段头缺 <owner> 字段（v0.7 强制）。"
                            f"应为 `## [{seg['date']} HH:MM] {file_owner} <action> | R<n>: <summary>`。"
                            f"实际 header: '{seg['header']}'"
                        ),
                    ))
                elif seg["owner"] != file_owner:
                    issues.append(Issue(
                        code="log-fragment-mergeable",
                        severity="warn",
                        file=rel, line=seg["line"],
                        detail=(
                            f"段头 owner={seg['owner']!r} 与文件名 owner={file_owner!r} 不一致。"
                            f"rollup 时会以文件名为准，但 review 中容易引起混乱。"
                        ),
                    ))
                # 规则 21: log.d/ 段提到的 wikilink 是否存在
                # 先剥离 code block / inline code，避免对 `[[X]]` 这种 placeholder 误报
                body_no_code = strip_code(seg["body"])
                for m in WIKILINK_IN_LOG_RE.finditer(body_no_code):
                    target = m.group(1).strip()
                    if target not in page_ids:
                        issues.append(Issue(
                            code="log-orphan-wiki-touched",
                            severity="warn",
                            file=rel, line=seg["line"],
                            detail=(
                                f"段提到 [[{target}]] 但 wiki 不存在该页。"
                                f"若是 work-in-progress（未建页）→ 忽略；若是 typo / 已 rename → 修正"
                            ),
                        ))

    # —— 规则 18 还覆盖：主 log.md ROLLUP_MARK 区块内段 ——
    if log_md.is_file():
        try:
            txt = log_md.read_text(encoding="utf-8")
        except OSError:
            txt = ""
        _, _, rollup_block = _split_log_md_by_marks(txt)
        if rollup_block:
            offset_line_start = txt[:txt.find(rollup_block)].count("\n") + 1
            for seg in _parse_log_segments(rollup_block, "Docs/log.md"):
                if not seg["owner"]:
                    issues.append(Issue(
                        code="log-fragment-required",
                        severity="error",
                        file="Docs/log.md",
                        line=offset_line_start + seg["line"],
                        detail=(
                            f"ROLLUP 区块内段头缺 <owner> 字段。"
                            f"主 log.md ROLLUP 区只能由 log_rollup.py 写入，不应手工修改。header: '{seg['header']}'"
                        ),
                    ))

    return issues


# ---------------------------------------------------------------------------
# ★v0.6★ 检查 19: frontmatter related: 字段一致性
# ---------------------------------------------------------------------------
#
# 设计意图:
#   broken-link 已检测正文 + frontmatter 中所有 [[X]] 的"目标存在性"(severity=error),
#   但有两件事它不覆盖:
#     1. 类型校验:related: 必须是 list of str,误写成 str / dict 时 broken-link 抓不住
#     2. 状态校验:related 引了 status=stale|deprecated 的页 → 设计上是有问题的
#        (related 应该指向 current 的同伴页面)
#   本检查与 prerequisites-mismatch 同结构,但聚焦 related 字段。warn 级,不拦截。
#
# 实现:
#   - 字段类型不对(非 list) → related-mismatch warn
#   - 列表项非 str → warn
#   - 项内 [[id]] target 不存在 → 不重复报(broken-link 已 error 抓住)
#   - 项内 [[id]] target.status in (stale, deprecated) → warn


def check_related_links(pages: list[WikiPage]) -> list[Issue]:
    issues: list[Issue] = []
    page_index = {p.page_id: p for p in pages}

    for p in pages:
        if not p.has_fm:
            continue
        related = p.fm.get("related")
        if related is None:
            continue
        if not isinstance(related, list):
            issues.append(Issue(
                code="related-mismatch",
                severity="warn",
                file=p.rel,
                line=1,
                detail=f"related 字段类型应为 list of str,实际为 {type(related).__name__}",
            ))
            continue
        for idx, item in enumerate(related, 1):
            if not isinstance(item, str):
                issues.append(Issue(
                    code="related-mismatch",
                    severity="warn",
                    file=p.rel,
                    line=1,
                    detail=f"related[{idx}] 类型应为 str,实际为 {type(item).__name__}",
                ))
                continue
            for m in re.finditer(r"\[\[([^\]]+)\]\]", item):
                target_id = m.group(1).split("|")[0].split("#")[0].strip()
                if not target_id:
                    continue
                target = page_index.get(target_id)
                if target is None:
                    # broken-link (error) 已覆盖,这里不重复报
                    continue
                target_status = target.fm.get("status", "") if target.has_fm else ""
                if target_status in ("stale", "deprecated"):
                    issues.append(Issue(
                        code="related-mismatch",
                        severity="warn",
                        file=p.rel,
                        line=1,
                        detail=(
                            f"related[{idx}] 引用 [[{target_id}]] status={target_status},"
                            f"建议先升级该页或换引用(related 应指向 current 同伴页)"
                        ),
                    ))
    return issues


# ---------------------------------------------------------------------------
# ★v1.0★ 检查 24: 30-tutorials/ 教程 frontmatter 专项检查
# ---------------------------------------------------------------------------
#
# 设计意图:
#   30-tutorials/ 下的教程文件有额外的 frontmatter 规范要求(series / lesson_index /
#   difficulty / title / description / prerequisites / type 值限定)。这些字段对教程
#   系列导航和学习路线至关重要。原由独立脚本 ToolsScript/check_frontmatter.py 检查,
#   现整合到 wiki_lint 统一流程,pre-commit 可拦截。
#
# ERROR 级(pre-commit 拦截):
#   - type 不是 guide/tutorial
#   - 缺少 series / lesson_index / difficulty
#   - difficulty 值不合法
#   - 缺少 title / description / prerequisites
#   - title 与 H1 不一致
#
# 修复(--fix):
#   - type: overview 文件 → guide, 其他 → tutorial
#   - title: 从 H1 提取
#   - description: 从 index.md 查找
#   - series: 从 _series.yaml slug 字段读取
#   - lesson_index: 从文件路径计算
#   - difficulty: 缺失默认 intermediate
#   - prerequisites: overview 文件 [], 其他为同系列上一文件

TUTORIALS_SUBDIR = "30-tutorials/"
VALID_TUTORIAL_TYPE = {"tutorial", "guide"}
VALID_TUTORIAL_DIFFICULTY = {"beginner", "intermediate", "advanced"}


def _is_tutorial_page(page: WikiPage) -> bool:
    """判断页面是否属于 30-tutorials/ 目录"""
    return page.page_id.startswith(TUTORIALS_SUBDIR)


def _tutorial_extract_h1(text: str) -> str:
    """从正文提取第一个一级标题(跳过 frontmatter)"""
    body = text
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            body = text[end + 4:]
    m = re.search(r"^[ \t]*#[ \t]+(.+?)\s*$", body, re.MULTILINE)
    return m.group(1).strip() if m else ""


def _tutorial_parse_index_descriptions(docs_root: Path) -> dict[str, str]:
    """从 Docs/index.md 解析 [[path]] - description 格式的描述映射"""
    index_file = docs_root / "index.md"
    descriptions: dict[str, str] = {}
    if not index_file.is_file():
        return descriptions
    content = index_file.read_text(encoding="utf-8")
    pattern = re.compile(r"\[\[([^\]]+)\]\]\s*-\s*(.+)")
    for m in pattern.finditer(content):
        descriptions[m.group(1).strip()] = m.group(2).strip()
    return descriptions


def _tutorial_find_series_slug(page: WikiPage, docs_root: Path) -> str:
    """查找教程页面所属系列的 slug(从 _series.yaml 读取, 纯 regex 无 yaml 依赖)"""
    tutorials_root = docs_root / "30-tutorials"
    rel_in_tutorials = page.page_id[len(TUTORIALS_SUBDIR):]
    series_dir_name = rel_in_tutorials.split("/")[0]
    series_yaml = tutorials_root / series_dir_name / "_series.yaml"
    if series_yaml.is_file():
        try:
            content = series_yaml.read_text(encoding="utf-8")
            m = re.search(r"^slug:\s*(.+)$", content, re.MULTILINE)
            if m:
                return m.group(1).strip().strip("'\"")
        except OSError:
            pass
    return series_dir_name


def _tutorial_compute_lesson_index(page: WikiPage) -> Optional[int]:
    """根据文件路径计算 lesson_index
    - 直接在系列目录: 文件名数字前缀 (00-overview.md → 0)
    - 数字前缀子目录: 子目录前缀*100 + 文件前缀 (10-engine-layer/00-x.md → 1000)
    - 非数字子目录: 100 + 文件前缀 (iris/00-x.md → 100)
    """
    rel_in_tutorials = page.page_id[len(TUTORIALS_SUBDIR):]
    parts = rel_in_tutorials.split("/")
    # parts: ['gas', '01-ga-overview'] or ['ue-framework', '10-engine-layer', '00-engines']

    filename = parts[-1]  # 不含 .md (page_id 已去除)
    file_match = re.match(r"^(\d+)", filename)
    if not file_match:
        return None
    file_num = int(file_match.group(1))

    if len(parts) > 2:
        subdir = parts[1]
        subdir_match = re.match(r"^(\d+)", subdir)
        if subdir_match:
            return int(subdir_match.group(1)) * 100 + file_num
        else:
            return 100 + file_num

    return file_num


def _tutorial_compute_prerequisites(page: WikiPage, tutorial_pages: list[WikiPage]) -> list[str]:
    """计算 prerequisites: overview 文件返回 [], 其他返回同系列上一个文件的 id"""
    filename = page.path.name
    if "overview" in filename:
        return []

    rel_in_tutorials = page.page_id[len(TUTORIALS_SUBDIR):]
    series_dir_name = rel_in_tutorials.split("/")[0]

    # 筛选同系列文件并排序
    series_files = []
    for p in tutorial_pages:
        p_rel = p.page_id[len(TUTORIALS_SUBDIR):]
        if p_rel.split("/")[0] == series_dir_name:
            idx = _tutorial_compute_lesson_index(p)
            series_files.append((idx if idx is not None else 9999, p))

    series_files.sort(key=lambda x: x[0])

    current_idx = _tutorial_compute_lesson_index(page)
    prev_page = None
    for idx, p in series_files:
        if p.page_id == page.page_id:
            break
        prev_page = p

    if prev_page is None:
        return []
    return [prev_page.page_id]


def check_tutorial_frontmatter(pages: list[WikiPage]) -> list[Issue]:
    """检查 30-tutorials/ 下教程文件的 frontmatter 规范(全部 ERROR 级)"""
    issues: list[Issue] = []
    for page in pages:
        if not _is_tutorial_page(page):
            continue
        if not page.has_fm:
            continue  # missing-fm 由通用 check_frontmatter 报告
        if page.is_meta_file:
            continue

        fm = page.fm

        # type 必须是 guide 或 tutorial
        ptype = fm.get("type", "")
        if ptype and ptype not in VALID_TUTORIAL_TYPE:
            issues.append(Issue(
                code="tutorial-fm",
                severity="error",
                file=page.rel,
                line=1,
                detail=f"type='{ptype}' 不合法,教程文件 type 必须为 guide 或 tutorial",
            ))

        # 必填字段: series
        if "series" not in fm or not fm.get("series"):
            issues.append(Issue(
                code="tutorial-fm",
                severity="error",
                file=page.rel,
                line=1,
                detail="缺少必填字段 'series'",
            ))

        # 必填字段: lesson_index
        if "lesson_index" not in fm or fm.get("lesson_index") is None:
            issues.append(Issue(
                code="tutorial-fm",
                severity="error",
                file=page.rel,
                line=1,
                detail="缺少必填字段 'lesson_index'",
            ))

        # 必填字段: difficulty
        diff = fm.get("difficulty", "")
        if not diff:
            issues.append(Issue(
                code="tutorial-fm",
                severity="error",
                file=page.rel,
                line=1,
                detail="缺少必填字段 'difficulty'",
            ))
        elif diff not in VALID_TUTORIAL_DIFFICULTY:
            issues.append(Issue(
                code="tutorial-fm",
                severity="error",
                file=page.rel,
                line=1,
                detail=f"difficulty='{diff}' 不合法,应为 {VALID_TUTORIAL_DIFFICULTY}",
            ))

        # 必填字段: title
        if "title" not in fm or not fm.get("title"):
            issues.append(Issue(
                code="tutorial-fm",
                severity="error",
                file=page.rel,
                line=1,
                detail="缺少必填字段 'title'",
            ))

        # 必填字段: description
        if "description" not in fm or not fm.get("description"):
            issues.append(Issue(
                code="tutorial-fm",
                severity="error",
                file=page.rel,
                line=1,
                detail="缺少必填字段 'description'",
            ))

        # 必填字段: prerequisites
        if "prerequisites" not in fm:
            issues.append(Issue(
                code="tutorial-fm",
                severity="error",
                file=page.rel,
                line=1,
                detail="缺少必填字段 'prerequisites'",
            ))

        # title 与 H1 一致性
        title = fm.get("title", "")
        h1 = _tutorial_extract_h1(page.text)
        if title and h1 and title.strip() != h1.strip():
            issues.append(Issue(
                code="tutorial-fm",
                severity="error",
                file=page.rel,
                line=1,
                detail=f"title 与 H1 不一致: title='{title[:40]}' vs H1='{h1[:40]}'",
            ))

    return issues


# ---------------------------------------------------------------------------
# 检查 10 (v1.2): 30-tutorials/ 内部引用闭合性
# ---------------------------------------------------------------------------

# 这些 wikilink 目标是导航/元文件，允许从教程引用（不算外部引用）
_TUTORIAL_REF_EXEMPT_TARGETS = {"index", "overview"}


def check_tutorial_internal_refs(pages: list[WikiPage]) -> list[Issue]:
    """检查 30-tutorials/ 下教程**正文** wikilink 是否指向 30-tutorials/ 内部页面。

    规则演进：
    - v1.2 起初：教程任何 wikilink 引外部 → ERROR
    - v1.3（ADR-0005 决策后）：图谱完备性 vs 读者可达性分层处理
        * frontmatter `related` / `prerequisites` / `sources` 中引外部 → 豁免
          （图谱性引用，由 web-app remark plugin 在渲染期降级为不可点击文本）
        * 教程**正文** wikilink 引外部 → 仍报但**降级为 WARN**
          （读者点击会 404，提倡用普通文本；但不再硬性 ERROR）

    详见 [[60-decisions/0005-tutorial-cross-link-policy]]。
    """
    issues: list[Issue] = []
    for page in pages:
        if not _is_tutorial_page(page):
            continue
        # 剥离 frontmatter 后再扫——frontmatter 内 related/prereq 的外部引用属于豁免范围
        text = page.text
        if page.fm_lines > 0:
            lines = text.splitlines(keepends=True)
            body = "".join(lines[page.fm_lines:])
            line_offset = page.fm_lines
        else:
            body = text
            line_offset = 0
        clean = strip_code(body)
        for m in WIKILINK_RE.finditer(clean):
            target = m.group(1).strip()
            # 豁免：导航/元文件（index、overview）
            if target in _TUTORIAL_REF_EXEMPT_TARGETS:
                continue
            # 合规：引用 30-tutorials/ 内部页面
            if target.startswith(TUTORIALS_SUBDIR):
                continue
            # 违规：教程正文 wikilink 引外部 → WARN（提倡用普通文本或不挂跳转）
            line_no = (
                clean[: clean.find(m.group(0))].count("\n") + 1 + line_offset
                if m.group(0) in clean
                else 0
            )
            issues.append(Issue(
                code="tutorial-ext-ref",
                severity="warn",
                file=page.rel,
                line=line_no,
                detail=(
                    f"教程正文 wikilink [[{target}]] 引用了外部页面"
                    f"（web-app 渲染时会显示为不可点击文本）；"
                    "frontmatter related/prereq/sources 中的外部引用已豁免（图谱性引用）"
                ),
            ))
    return issues


def fix_tutorial_frontmatter(pages: list[WikiPage], docs_root: Path) -> list[str]:
    """修复 30-tutorials/ 下教程文件的 frontmatter。返回修改过的文件 rel 路径列表。"""
    tutorial_pages = [p for p in pages if _is_tutorial_page(p) and p.has_fm and not p.is_meta_file]
    if not tutorial_pages:
        return []

    index_descs = _tutorial_parse_index_descriptions(docs_root)
    changed: list[str] = []

    for page in tutorial_pages:
        fm = page.fm
        text = page.text
        modified = False

        # 1. 修复 type
        ptype = fm.get("type", "")
        if not ptype or ptype not in VALID_TUTORIAL_TYPE:
            new_type = "guide" if "overview" in page.path.name else "tutorial"
            if "type" in fm:
                text = re.sub(r"^type:\s*.*$", f"type: {new_type}", text, count=1, flags=re.MULTILINE)
            else:
                text = _insert_fm_field(text, "type", new_type)
            fm["type"] = new_type
            modified = True

        # 2. 修复 title
        if "title" not in fm or not fm.get("title"):
            h1 = _tutorial_extract_h1(text)
            if h1:
                text = _insert_fm_field(text, "title", h1)
                fm["title"] = h1
                modified = True

        # 3. 修复 description
        if "description" not in fm or not fm.get("description"):
            desc = index_descs.get(page.page_id, "")
            if desc:
                text = _insert_fm_field(text, "description", desc)
                fm["description"] = desc
                modified = True

        # 4. 修复 series
        if "series" not in fm or not fm.get("series"):
            slug = _tutorial_find_series_slug(page, docs_root)
            text = _insert_fm_field(text, "series", slug)
            fm["series"] = slug
            modified = True

        # 5. 修复 lesson_index
        if "lesson_index" not in fm or fm.get("lesson_index") is None:
            idx = _tutorial_compute_lesson_index(page)
            if idx is not None:
                text = _insert_fm_field(text, "lesson_index", str(idx))
                fm["lesson_index"] = idx
                modified = True

        # 6. 修复 difficulty
        if "difficulty" not in fm or not fm.get("difficulty"):
            text = _insert_fm_field(text, "difficulty", "intermediate")
            fm["difficulty"] = "intermediate"
            modified = True

        # 7. 修复 prerequisites
        if "prerequisites" not in fm:
            prereqs = _tutorial_compute_prerequisites(page, tutorial_pages)
            if not prereqs:
                text = _insert_fm_field(text, "prerequisites", "[]")
            else:
                text = _insert_fm_field(text, "prerequisites", f"[{prereqs[0]}]")
            fm["prerequisites"] = prereqs
            modified = True

        if modified:
            page.path.write_text(text, encoding="utf-8")
            changed.append(page.rel)

    return changed


def check_nav_block(pages: list[WikiPage]) -> list[Issue]:
    """检测 wiki 页面是否有尾部导航块 (<!-- nav:auto -->)。
    
    v0.8 新增。确保页面底部包含导航块，方便用户在 wiki 间顺序浏览。
    跳过：index.md / overview.md / 00-meta/ 下的文件 / 不在 index.md 的页面。
    """
    issues: list[Issue] = []
    nav_begin = "<!-- nav:auto -->"
    
    # 跳过的页面集合
    skip_ids = {"index", "overview"}
    skip_prefixes = ("00-meta/",)
    
    for p in pages:
        # 跳过条件
        if p.page_id in skip_ids:
            continue
        if any(p.page_id.startswith(prefix) for prefix in skip_prefixes):
            continue
        if not p.has_fm:
            continue
        
        # 检查是否有 nav 块
        if nav_begin not in p.text:
            issues.append(Issue(
                severity="warn",
                code="missing-nav",
                file=p.rel,
                detail="页面缺少尾部导航块 (<!-- nav:auto -->)，建议运行 nav_inject.py --apply",
            ))
    
    return issues


# ---------------------------------------------------------------------------
# ★v1.1★ Mermaid 语法检查 & 修复
# ---------------------------------------------------------------------------
# 来源事故：Mermaid flowchart/graph 节点标签 `A[Foo()]` 中的圆括号 `()` 被
# 解析器误解为节点形状定义符（`()` = 圆角节点），导致渲染失败。
# 修复方法：给含 `()` 的方括号标签加引号 → `A["Foo()"]`。

_MERMAID_FENCE_RE = re.compile(r"^```mermaid\s*\n(.*?)\n```", re.MULTILINE | re.DOTALL)


def _mermaid_extract_blocks(text: str) -> list[tuple[int, int, str]]:
    """从 markdown 中提取所有 mermaid 代码块: (start, end, source)."""
    return [(m.start(), m.end(), m.group(1)) for m in _MERMAID_FENCE_RE.finditer(text)]


def _mermaid_static_check(src: str) -> list[tuple[int, str]]:
    """对单个 mermaid source 做静态检查。返回 [(line_no, detail), ...]。"""
    issues: list[tuple[int, str]] = []
    lines = src.split("\n")

    # 判断图表类型
    first_line = src.strip().split("\n")[0].strip().lower() if src.strip() else ""
    is_mindmap = first_line.startswith("mindmap")
    is_sequence = first_line.startswith("sequencediagram")
    is_flowchart = first_line.startswith("graph") or first_line.startswith("flowchart")

    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        # 跳过注释、样式、classDef 等
        if not stripped or stripped.startswith("%%") or stripped.startswith("style ") or \
           stripped.startswith("linkStyle ") or stripped.startswith("classDef ") or \
           stripped.startswith("class "):
            continue
        # 跳过 loop/alt/opt 标签
        lower = stripped.lower()
        if lower.startswith("loop ") or lower.startswith("alt ") or \
           lower.startswith("opt ") or lower.startswith("rect ") or \
           lower.startswith("par ") or lower.startswith("critical "):
            continue

        # 检测：边标签中含未引用的圆括号 -->|Foo()|
        if is_flowchart:
            for m in re.finditer(r"\|([^|\"]*\([^|]*)\|", line):
                label = m.group(1)
                if not label.startswith('"') and not label.startswith("'"):
                    issues.append((i, f'Unquoted () in edge label: |{label}|'))

        # 检测：flowchart 中使用 `: label` 语法（仅 classDiagram 合法）
        if is_flowchart:
            if re.search(r"\w+\s*--[->|.]+\s*\w+\s+:\s+\w+", stripped):
                issues.append((i, f'Colon label in flowchart: use -->|label| instead'))

        # 检测：错误的边标签 --> X|Yes| Y（中间多了一个节点名）
        if is_flowchart:
            bad_edge = re.search(r"--[->]+\s+\w+\|[^|]+\|\s+\w+", stripped)
            if bad_edge:
                issues.append((i, f'Malformed edge label: {bad_edge.group(0)}'))

        # 检测：方括号标签内含未引用的圆括号 word[...(...)]
        for m in re.finditer(r"\b\w+\[([^\]\"]*\([^\]]*)\]", line):
            label = m.group(1)
            if not label.startswith('"') and not label.startswith("'"):
                issues.append((i, f'Unquoted () in [...] label: {m.group(0)}'))

        # 检测：圆括号节点内嵌套圆括号（跳过 mindmap/sequence）
        if not is_mindmap and not is_sequence:
            for m in re.finditer(r"\b(\w+)\(([^\)\"]*\([^\)]*\)[^\)\"]*)\)", line):
                node_id = m.group(1)
                _skip = {"subgraph", "end", "click", "class", "style", "linkStyle",
                         "classDef", "direction", "participant", "actor", "note",
                         "root", "loop", "alt", "opt", "rect", "par", "critical",
                         "break", "while", "activate", "deactivate"}
                if node_id.lower() in _skip:
                    continue
                # 排除已在引号标签内的匹配
                prefix = line[:m.start()]
                if re.search(r'\w+\["[^"]*$', prefix):
                    continue
                issues.append((i, f'Nested () in (...) node: {m.group(0)}'))

    return issues


def check_mermaid_syntax(pages: list[WikiPage]) -> list[Issue]:
    """★v1.1★ 检测 Mermaid 代码块中的常见语法错误（括号未引用等）。

    级别: warn（不阻塞 pre-commit，但应修复）。
    """
    issues: list[Issue] = []
    for p in pages:
        blocks = _mermaid_extract_blocks(p.text)
        for start, _end, src in blocks:
            block_line = p.text[:start].count("\n") + 2  # mermaid 块起始行号
            static_issues = _mermaid_static_check(src)
            for line_in_block, detail in static_issues:
                issues.append(Issue(
                    code="mermaid-syntax",
                    severity="warn",
                    file=p.rel,
                    line=block_line + line_in_block,
                    detail=detail,
                ))
    return issues


def _mermaid_fix_block(src: str) -> str:
    """修复单个 mermaid 代码块的已知语法问题。"""
    first_line = src.strip().split("\n")[0].strip().lower() if src.strip() else ""
    is_flowchart = first_line.startswith("graph") or first_line.startswith("flowchart")

    lines = src.split("\n")
    out: list[str] = []
    for line in lines:
        stripped = line.strip()
        # 跳过注释、样式行
        if stripped.startswith("%%") or stripped.startswith("style ") or \
           stripped.startswith("linkStyle ") or stripped.startswith("classDef "):
            out.append(line)
            continue

        fixed = line

        # 修复：flowchart 中的 `: label` 语法 → -->|label|
        if is_flowchart:
            fixed = re.sub(
                r"(\b\w+)\s*(--[->]+)\s*(\w+)\s+:\s+(.+?)$",
                lambda m: f'{m.group(1)} {m.group(2)}|{m.group(4).strip()}| {m.group(3)}',
                fixed,
            )

        # 修复：边标签中的括号 |Foo()| → |"Foo()"|
        if is_flowchart:
            fixed = re.sub(
                r"\|([^|\"]*\([^|]*)\|",
                lambda m: m.group(0) if m.group(1).startswith('"') or m.group(1).startswith("'")
                else f'|"{m.group(1)}"|',
                fixed,
            )

        # 修复：方括号标签内含圆括号 → 加引号
        fixed = re.sub(
            r"(\b\w+)\[([^\]\"]*\([^\]]*)\]",
            lambda m: m.group(0) if m.group(2).startswith('"') or m.group(2).startswith("'")
            else f'{m.group(1)}["{m.group(2).replace(chr(34), "#quot;")}"]',
            fixed,
        )
        out.append(fixed)
    return "\n".join(out)


def fix_mermaid_syntax(pages: list[WikiPage]) -> list[str]:
    """★v1.1★ 自动修复 Mermaid 语法问题。返回修改过的文件 rel 路径列表。"""
    changed: list[str] = []
    for p in pages:
        blocks = _mermaid_extract_blocks(p.text)
        if not blocks:
            continue
        new_text = p.text
        file_modified = False
        for _start, _end, src in blocks:
            static_issues = _mermaid_static_check(src)
            if not static_issues:
                continue
            fixed_src = _mermaid_fix_block(src)
            if fixed_src != src:
                old_block = f"```mermaid\n{src}\n```"
                new_block = f"```mermaid\n{fixed_src}\n```"
                new_text = new_text.replace(old_block, new_block, 1)
                file_modified = True
        if file_modified:
            p.path.write_text(new_text, encoding="utf-8")
            changed.append(p.rel)
    return changed


# ---------------------------------------------------------------------------
# 自动修复（仅安全项）
# ---------------------------------------------------------------------------

def autofix(pages: list[WikiPage], docs_root: Path) -> list[str]:
    """补 last_synced（缺失时设为今天）+ status: draft（缺失时）。
    返回修改过的文件 rel 路径列表。
    """
    today = date.today().isoformat()
    changed: list[str] = []
    for p in pages:
        if p.is_meta_file or not p.has_fm:
            continue
        new_text = p.text
        modified = False
        if "last_synced" not in p.fm:
            new_text = _insert_fm_field(new_text, "last_synced", today)
            modified = True
        if "status" not in p.fm:
            new_text = _insert_fm_field(new_text, "status", "draft")
            modified = True
        if modified:
            p.path.write_text(new_text, encoding="utf-8")
            changed.append(p.rel)
    return changed


def _insert_fm_field(text: str, key: str, value: str) -> str:
    """在 frontmatter 闭合 --- 之前插入一行 'key: value'。"""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return text
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            lines.insert(i, f"{key}: {value}")
            return "\n".join(lines) + ("\n" if text.endswith("\n") else "")
    return text


# ---------------------------------------------------------------------------
# 报告输出
# ---------------------------------------------------------------------------

def render_report(issues: list[Issue], pages: list[WikiPage], src_files_n: int, *, json_out: bool) -> str:
    err = [i for i in issues if i.severity == "error"]
    warn = [i for i in issues if i.severity == "warn"]
    info = [i for i in issues if i.severity == "info"]

    if json_out:
        return json.dumps({
            "summary": {
                "pages": len(pages),
                "source_files": src_files_n,
                "errors": len(err),
                "warnings": len(warn),
                "info": len(info),
                "exit_code": _exit_code(err, warn),
            },
            "issues": [asdict(i) for i in issues],
        }, ensure_ascii=False, indent=2)

    out: list[str] = []
    out.append("=" * 60)
    out.append(f"WIKI LINT REPORT  —  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    out.append(f"  pages={len(pages)}  source_files={src_files_n}")
    out.append("=" * 60)

    if err:
        out.append("")
        out.append(f"ERRORS ({len(err)}) — must fix:")
        for i in err:
            out.append(i.fmt())
    if warn:
        out.append("")
        out.append(f"WARNINGS ({len(warn)}) — should fix:")
        for i in warn:
            out.append(i.fmt())
    if info:
        out.append("")
        out.append(f"INFO ({len(info)}):")
        for i in info:
            out.append(i.fmt())

    out.append("")
    out.append("-" * 60)
    out.append(f"summary: {len(err)} errors, {len(warn)} warnings, {len(info)} info")
    out.append(f"exit code: {_exit_code(err, warn)}")
    if not err and not warn:
        out.append("clean ✓")
    return "\n".join(out)


def _exit_code(err: list[Issue], warn: list[Issue]) -> int:
    if err:
        return 2
    if warn:
        return 1
    return 0


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------

def run(args) -> int:
    project_root = Path(args.project_root).resolve()
    docs_root = project_root / DOCS_DIR

    # ★v0.2★ --update-cache / --show-cache 是独立子命令，不跑常规检查
    if args.show_cache:
        print(show_anchor_cache(project_root))
        return 0
    if args.update_cache:
        pages = collect_pages(docs_root)
        n_add, n_upd, n_del = update_anchor_cache(pages, project_root)
        print(f"[update-cache] {n_add} 新增, {n_upd} 更新 sha256, {n_del} 删除")
        print(f"[update-cache] cache 文件: {ANCHOR_CACHE_REL}")
        print(f"[update-cache] 记得 git add 这个 cache 文件")
        return 0

    pages = collect_pages(docs_root)
    src_files_n = 0

    issues: list[Issue] = []
    if args.scope in ("wiki", "all"):
        issues.extend(check_broken_links(pages, docs_root))
        issues.extend(check_frontmatter(pages))
        issues.extend(check_anchors(pages, project_root))
        issues.extend(check_index_consistency(pages, docs_root))
        # ★v0.7★ log-fragment-required 是 ERROR 级，必须在 --check 模式也跑（pre-commit 拦截）
        issues.extend(check_log_fragment_v07(pages, docs_root))
        # ★v1.0★ 教程 frontmatter 专项检查（ERROR 级，pre-commit 拦截）
        issues.extend(check_tutorial_frontmatter(pages))
        # ★v1.2★ 教程内部引用闭合性检查（ERROR 级，pre-commit 拦截）
        issues.extend(check_tutorial_internal_refs(pages))
        if not args.check:  # 仅 full 模式
            issues.extend(check_ascii_art(pages))
            issues.extend(check_bidir_links(pages))
            issues.extend(check_status(pages))
            issues.extend(check_orphans(pages))
            # ★v0.2★ full 模式下跑 sha256 + version drift
            issues.extend(check_anchor_sha256(pages, project_root))
            issues.extend(check_version_drift(pages, docs_root))
            # ★v0.4★ full 模式下跑 last_synced 过期 + 同名实体检测
            issues.extend(check_last_synced_stale(pages))
            issues.extend(check_duplicate_entity(pages))
            # ★v0.5★ full 模式下跑 prerequisites 字段一致性
            issues.extend(check_prerequisites(pages))
            # ★v0.6★ full 模式下跑 log.md R 编号顺序 + related 字段一致性
            issues.extend(check_log_order(docs_root))
            issues.extend(check_related_links(pages))
        
        # ★v0.8★ nav 块检查（--check 模式也跑，因为 nav 是基本规范）
        issues.extend(check_nav_block(pages))
        # ★v1.1★ Mermaid 语法检查（full 模式，warn 级）
        if not args.check:
            issues.extend(check_mermaid_syntax(pages))

    if args.scope in ("source", "all"):
        src_issues = check_variant_includes(project_root)
        issues.extend(src_issues)
        # ★v0.3★ menu_config 同 action 同 label 检测
        # 这是项目配置层的检测，归在 source scope；error 级（menu-config-invalid）
        # 即使 --check 模式也跑
        issues.extend(check_menu_action_label(project_root))
        # ★v0.4★ .bat 文件 chcp 之前 ASCII-only 检查
        # 项目配置/入口层的检测，归在 source scope；只在 full 模式跑（warn 级别）
        if not args.check:
            issues.extend(check_bat_chcp_ascii(project_root))
        # 估算扫了多少源文件（可选）
        src_root = project_root / "Source" / "ue_ai_demo"
        if src_root.is_dir():
            src_files_n = sum(1 for _ in src_root.rglob("*.cpp")) + sum(1 for _ in src_root.rglob("*.h"))

    if args.fix:
        # ★v1.1★ Mermaid 语法修复（在教程 frontmatter 之前，避免冲突）
        mermaid_changed = fix_mermaid_syntax(pages)
        if mermaid_changed:
            print(f"[autofix] Mermaid 语法修复了 {len(mermaid_changed)} 个文件",
                  file=sys.stderr)

        # ★v1.0★ 教程 frontmatter 修复（在 nav_inject 之前，因为可能新增/修改 frontmatter）
        tutorial_changed = fix_tutorial_frontmatter(pages, docs_root)
        if tutorial_changed:
            print(f"[autofix] 教程 frontmatter 修复了 {len(tutorial_changed)} 个文件",
                  file=sys.stderr)

        # ★v0.9★ 自动运行 nav_inject.py --apply 修复 missing-nav
        nav_inject_path = Path(__file__).parent / "nav_inject.py"
        if nav_inject_path.is_file():
            print("[autofix] 正在运行 nav_inject.py --apply 批量添加 nav 导航块...", file=sys.stderr)
            try:
                result = subprocess.run(
                    [sys.executable, str(nav_inject_path), "--apply"],
                    cwd=str(args.project_root),  # 从项目根目录运行
                    capture_output=True,
                    text=True
                )
                if result.returncode == 0:
                    print(f"[autofix] nav_inject.py 完成", file=sys.stderr)
                else:
                    print(f"[autofix] nav_inject.py 警告: {result.stderr[:200]}", file=sys.stderr)
            except Exception as e:
                print(f"[autofix] nav_inject.py 运行失败: {e}", file=sys.stderr)
        
        changed = autofix(pages, docs_root)
        if changed:
            print(f"[autofix] 修改了 {len(changed)} 个文件: {changed[:5]}{'...' if len(changed)>5 else ''}",
                  file=sys.stderr)
            # 修复后重扫一次以更新报告
            pages = collect_pages(docs_root)
            issues = []
            issues.extend(check_broken_links(pages, docs_root))
            issues.extend(check_frontmatter(pages))
            issues.extend(check_tutorial_frontmatter(pages))
            issues.extend(check_tutorial_internal_refs(pages))
            issues.extend(check_mermaid_syntax(pages))

    print(render_report(issues, pages, src_files_n, json_out=args.json))

    err = [i for i in issues if i.severity == "error"]
    warn = [i for i in issues if i.severity == "warn"]
    if args.check:
        return 2 if err else 0
    return _exit_code(err, warn)


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="项目知识库 + Variant 隔离 lint v1.1")
    ap.add_argument("--project-root", default=os.environ.get("PROJECT_ROOT", str(_default_project_root())),
                    help="项目根目录（默认：脚本上上上上层）")
    ap.add_argument("--scope", choices=["wiki", "source", "all"], default="all",
                    help="扫描范围（默认 all）")
    ap.add_argument("--check", action="store_true",
                    help="仅 ERROR 级别（pre-commit 模式，速度快）")
    ap.add_argument("--json", action="store_true", help="JSON 格式输出")
    ap.add_argument("--fix", action="store_true",
                    help="自动修复安全项（last_synced / status / 教程 frontmatter / Mermaid 语法）")
    ap.add_argument("--update-cache", action="store_true",
                    help="★v0.2★ 重算所有 anchor sha256 → 写到 cache，然后退出")
    ap.add_argument("--show-cache", action="store_true",
                    help="★v0.2★ 打印 anchor cache 概况，然后退出")
    return ap.parse_args()


def _default_project_root() -> Path:
    """脚本默认在 .codebuddy/skills/project-wiki/scripts/ 下，上 4 层是项目根。"""
    return Path(__file__).resolve().parents[4]


def main() -> None:
    args = parse_args()
    try:
        rc = run(args)
    except Exception as e:
        print(f"[lint-error] {type(e).__name__}: {e}", file=sys.stderr)
        rc = 3
    sys.exit(rc)


if __name__ == "__main__":
    main()
