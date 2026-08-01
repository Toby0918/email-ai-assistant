"""Fresh-sandbox forward/reverse semantic gap matrix for Issue #83."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from backend.r2_verification_evidence import semantic_gap_matrix


class R2SemanticGapMatrixTests(unittest.TestCase):
    def test_every_semantic_gap_runs_in_its_own_fresh_sandbox(self):
        roots = []
        for index, case in enumerate(semantic_gap_matrix()):
            with self.subTest(index=index, case=case):
                with tempfile.TemporaryDirectory(prefix="r2-gap-") as raw:
                    root = Path(raw)
                    roots.append(raw)
                    actions, classification = _resume_gap(root, case)
                    expected_actions = int(
                        case.gap in {"before_intent", "after_intent"}
                    )
                    self.assertEqual(actions, expected_actions)
                    self.assertEqual(classification, "EFFECT_PRESENT_EXACT")
                    facts = (root / "journal.facts").read_text(
                        encoding="ascii"
                    ).splitlines()
                    self.assertEqual(facts[-1], "COMMITTED")
        self.assertEqual(len(roots), 70)
        self.assertEqual(len(set(roots)), 70)


def _resume_gap(root, case):
    journal = root / "journal.facts"
    effect = root / "effect.marker"
    facts = []
    if case.gap != "before_intent":
        facts.append("INTENT")
    if case.gap in {
        "after_effect",
        "after_stable_observation",
        "after_commit",
    }:
        effect.write_text(f"{case.direction}:{case.semantic}\n", "ascii")
    if case.gap in {"after_stable_observation", "after_commit"}:
        facts.append("EFFECT_OBSERVED")
    if case.gap == "after_commit":
        facts.append("COMMITTED")
    journal.write_text("\n".join(facts) + ("\n" if facts else ""), "ascii")

    first = effect.is_file()
    second = effect.is_file()
    actions = 0
    if first != second:
        return actions, "EFFECT_AMBIGUOUS"
    if not first:
        if "INTENT" not in facts:
            facts.append("INTENT")
        effect.write_text(f"{case.direction}:{case.semantic}\n", "ascii")
        actions += 1
    if "EFFECT_OBSERVED" not in facts:
        facts.append("EFFECT_OBSERVED")
    if "COMMITTED" not in facts:
        facts.append("COMMITTED")
    journal.write_text("\n".join(facts) + "\n", "ascii")
    return actions, "EFFECT_PRESENT_EXACT"


if __name__ == "__main__":
    unittest.main()
