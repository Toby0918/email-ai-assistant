"""Behavior tests for browser extension analysis rendering."""

from __future__ import annotations

import shutil
import subprocess
import textwrap
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RENDERER = ROOT / "frontend" / "browser_extension" / "shared" / "render_analysis.js"


class BrowserExtensionRendererBehaviorTests(unittest.TestCase):
    def test_renders_object_lists_without_default_object_text(self) -> None:
        if shutil.which("node") is None:
            self.skipTest("Node.js is required for browser extension renderer tests")

        script = f"""
        const fs = require("fs");
        const vm = require("vm");
        const renderer = fs.readFileSync({str(RENDERER)!r}, "utf8");
        const context = {{ window: {{}} }};
        vm.runInNewContext(renderer, context);

        const fields = {{
          priority: {{ textContent: "" }},
          summary: {{ textContent: "" }},
          category: {{ textContent: "" }},
          risks: {{ textContent: "" }},
          actions: {{ textContent: "" }},
          draft: {{ value: "" }},
        }};

        context.window.EmailAssistantRender.renderAnalysis(fields, {{
          priority: "high",
          summary: "需要核对付款状态。",
          category: "payment",
          risk_flags: [{{ type: "payment_risk", level: "high", evidence: "邮件提到付款或发票。" }}],
          suggested_actions: [
            {{ type: "confirm", description: "请先核对付款、发票或汇款状态，再回复。" }},
            {{ type: "check_inventory" }},
          ],
          reply_draft: {{ body: "Draft body" }},
        }});

        if (fields.priority.textContent !== "高") {{
          throw new Error(`priority label missing: ${{fields.priority.textContent}}`);
        }}
        if (fields.category.textContent !== "付款/发票") {{
          throw new Error(`category label missing: ${{fields.category.textContent}}`);
        }}
        if (fields.risks.textContent.includes("[object Object]")) {{
          throw new Error(`risk text is not readable: ${{fields.risks.textContent}}`);
        }}
        if (!fields.risks.textContent.includes("付款风险")) {{
          throw new Error(`risk label missing: ${{fields.risks.textContent}}`);
        }}
        if (!fields.risks.textContent.includes("高")) {{
          throw new Error(`risk level missing: ${{fields.risks.textContent}}`);
        }}
        if (fields.actions.textContent.includes("[object Object]")) {{
          throw new Error(`action text is not readable: ${{fields.actions.textContent}}`);
        }}
        if (!fields.actions.textContent.includes("请先核对付款、发票或汇款状态，再回复。")) {{
          throw new Error(`action description missing: ${{fields.actions.textContent}}`);
        }}
        if (!fields.actions.textContent.includes("核查库存")) {{
          throw new Error(`action fallback label missing: ${{fields.actions.textContent}}`);
        }}
        """

        result = subprocess.run(
            ["node", "-e", textwrap.dedent(script)],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
        if result.returncode != 0:
            self.fail(result.stderr or result.stdout)


if __name__ == "__main__":
    unittest.main()
