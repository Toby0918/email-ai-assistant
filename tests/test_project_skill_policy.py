"""Project-level Codex skill policy contracts."""

from __future__ import annotations

import tomllib
import unittest
from pathlib import Path

from scripts.repo_utils import is_text_file, iter_project_files, read_text


ROOT = Path(__file__).resolve().parents[1]
PROJECT_CONFIG = ROOT / ".codex" / "config.toml"
POLICY_MANIFEST = ROOT / ".codex" / "project-skill-policy.toml"
SUPERPOWERS_PLUGIN = "superpowers@openai-curated-remote"
MIGRATION_RECORD = (
    ROOT / "docs" / "operations" / "matt_pocock_skill_migration_task_brief.md"
)
EXPECTED_IMPLICIT_SKILLS = {
    "code-review",
    "codebase-design",
    "design-an-interface",
    "diagnosing-bugs",
    "domain-modeling",
    "git-guardrails-claude-code",
    "grilling",
    "migrate-to-shoehorn",
    "obsidian-vault",
    "prototype",
    "qa",
    "request-refactor-plan",
    "research",
    "resolving-merge-conflicts",
    "scaffold-exercises",
    "setup-pre-commit",
    "tdd",
}
EXPECTED_EXPLICIT_ONLY_SKILLS = {
    "ask-matt",
    "batch-grill-me",
    "claude-handoff",
    "edit-article",
    "grill-me",
    "grill-with-docs",
    "handoff",
    "implement",
    "improve-codebase-architecture",
    "loop-me",
    "setup-matt-pocock-skills",
    "setup-ts-deep-modules",
    "teach",
    "to-questionnaire",
    "to-spec",
    "to-tickets",
    "triage",
    "ubiquitous-language",
    "wayfinder",
    "wizard",
    "writing-beats",
    "writing-fragments",
    "writing-great-skills",
    "writing-shape",
}


def load_toml(path: Path) -> dict[str, object]:
    return tomllib.loads(path.read_text(encoding="utf-8"))


class ProjectSkillPolicyTests(unittest.TestCase):
    def test_matt_skills_are_available_and_superpowers_plugin_is_disabled(self) -> None:
        config = load_toml(PROJECT_CONFIG)
        manifest = load_toml(POLICY_MANIFEST)

        self.assertEqual(
            config.get("plugins"),
            {SUPERPOWERS_PLUGIN: {"enabled": False}},
        )
        self.assertNotIn("skills", config)

        policy = manifest["policy"]
        counts = manifest["matt_pocock"]["counts"]
        superpowers = manifest["superpowers"]

        self.assertEqual(policy["mode"], "matt-pocock-primary")
        self.assertFalse(policy["global_config_modified"])
        self.assertFalse(policy["installed_skill_files_modified"])
        self.assertEqual(counts["installed"], 41)
        self.assertEqual(counts["available"], 41)
        self.assertEqual(counts["disabled"], 0)
        self.assertEqual(superpowers["plugin_id"], SUPERPOWERS_PLUGIN)
        self.assertTrue(superpowers["disabled"])

    def test_manifest_preserves_native_matt_skill_activation_partition(self) -> None:
        manifest = load_toml(POLICY_MANIFEST)
        counts = manifest["matt_pocock"]["counts"]
        skills = manifest["matt_pocock"]["skills"]

        implicit = set(skills["implicit"])
        explicit_only = set(skills["explicit_only"])

        self.assertEqual(implicit, EXPECTED_IMPLICIT_SKILLS)
        self.assertEqual(explicit_only, EXPECTED_EXPLICIT_ONLY_SKILLS)
        self.assertTrue(implicit.isdisjoint(explicit_only))
        self.assertEqual(len(implicit | explicit_only), 41)
        self.assertEqual(counts["implicit"], 17)
        self.assertEqual(counts["explicit_only"], 24)

    def test_manifest_documents_new_session_activation_and_non_upstream_exclusion(
        self,
    ) -> None:
        manifest = load_toml(POLICY_MANIFEST)
        counts = manifest["matt_pocock"]["counts"]
        inventory = manifest["matt_pocock"]["inventory"]

        self.assertTrue(manifest["activation_requires_new_session"])
        self.assertNotIn("restart_required", manifest)
        self.assertEqual(counts["project_disabled"], 0)
        self.assertEqual(inventory["excluded_non_upstream"], ["netease-uu-booster"])

    def test_repository_has_no_legacy_superpowers_artifacts_or_live_references(
        self,
    ) -> None:
        legacy_name = "super" + "powers"
        legacy_docs = ROOT / "docs" / legacy_name
        legacy_state = ROOT / f".{legacy_name}"
        forbidden_references = (
            f"docs/{legacy_name}/",
            f".{legacy_name}/sdd",
            f"{legacy_name}:",
        )

        self.assertFalse(legacy_docs.exists(), f"remove legacy directory: {legacy_docs}")
        self.assertFalse(legacy_state.exists(), f"remove legacy directory: {legacy_state}")

        findings: list[str] = []
        excluded = {MIGRATION_RECORD.resolve(), Path(__file__).resolve()}
        for path in iter_project_files(ROOT):
            if path.resolve() in excluded or not is_text_file(path):
                continue
            text = read_text(path)
            for marker in forbidden_references:
                if marker in text:
                    findings.append(f"{path.relative_to(ROOT).as_posix()}: {marker}")

        self.assertEqual(findings, [], "remove legacy live references")


if __name__ == "__main__":
    unittest.main()
