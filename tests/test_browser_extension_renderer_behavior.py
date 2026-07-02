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
          summary: "Payment needs confirmation.",
          category: "payment",
          risk_flags: [{{ type: "payment_risk", level: "high" }}],
          suggested_actions: [
            {{ type: "confirm", description: "Confirm payment status before replying." }},
          ],
          reply_draft: {{ body: "Draft body" }},
        }});

        if (fields.risks.textContent.includes("[object Object]")) {{
          throw new Error(`risk text is not readable: ${{fields.risks.textContent}}`);
        }}
        if (!fields.risks.textContent.includes("payment_risk")) {{
          throw new Error(`risk type missing: ${{fields.risks.textContent}}`);
        }}
        if (!fields.risks.textContent.includes("high")) {{
          throw new Error(`risk level missing: ${{fields.risks.textContent}}`);
        }}
        if (fields.actions.textContent.includes("[object Object]")) {{
          throw new Error(`action text is not readable: ${{fields.actions.textContent}}`);
        }}
        if (!fields.actions.textContent.includes("Confirm payment status before replying.")) {{
          throw new Error(`action description missing: ${{fields.actions.textContent}}`);
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
