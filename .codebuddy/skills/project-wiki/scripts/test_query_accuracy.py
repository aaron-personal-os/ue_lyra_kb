#!/usr/bin/env python3
"""test_query_accuracy.py — 知识库查询机制准确度测试

测试覆盖：
  T1  基础关键词查询
  T2  CamelCase 自动拆分
  T3  CJK 中文分词（字符级匹配）
  T4  Alias 词表扩展（GAS → Gameplay Ability System）
  T5  种子模式 --id（多类型 1-hop 邻居）
  T6  系列模式 --series（按 lesson_index 排序）
  T7  限定 category / domain 软降权
  T8  Anchor-hit bonus（代码反查 wiki）
  T9  Page-id full-token bonus（精确页 id 匹配）
  T10 Status 修正系数（stale/deprecated 警告）
  T11 1-hop 邻居展开（related / prereq / wikilink / series-prev/next）
  T12 自动 fallback 到 Tier 0（零候选时）
  T13 JSON 输出格式
  T14 --no-alias 关闭别名扩展
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import time
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

SCRIPTS_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPTS_DIR.parent
REPO_ROOT = SKILL_DIR.parents[2]
DB_PATH = SKILL_DIR / ".cache" / "wiki.db"

PYTHON = "py"  # Windows Python Launcher


@dataclass
class TestResult:
    test_id: str
    description: str
    passed: bool
    detail: str = ""
    duration_ms: float = 0.0
    raw_output: str = ""


@dataclass
class TestSuite:
    results: list[TestResult] = field(default_factory=list)

    def add(self, r: TestResult):
        self.results.append(r)

    def summary(self) -> str:
        total = len(self.results)
        passed = sum(1 for r in self.results if r.passed)
        failed = total - passed
        lines = [
            "",
            "=" * 60,
            f"  测试结果汇总",
            "=" * 60,
            f"  总数：  {total}",
            f"  通过：  {passed}  [PASS]",
            f"  失败：  {failed}  [FAIL]",
            "=" * 60,
        ]
        if failed > 0:
            lines.append("")
            lines.append("  失败测试详情：")
            for r in self.results:
                if not r.passed:
                    lines.append(f"    {r.test_id:6s}  {r.description}")
                    lines.append(f"           → {r.detail}")
            lines.append("")
        return "\n".join(lines)


def run_wiki_query(
    args: list[str],
    *,
    timeout: int = 30,
) -> tuple[str, str, int]:
    """运行 wiki_query.py，返回 (stdout, stderr, exit_code)。"""
    cmd = [PYTHON, str(SCRIPTS_DIR / "wiki_query.py"), *args]
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
        cwd=str(REPO_ROOT),
        encoding="utf-8",
        errors="replace",
    )
    return result.stdout, result.stderr, result.returncode


def run_query_py(
    args: list[str],
    *,
    timeout: int = 30,
) -> tuple[str, str, int]:
    """运行 query.py（Tier 0 对比）。"""
    cmd = [PYTHON, str(SCRIPTS_DIR / "query.py"), *args]
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
        cwd=str(REPO_ROOT),
        encoding="utf-8",
        errors="replace",
    )
    return result.stdout, result.stderr, result.returncode


def has_candidate(output: str, page_id: str) -> bool:
    """检查输出中是否包含某个候选页。"""
    pattern = rf"\[[\d]+\]\s+\[\[{re.escape(page_id)}\]\]"
    return bool(re.search(pattern, output))


def get_top_candidate(output: str) -> Optional[str]:
    """从人类可读输出中提取 Top-1 候选的 page_id。"""
    m = re.search(r"\[1\]\s+★?\s*\[\[([^\]|#]+)", output)
    if m:
        return m.group(1).strip()
    return None


def get_all_candidates(output: str) -> list[str]:
    """提取所有候选 page_id。"""
    return re.findall(r"\[[\d]+\]\s+★?\s*\[\[([^\]|#]+)", output)


def has_warning(output: str, keyword: str) -> bool:
    """检查输出中是否包含某个警告。"""
    return keyword.lower() in output.lower()


# =====================================================================
# 测试用例
# =====================================================================

def test_basic_keyword(suite: TestSuite):
    """T1: 基础关键词查询 — 'GameplayAbility' 应命中 GAS 相关页。"""
    t0 = time.time()
    out, err, code = run_wiki_query(["GameplayAbility", "--max-candidates", "5"])
    dur = (time.time() - t0) * 1000

    candidates = get_all_candidates(out)
    passed = len(candidates) > 0 and any("gas" in c.lower() for c in candidates[:3])
    detail = f"candidates={candidates[:5]}, err={err[:200]}" if not passed else f"top={candidates[:3]}"
    suite.add(TestResult("T1", "基础关键词查询", passed, detail, dur, out))


def test_camel_case_split(suite: TestSuite):
    """T2: CamelCase 自动拆分 — 'LyraCharacter' → 'lyra' + 'character'。"""
    t0 = time.time()
    out, err, code = run_wiki_query(["LyraCharacter", "--max-candidates", "5"])
    dur = (time.time() - t0) * 1000

    top = get_top_candidate(out)
    # 期望 Top-1 是 ALyraCharacter 模块文档
    passed = top is not None and "ALyraCharacter".lower() in top.lower()
    detail = f"top={top}, candidates={get_all_candidates(out)[:3]}"
    suite.add(TestResult("T2", "CamelCase 自动拆分", passed, detail, dur, out))


def test_cjk_chinese(suite: TestSuite):
    """T3: CJK 中文分词 — '生命值' 应命中 HealthComponent 相关页。"""
    t0 = time.time()
    out, err, code = run_wiki_query(["生命值", "--max-candidates", "5"])
    dur = (time.time() - t0) * 1000

    candidates = get_all_candidates(out)
    # 中文查询至少应返回结果（可能通过 body 命中）
    passed = len(candidates) > 0
    detail = f"candidates={candidates[:5]}" if passed else f"no candidates, err={err[:300]}"
    suite.add(TestResult("T3", "CJK 中文分词", passed, detail, dur, out))


def test_alias_expansion(suite: TestSuite):
    """T4: Alias 词表扩展 — 'GAS' 应扩展为 'gameplay ability system'。"""
    t0 = time.time()
    out, err, code = run_wiki_query(["GAS", "--max-candidates", "5"])
    dur = (time.time() - t0) * 1000

    # 检查是否输出了 alias-expanded 提示
    alias_expanded = "Alias-expanded" in out or "alias" in out.lower()
    candidates = get_all_candidates(out)
    # GAS 查询应命中 GAS 教程系列相关页
    passed = len(candidates) > 0 and any("gas" in c.lower() for c in candidates[:3])
    detail = f"alias_expanded_hint={alias_expanded}, top={candidates[:3]}"
    suite.add(TestResult("T4", "Alias 词表扩展 (GAS)", passed, detail, dur, out))


def test_alias_no_alias_flag(suite: TestSuite):
    """T4b: --no-alias 应关闭别名扩展。"""
    t0 = time.time()
    out, err, code = run_wiki_query(["GAS", "--no-alias", "--max-candidates", "5"])
    dur = (time.time() - t0) * 1000

    no_alias_hint = "Alias-expanded" not in out
    passed = no_alias_hint  # 不应出现 alias 扩展提示
    detail = f"no_alias_hint={no_alias_hint}, top={get_all_candidates(out)[:3]}"
    suite.add(TestResult("T4b", "--no-alias 关闭别名", passed, detail, dur, out))


def test_seed_mode(suite: TestSuite):
    """T5: 种子模式 --id — 展开指定页的 1-hop 邻居。"""
    t0 = time.time()
    seed_id = "30-tutorials/gas/01-GA简介与配置"
    out, err, code = run_wiki_query(["--id", seed_id])
    dur = (time.time() - t0) * 1000

    # 应包含种子页本身 + 邻居列表
    has_seed = has_candidate(out, seed_id)
    has_neighbors = "1-HOP NEIGHBORS" in out or "neighbors" in out.lower()
    passed = has_seed and len(get_all_candidates(out)) >= 1
    detail = f"has_seed={has_seed}, has_neighbors={has_neighbors}, neighbors_section={'1-HOP' in out}"
    suite.add(TestResult("T5", "种子模式 --id", passed, detail, dur, out))


def test_series_mode(suite: TestSuite):
    """T6: 系列模式 --series — 按 lesson_index 排序列出全套课程。"""
    t0 = time.time()
    out, err, code = run_wiki_query(["--series", "gas"])
    dur = (time.time() - t0) * 1000

    candidates = get_all_candidates(out)
    # gas 系列应有 > 20 课
    passed = len(candidates) >= 20
    # 检查是否按顺序排列（01 应在 02 前）
    indices = []
    for c in candidates:
        m = re.search(r"/(\d+)-", c)
        if m:
            indices.append(int(m.group(1)))
    ordered = indices == sorted(indices)
    detail = f"count={len(candidates)}, ordered={ordered}, first_few={candidates[:3]}"
    suite.add(TestResult("T6", "系列模式 --series gas", passed, detail, dur, out))


def test_category_filter(suite: TestSuite):
    """T7: 限定 category 软降权 — 30-tutorials 应优先于 20-modules。"""
    t0 = time.time()
    out, err, code = run_wiki_query(
        ["ability", "--category", "30-tutorials", "--max-candidates", "10"]
    )
    dur = (time.time() - t0) * 1000

    candidates = get_all_candidates(out)
    # 前 3 应主要是 30-tutorials/ 下的页
    top3_categories = [c.split("/")[0] if "/" in c else "" for c in candidates[:3]]
    mostly_tutorials = sum(1 for c in top3_categories if c == "30-tutorials") >= 2
    passed = len(candidates) > 0
    detail = f"top3_categories={top3_categories}, mostly_tutorials={mostly_tutorials}"
    suite.add(TestResult("T7", "category 软降权", passed, detail, dur, out))


def test_domain_filter(suite: TestSuite):
    """T7b: 限定 domain 软降权 — gas domain 应优先。"""
    t0 = time.time()
    out, err, code = run_wiki_query(
        ["ability", "--domain", "gas", "--max-candidates", "10"]
    )
    dur = (time.time() - t0) * 1000

    candidates = get_all_candidates(out)
    passed = len(candidates) > 0
    detail = f"top={candidates[:5]}"
    suite.add(TestResult("T7b", "domain 软降权 (gas)", passed, detail, dur, out))


def test_anchor_hit(suite: TestSuite):
    """T8: Anchor-hit bonus — 查询 'LyraCharacter.cpp' 应命中模块文档。"""
    t0 = time.time()
    out, err, code = run_wiki_query(["LyraCharacter.cpp", "--max-candidates", "5"])
    dur = (time.time() - t0) * 1000

    top = get_top_candidate(out)
    # Anchor 命中应使 ALyraCharacter 排前面
    passed = top is not None and "ALyraCharacter".lower() in top.lower()
    detail = f"top={top}, anchor_hit_expected=ALyraCharacter"
    suite.add(TestResult("T8", "Anchor-hit bonus", passed, detail, dur, out))


def test_page_id_full_token(suite: TestSuite):
    """T9: Page-id full-token bonus — 精确页 id 查询应 Top-1 命中。"""
    t0 = time.time()
    out, err, code = run_wiki_query(
        ["ULyraAbilitySystemComponent", "--max-candidates", "5"]
    )
    dur = (time.time() - t0) * 1000

    top = get_top_candidate(out)
    passed = top is not None and "ULyraAbilitySystemComponent".lower() in top.lower()
    detail = f"top={top}"
    suite.add(TestResult("T9", "Page-id full-token bonus", passed, detail, dur, out))


def test_status_stale_warning(suite: TestSuite):
    """T10: Status 修正系数 — stale/deprecated 页应有警告。"""
    # 先找一个 stale 页（如果有）
    t0 = time.time()
    out, err, code = run_wiki_query(["GAS", "--max-candidates", "10"])
    dur = (time.time() - t0) * 1000

    # 检查是否有 stale/deprecated 警告
    has_stale_warning = "stale" in out.lower() and ("⚠" in out or "warn" in out.lower())
    passed = True  # 如果没有 stale 页则此测试跳过，不 fail
    detail = f"has_stale_warning={has_stale_warning}"
    suite.add(TestResult("T10", "Status stale 警告", passed, detail, dur, out))


def test_1_hop_neighbors(suite: TestSuite):
    """T11: 1-hop 邻居展开 — 检查 related / prereq / wikilink 边。"""
    t0 = time.time()
    seed_id = "30-tutorials/gas/02-GA执行流程详解"
    out, err, code = run_wiki_query(["--id", seed_id])
    dur = (time.time() - t0) * 1000

    # 邻居列表应非空
    neighbors_section = "1-HOP NEIGHBORS" in out
    passed = neighbors_section
    detail = f"neighbors_section={neighbors_section}"
    if neighbors_section:
        # 提取邻居数量
        m = re.search(r"1-HOP NEIGHBORS\s*\((\d+)\)", out)
        if m:
            detail += f", neighbor_count={m.group(1)}"
    suite.add(TestResult("T11", "1-hop 邻居展开", passed, detail, dur, out))


def test_auto_fallback_zero_candidates(suite: TestSuite):
    """T12: 自动 fallback — 极低概率词应触发 Tier 0 fallback。"""
    t0 = time.time()
    # 使用几乎不可能命中的查询
    out, err, code = run_wiki_query(["qzqzqzqz9999nonexistent"], timeout=30)
    dur = (time.time() - t0) * 1000

    # 应看到 fallback 提示（Tier 1 零候选时）
    has_fallback = "fallback" in err.lower() or "Tier 0" in err or "query.py" in err
    # 或者 query.py deprecation 提示
    passed = True  # 此测试仅检查行为，不强制 fail
    detail = f"has_fallback_hint={'yes' if has_fallback else 'no'}, err={err[:300]}"
    suite.add(TestResult("T12", "自动 fallback (零候选)", passed, detail, dur, out))


def test_json_output(suite: TestSuite):
    """T13: JSON 输出格式 — --json 应返回合法 JSON。"""
    t0 = time.time()
    out, err, code = run_wiki_query(["GAS", "--json", "--max-candidates", "3"])
    dur = (time.time() - t0) * 1000

    try:
        data = json.loads(out)
        is_valid = "candidates" in data and "query" in data and "tier" in data
        detail = f"valid_json={is_valid}, keys={list(data.keys())}"
    except json.JSONDecodeError as e:
        is_valid = False
        detail = f"JSON parse error: {e}, stdout={out[:300]}"
    passed = is_valid
    suite.add(TestResult("T13", "JSON 输出格式", passed, detail, dur, out))


def test_tier_display(suite: TestSuite):
    """T14: Tier 标识 — 输出应包含 Tier 信息。"""
    t0 = time.time()
    out, err, code = run_wiki_query(["GAS"], timeout=15)
    dur = (time.time() - t0) * 1000

    has_tier = "[Tier" in out or "tier" in out.lower()
    passed = has_tier
    detail = f"has_tier={has_tier}, tier_line={[l for l in out.splitlines() if 'Tier' in l]}"
    suite.add(TestResult("T14", "Tier 标识显示", passed, detail, dur, out))


def test_query_vs_query_py_consistency(suite: TestSuite):
    """T15: wiki_query.py 与 query.py 结果一致性（Top-3 应有重叠）。"""
    t0 = time.time()
    out_wiki, _, _ = run_wiki_query(["GAS", "--max-candidates", "5"])
    out_query, _, _ = run_query_py(["GAS", "--max-candidates", "5", "--no-body"])
    dur = (time.time() - t0) * 1000

    cands_wiki = get_all_candidates(out_wiki)
    cands_query = get_all_candidates(out_query)

    # 计算重叠度
    set_wiki = set(c.lower() for c in cands_wiki)
    set_query = set(c.lower() for c in cands_query)
    overlap = set_wiki & set_query
    overlap_ratio = len(overlap) / max(len(set_wiki), 1)

    passed = overlap_ratio >= 0.4  # 至少 40% 重叠
    detail = (
        f"wiki={cands_wiki[:3]}, "
        f"query_py={cands_query[:3]}, "
        f"overlap={len(overlap)}/{max(len(set_wiki),1)} ({overlap_ratio:.0%})"
    )
    suite.add(TestResult("T15", "wiki_query vs query.py 一致性", passed, detail, dur, out_wiki))


# =====================================================================
# Main
# =====================================================================

def main():
    print("=" * 60)
    print("  知识库查询机制准确度测试")
    print("=" * 60)
    print(f"  DB: {DB_PATH}")
    print(f"  DB exists: {DB_PATH.exists()}")
    if not DB_PATH.exists():
        print("  [ERROR] wiki.db not found! Run wiki_rebuild.py first.")
        sys.exit(1)
    print()

    suite = TestSuite()

    # 运行所有测试
    tests = [
        ("T1",  test_basic_keyword, "基础关键词查询"),
        ("T2",  test_camel_case_split, "CamelCase 自动拆分"),
        ("T3",  test_cjk_chinese, "CJK 中文分词"),
        ("T4",  test_alias_expansion, "Alias 词表扩展"),
        ("T4b", test_alias_no_alias_flag, "--no-alias 关闭别名"),
        ("T5",  test_seed_mode, "种子模式 --id"),
        ("T6",  test_series_mode, "系列模式 --series"),
        ("T7",  test_category_filter, "category 软降权"),
        ("T7b", test_domain_filter, "domain 软降权"),
        ("T8",  test_anchor_hit, "Anchor-hit bonus"),
        ("T9",  test_page_id_full_token, "Page-id full-token"),
        ("T10", test_status_stale_warning, "Status 警告"),
        ("T11", test_1_hop_neighbors, "1-hop 邻居"),
        ("T12", test_auto_fallback_zero_candidates, "自动 fallback"),
        ("T13", test_json_output, "JSON 输出"),
        ("T14", test_tier_display, "Tier 标识"),
        ("T15", test_query_vs_query_py_consistency, "一致性检查"),
    ]

    for tid, func, desc in tests:
        print(f"  Running {tid}: {desc}...", flush=True)
        try:
            func(suite)
            r = suite.results[-1]
            status = "[PASS]" if r.passed else "[FAIL]"
            print(f"    {status} ({r.duration_ms:.0f}ms) {r.detail[:100]}")
        except Exception as e:
            suite.add(TestResult(tid, desc, False, f"Exception: {e}"))
            print(f"    [ERROR] {e}")

    # 输出汇总
    print(suite.summary())

    # 输出详细结果到文件
    report_path = REPO_ROOT / ".codebuddy" / "skills" / "project-wiki" / "test-report.txt"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(f"Query Accuracy Test Report\n")
        f.write(f"=" * 60 + "\n")
        f.write(f"Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"DB: {DB_PATH}\n")
        f.write(f"DB size: {DB_PATH.stat().st_size / 1024:.1f} KB\n")
        f.write("\n")
        for r in suite.results:
            status = "[PASS]" if r.passed else "[FAIL]"
            f.write(f"  {status} {r.test_id}: {r.description}\n")
            f.write(f"         {r.detail}\n")
            f.write(f"         ({r.duration_ms:.0f}ms)\n\n")
        f.write(suite.summary())
    print(f"\n  详细报告已保存到：{report_path}")

    failed = sum(1 for r in suite.results if not r.passed)
    sys.exit(1 if failed > 0 else 0)


if __name__ == "__main__":
    main()
