"""Issue #51 immutable Cutover Profile contract tests."""

from __future__ import annotations

import hashlib
import json
import unittest
from dataclasses import FrozenInstanceError, fields

from backend.cutover_contracts import CutoverContractError, CutoverProfileV1
from tests.cutover_contract_fixtures import (
    HostileComparison,
    HostileKey,
    valid_profile_body,
)


def canonical_json(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


class CutoverProfileContractTests(unittest.TestCase):
    def test_profile_binds_every_reviewed_role_without_host_paths(self) -> None:
        profile = CutoverProfileV1.create(valid_profile_body())
        value = profile.to_mapping()

        self.assertEqual(value["profile_type"], "CutoverProfileV1")
        self.assertEqual(len(value["role_selections"]), 14)
        self.assertEqual(len(value["evidence_roles"]), 6)
        self.assertEqual(len(value["reviewed_git_selections"]), 7)
        self.assertEqual(len(value["worktree_roster"]), 11)
        self.assertEqual(
            [item["placement"] for item in value["worktree_roster"]],
            ["embedded"] * 8 + ["external"] * 3,
        )
        self.assertEqual(value["runtime_inputs"]["python_version"], "3.12.13")
        self.assertEqual(value["runtime_inputs"]["sqlite_version"], "3.50.4")
        self.assertEqual(value["sqlite_source"]["publication"], "create_only")
        self.assertEqual(value["crx"]["publication"], "create_only")
        self.assertEqual(value["config"]["provider_mode"], "disabled")
        self.assertFalse(value["maintenance_rules"]["cleanup_authorized"])
        serialized = profile.to_canonical_json().decode("utf-8")
        for forbidden in ("D:\\", "/home/", "S-1-5-", "D:(A;", "refs/heads/"):
            self.assertNotIn(forbidden, serialized)

    def test_profile_is_frozen_slotted_and_repr_redacted(self) -> None:
        profile = CutoverProfileV1.create(valid_profile_body())

        self.assertFalse(hasattr(profile, "__dict__"))
        self.assertFalse(hasattr(CutoverProfileV1, "_from_body"))
        self.assertEqual(repr(profile), "CutoverProfileV1()")
        self.assertEqual(
            tuple(field.name for field in fields(CutoverProfileV1)),
            (
                "governing_master_commit",
                "operator_fingerprint",
                "role_selections",
                "evidence_roles",
                "reviewed_git_selections",
                "worktree_roster",
                "runtime_inputs",
                "sqlite_source",
                "crx",
                "config",
                "acl_policy",
                "maintenance_rules",
                "rollback_roles",
                "profile_fingerprint",
            ),
        )
        with self.assertRaises(FrozenInstanceError):
            profile.profile_fingerprint = "0" * 64
        with self.assertRaises(TypeError):
            CutoverProfileV1()

    def test_profile_fingerprint_and_json_are_deterministic(self) -> None:
        first_body = valid_profile_body()
        second_body = dict(reversed(list(first_body.items())))
        first = CutoverProfileV1.create(first_body)
        second = CutoverProfileV1.create(second_body)
        body_fingerprint = hashlib.sha256(canonical_json(first_body)).hexdigest()

        self.assertEqual(first.profile_fingerprint, body_fingerprint)
        self.assertEqual(first, second)
        self.assertEqual(first.to_canonical_json(), second.to_canonical_json())
        self.assertEqual(
            CutoverProfileV1.from_json(first.to_canonical_json()),
            first,
        )
        self.assertEqual(CutoverProfileV1.from_mapping(first.to_mapping()), first)

    def test_profile_parser_rejects_duplicate_unknown_and_noncanonical_json(
        self,
    ) -> None:
        profile = CutoverProfileV1.create(valid_profile_body())
        canonical = profile.to_canonical_json()
        duplicate = canonical.replace(
            b'{"acl_policy":',
            b'{"profile_type":"CutoverProfileV1","acl_policy":',
            1,
        )
        unknown = profile.to_mapping()
        unknown["message"] = "not allowed"
        pretty = json.dumps(profile.to_mapping(), indent=2).encode("utf-8")

        lone_surrogate = canonical.replace(
            b'"profile_type":"CutoverProfileV1"',
            b'"profile_type":"\\ud800"',
            1,
        )
        for payload in (duplicate, canonical + b" ", pretty, lone_surrogate):
            with self.subTest(payload=payload[:40]):
                with self.assertRaisesRegex(
                    CutoverContractError,
                    "^CUTOVER_PROFILE_INVALID$",
                ):
                    CutoverProfileV1.from_json(payload)
        with self.assertRaisesRegex(
            CutoverContractError,
            "^CUTOVER_PROFILE_INVALID$",
        ):
            CutoverProfileV1.from_mapping(unknown)

    def test_profile_parser_fails_closed_on_excessive_json_nesting(self) -> None:
        payload = (
            b'{"profile_type":'
            + b"[" * 5_000
            + b"0"
            + b"]" * 5_000
            + b"}"
        )

        with self.assertRaisesRegex(
            CutoverContractError,
            "^CUTOVER_PROFILE_INVALID$",
        ):
            CutoverProfileV1.from_json(payload)

    def test_profile_rejects_incomplete_or_redirectable_selections(self) -> None:
        mutations = []
        missing_role = valid_profile_body()
        del missing_role["role_selections"]["repository_root"]
        mutations.append(missing_role)
        path_value = valid_profile_body()
        path_value["evidence_roles"]["package_target"] = "D:\\package.zip"
        mutations.append(path_value)
        wrong_roster = valid_profile_body()
        wrong_roster["worktree_roster"] = wrong_roster["worktree_roster"][:-1]
        mutations.append(wrong_roster)
        wrong_placement = valid_profile_body()
        wrong_placement["worktree_roster"][8]["placement"] = "embedded"
        mutations.append(wrong_placement)
        wrong_runtime = valid_profile_body()
        wrong_runtime["runtime_inputs"]["python_version"] = "3.13.0"
        mutations.append(wrong_runtime)
        environment_config = valid_profile_body()
        environment_config["config"]["reads_environment"] = True
        mutations.append(environment_config)
        cleanup_enabled = valid_profile_body()
        cleanup_enabled["maintenance_rules"]["cleanup_authorized"] = True
        mutations.append(cleanup_enabled)

        for value in mutations:
            with self.subTest(value=value):
                with self.assertRaisesRegex(
                    CutoverContractError,
                    "^CUTOVER_PROFILE_INVALID$",
                ):
                    CutoverProfileV1.create(value)

    def test_profile_rejects_boolean_counts_and_tampered_fingerprint(self) -> None:
        boolean_size = valid_profile_body()
        boolean_size["crx"]["size_bytes"] = True
        with self.assertRaises(CutoverContractError):
            CutoverProfileV1.create(boolean_size)

        profile = CutoverProfileV1.create(valid_profile_body())
        tampered = profile.to_mapping()
        tampered["profile_fingerprint"] = "f" * 64
        with self.assertRaisesRegex(
            CutoverContractError,
            "^CUTOVER_PROFILE_INVALID$",
        ):
            CutoverProfileV1.from_mapping(tampered)

    def test_profile_mapping_fails_closed_before_hostile_comparison(self) -> None:
        mutations = []
        for section, field in (
            (None, "profile_type"),
            ("runtime_inputs", "python_version"),
            ("sqlite_source", "role"),
            ("crx", "publication"),
            ("config", "provider_mode"),
            ("acl_policy", "parent_mode"),
        ):
            body = valid_profile_body()
            target = body if section is None else body[section]
            target[field] = HostileComparison()
            mutations.append(body)
        roster = valid_profile_body()
        roster["worktree_roster"][0]["placement"] = HostileComparison()
        mutations.append(roster)
        allowed_keys = valid_profile_body()
        allowed_keys["config"]["allowed_keys"][0] = HostileComparison()
        mutations.append(allowed_keys)
        principals = valid_profile_body()
        principals["acl_policy"]["container_principal_roles"][0] = (
            HostileComparison()
        )
        mutations.append(principals)

        for value in mutations:
            with self.subTest(value=value):
                with self.assertRaisesRegex(
                    CutoverContractError,
                    "^CUTOVER_PROFILE_INVALID$",
                ):
                    CutoverProfileV1.create(value)

        mapping = CutoverProfileV1.create(valid_profile_body()).to_mapping()
        mapping["profile_fingerprint"] = HostileComparison()
        with self.assertRaisesRegex(
            CutoverContractError,
            "^CUTOVER_PROFILE_INVALID$",
        ):
            CutoverProfileV1.from_mapping(mapping)

        hostile_key = valid_profile_body()
        profile_type = hostile_key.pop("profile_type")
        hostile_key = {
            HostileKey("profile_type"): profile_type,
            **hostile_key,
        }
        with self.assertRaisesRegex(
            CutoverContractError,
            "^CUTOVER_PROFILE_INVALID$",
        ):
            CutoverProfileV1.create(hostile_key)

    def test_profile_mapping_results_do_not_alias_mutable_input(self) -> None:
        body = valid_profile_body()
        profile = CutoverProfileV1.create(body)
        before = profile.to_canonical_json()
        body["worktree_roster"].clear()
        body["config"]["allowed_keys"].clear()
        projected = profile.to_mapping()
        projected["role_selections"].clear()
        projected["acl_policy"]["container_principal_roles"].clear()

        self.assertEqual(profile.to_canonical_json(), before)


if __name__ == "__main__":
    unittest.main()
