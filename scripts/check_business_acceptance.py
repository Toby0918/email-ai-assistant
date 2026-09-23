"""Run 22 synthetic current-email checkpoints, including explicit known gaps.

Exit 1 means checkpoint gaps; it never means the source regression suite failed.
This is offline and does not open research originals or contact a provider.
"""
from __future__ import annotations

import json
from pathlib import Path
import sys
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.email_agent.analyzer import analyze_current_email
from backend.email_agent.config import build_standalone_verification_config


def _value(result: dict, path: str):
    value = result
    for field in path.split("."):
        value = value[field]
    return value


def run() -> int:
    cases_path = ROOT / "examples/business_acceptance/cases.json"
    cases = json.loads(cases_path.read_text(encoding="utf-8"))
    if len(cases) != 22 or len({case["id"] for case in cases}) != 22:
        raise ValueError("Expected exactly 22 distinct acceptance checkpoints")
    output = ROOT / "Build/business-acceptance"
    output.mkdir(parents=True, exist_ok=True)
    config = build_standalone_verification_config(
        sqlite_path=output / "unused.sqlite3", attachment_temp_dir=output / "attachment-temp",
    )
    rows = []
    for case in cases:
        result = analyze_current_email({"subject": case["subject"], "from": "buyer@example.test",
                                        "body_text": case["body"]}, config=config)
        checks = []
        for check in case["checks"]:
            actual = _value(result, check["field"])
            text = actual if isinstance(actual, str) else json.dumps(actual, ensure_ascii=False)
            if "equals" in check:
                passed = actual == check["equals"]
            elif "not_contains" in check:
                passed = check["not_contains"] not in text
            else:
                passed = check["contains"] in text
            checks.append({**check, "passed": passed, "actual": actual})
        rows.append({**case, "status": "CHECKPOINT_PASS" if all(item["passed"] for item in checks) else "GAP",
                     "checks": checks, "analysis": result, "full_scenario_acceptance": "NOT_ESTABLISHED"})
    passed = sum(row["status"] == "CHECKPOINT_PASS" for row in rows)
    report = {"created_utc": datetime.now(timezone.utc).isoformat(), "synthetic": True,
              "entry_point": "analyze_current_email", "providers": "disabled", "mailbox_access": False,
              "checkpoint_pass": passed, "checkpoint_gaps": len(rows) - passed, "cases": rows}
    (output / "results.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = ["# 22 个业务案例的可重复检查", "", f"本次：{passed} 个文字检查点通过，{22 - passed} 个仍有缺口。",
             "所有输入均为合成资料，远程模型关闭。通过一个文字检查点不代表完整业务案例、附件图片或真实邮箱验收通过。",
             "字符串检查是固定表达的回归门槛；未命中需结合保存的完整输出复核，不是通用语义准确率。", "",
             "| 案例 | 检查内容 | 本次结果 | 完整案例仍需验收的范围 |", "|---|---|---|---|"]
    for row in rows:
        label = "文字检查点通过" if row["status"] == "CHECKPOINT_PASS" else "存在缺口"
        lines.append(f"| {row['id']} | {row['title']} | {label} | {row['remaining']} |")
    (output / "验收结果.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"checkpoint_pass": passed, "checkpoint_gaps": 22 - passed,
                      "report": str(output / "验收结果.md")}, ensure_ascii=True))
    return 0 if passed == len(rows) else 1


if __name__ == "__main__":
    raise SystemExit(run())
