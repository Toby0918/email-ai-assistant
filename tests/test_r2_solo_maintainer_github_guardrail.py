"""Authenticated GitHub guardrail observation tests for the private closure seam."""

from __future__ import annotations

import json
import subprocess
import sys
import unittest
from unittest.mock import patch

from backend.r2_solo_maintainer_closure._canonical import canonical_json, fingerprint
from backend.r2_solo_maintainer_closure.contracts import (
    ClosureErrorCode,
    SoloMaintainerClosureError,
)
from backend.r2_solo_maintainer_closure.github_guardrail import (
    _GH_EXECUTABLE,
    _MAX_OUTPUT,
    _GhGuardrailReadAdapter,
    _GuardrailObservation,
    _run_process,
    collect_verified_guardrail,
)
from backend.r2_solo_maintainer_closure.hosted_evidence import ruleset_configuration_v1


_LISTING_PATH = (
    "/repos/Toby0918/email-ai-assistant/rulesets?ref=refs/heads/master"
    "&includes_parents=false&per_page=100"
)
_DETAIL_PATH = "/repos/Toby0918/email-ai-assistant/rulesets/20601214"
_CLASSIC_PATH = "/repos/Toby0918/email-ai-assistant/branches/master/protection"
_CLASSIC_MISSING_STDERR = b"gh: Branch not protected (HTTP 404)\n"
_ABSENT = object()


class _FakeReader:
    def __init__(self, observation: object) -> None:
        self.observation = observation
        self.call_count = 0

    def read(self) -> object:
        self.call_count += 1
        return self.observation


class _SequenceRunner:
    def __init__(self, *results: tuple[int, bytes, bytes]) -> None:
        self._results = iter(results)
        self.calls: list[tuple[tuple[str, ...], dict[str, str]]] = []

    def __call__(self, arguments: tuple[str, ...], environment: dict[str, str]):
        self.calls.append((arguments, dict(environment)))
        return_code, stdout, stderr = next(self._results)
        return subprocess.CompletedProcess(arguments, return_code, stdout, stderr)


def _copy(value: object) -> object:
    return json.loads(json.dumps(value))


def _detail(required_reviewers: object = _ABSENT) -> dict[str, object]:
    detail = _copy(ruleset_configuration_v1())
    if required_reviewers is not _ABSENT:
        detail["rules"][2]["parameters"]["required_reviewers"] = required_reviewers
    return detail


def _listing() -> list[dict[str, object]]:
    return [{
        "id": 20601214,
        "name": "master-solo-maintainer-closure-v1",
        "target": "branch",
        "enforcement": "active",
    }]


def _observation(
    *, detail: object = _ABSENT, listing: object = _ABSENT,
    classic_present: object = False,
) -> _GuardrailObservation:
    return _GuardrailObservation(
        listing=_listing() if listing is _ABSENT else listing,
        detail=_detail([]) if detail is _ABSENT else detail,
        classic_branch_protection_present=classic_present,
    )


def _auth(
    *, login: str = "Toby0918", state: str = "success", active: object = True,
    token_source: str = "keyring", protocol: str = "https",
) -> bytes:
    return json.dumps({"hosts": {"github.com": [{
        "state": state,
        "active": active,
        "host": "github.com",
        "login": login,
        "tokenSource": token_source,
        "scopes": "gist, read:org, repo, workflow",
        "gitProtocol": protocol,
    }]}}).encode("utf-8")


def _api(status: int, body: object = _ABSENT) -> bytes:
    reason = "OK" if status == 200 else "Not Found"
    header = f"HTTP/2.0 {status} {reason}\r\nContent-Type: application/json\r\n\r\n"
    payload = b"" if body is _ABSENT else json.dumps(body).encode("utf-8")
    return header.encode("ascii") + payload


def _success_runner(*, final_auth: bytes | None = None) -> _SequenceRunner:
    return _SequenceRunner(
        (0, _auth(), b""),
        (0, _api(200, _listing()), b""),
        (0, _api(200, _detail([])), b""),
        (1, _api(404, {"message": "Branch not protected"}), _CLASSIC_MISSING_STDERR),
        (0, final_auth if final_auth is not None else _auth(), b""),
    )


class GitHubGuardrailCompatibilityTests(unittest.TestCase):
    def assert_guardrail_rejected(self, reader: object) -> None:
        with self.assertRaises(SoloMaintainerClosureError) as caught:
            collect_verified_guardrail(reader)
        self.assertEqual(
            caught.exception.code,
            ClosureErrorCode.GITHUB_GUARDRAIL_REJECTED,
        )

    def test_in_memory_reader_accepts_only_empty_beta_default(self) -> None:
        reader = _FakeReader(_observation())

        snapshot = collect_verified_guardrail(reader)

        self.assertEqual(reader.call_count, 1)
        self.assertEqual(snapshot.ruleset_id, 20601214)
        self.assertEqual(snapshot.ruleset_configuration, ruleset_configuration_v1())
        self.assertEqual(len(canonical_json(snapshot.ruleset_configuration)), 965)
        self.assertEqual(
            snapshot.ruleset_configuration_fingerprint,
            "5f1c00727e4637c58abc7a8299f6c5846be0d8b6b3511d84bf3114e17422ca6e",
        )
        self.assertEqual(
            fingerprint("r2-github-ruleset-configuration-v1", ruleset_configuration_v1()),
            snapshot.ruleset_configuration_fingerprint,
        )

    def test_zero_approval_ruleset_accepts_enabled_unattributed_default(self) -> None:
        detail = _detail([])
        detail["rules"][2]["parameters"][
            "require_extra_approval_for_unattributed_changes"
        ] = True

        snapshot = collect_verified_guardrail(
            _FakeReader(_observation(detail=detail))
        )

        self.assertEqual(snapshot.ruleset_configuration, ruleset_configuration_v1())
        self.assertEqual(len(canonical_json(snapshot.ruleset_configuration)), 965)
        self.assertEqual(
            snapshot.ruleset_configuration_fingerprint,
            "5f1c00727e4637c58abc7a8299f6c5846be0d8b6b3511d84bf3114e17422ca6e",
        )

    def test_unattributed_default_requires_exact_true_and_exact_zero_count(self) -> None:
        field = "require_extra_approval_for_unattributed_changes"
        for value in (False, 0, 1, None, "true", [], {}):
            detail = _detail([])
            detail["rules"][2]["parameters"][field] = value
            with self.subTest(field_value=value):
                self.assert_guardrail_rejected(
                    _FakeReader(_observation(detail=detail))
                )
        for value in (True, False, 1, -1, None, "0"):
            detail = _detail([])
            detail["rules"][2]["parameters"][field] = True
            detail["rules"][2]["parameters"][
                "required_approving_review_count"
            ] = value
            with self.subTest(approval_count=value):
                self.assert_guardrail_rejected(
                    _FakeReader(_observation(detail=detail))
                )

    def test_beta_field_may_be_absent(self) -> None:
        snapshot = collect_verified_guardrail(_FakeReader(_observation(detail=_detail())))
        self.assertEqual(snapshot.ruleset_configuration, ruleset_configuration_v1())

    def test_top_level_observational_metadata_does_not_change_canonical_contract(self) -> None:
        detail = _detail([])
        detail["updated_at"] = "2026-08-09T00:00:00Z"
        detail["current_user_can_bypass"] = "never"
        snapshot = collect_verified_guardrail(_FakeReader(_observation(detail=detail)))
        self.assertEqual(snapshot.ruleset_configuration, ruleset_configuration_v1())

    def test_missing_or_nonempty_bypass_is_rejected(self) -> None:
        for bypass in (_ABSENT, (), [{"actor_id": 1}]):
            detail = _detail([])
            if bypass is _ABSENT:
                del detail["bypass_actors"]
            else:
                detail["bypass_actors"] = bypass
            with self.subTest(bypass=bypass):
                self.assert_guardrail_rejected(_FakeReader(_observation(detail=detail)))

    def test_nonempty_or_wrong_type_beta_field_is_rejected(self) -> None:
        for value in ((), [{"login": "reviewer"}], {}, None, 0, False):
            with self.subTest(value=value):
                self.assert_guardrail_rejected(
                    _FakeReader(_observation(detail=_detail(value)))
                )

    def test_duplicate_pull_request_or_nested_drift_is_rejected(self) -> None:
        duplicate = _detail([])
        duplicate["rules"].append(_copy(duplicate["rules"][2]))
        drift = _detail([])
        drift["rules"][3]["parameters"]["required_status_checks"][0][
            "integration_id"
        ] = 1
        for detail in (duplicate, drift):
            with self.subTest(detail=detail):
                self.assert_guardrail_rejected(
                    _FakeReader(_observation(detail=detail))
                )

    def test_layered_ruleset_or_classic_protection_is_rejected(self) -> None:
        layered = _listing() + [{
            "id": 2,
            "name": "unexpected-layer",
            "target": "branch",
            "enforcement": "active",
        }]
        self.assert_guardrail_rejected(
            _FakeReader(_observation(listing=layered))
        )
        self.assert_guardrail_rejected(
            _FakeReader(_observation(classic_present=True))
        )

    def test_ruleset_id_must_be_a_positive_exact_integer(self) -> None:
        for value in (True, 0, -1, "20601214"):
            listing = _listing()
            listing[0]["id"] = value
            with self.subTest(value=value):
                self.assert_guardrail_rejected(
                    _FakeReader(_observation(listing=listing))
                )

    def test_adapter_uses_fixed_authenticated_get_commands_and_sanitized_environment(self) -> None:
        runner = _success_runner()
        hostile = {
            "GH_TOKEN": "secret-gh",
            "GITHUB_TOKEN": "secret-github",
            "GH_ENTERPRISE_TOKEN": "secret-enterprise",
            "GITHUB_ENTERPRISE_TOKEN": "secret-enterprise-github",
            "GH_HOST": "evil.example",
            "GH_REPO": "other/repository",
            "GH_CONFIG_DIR": "C:\\hostile",
            "HTTP_PROXY": "http://evil.example",
            "HTTPS_PROXY": "http://evil.example",
            "ALL_PROXY": "http://evil.example",
        }
        with patch.dict("os.environ", hostile, clear=False):
            snapshot = collect_verified_guardrail(_GhGuardrailReadAdapter(runner))

        self.assertEqual(snapshot.ruleset_id, 20601214)
        auth = (
            _GH_EXECUTABLE, "auth", "status", "--active", "--hostname",
            "github.com", "--json", "hosts",
        )
        api_prefix = (
            _GH_EXECUTABLE, "api", "--hostname", "github.com", "--method", "GET",
            "--include", "--header", "Accept:application/vnd.github+json",
        )
        self.assertEqual(
            [arguments for arguments, _environment in runner.calls],
            [
                auth,
                (*api_prefix, _LISTING_PATH),
                (*api_prefix, _DETAIL_PATH),
                (*api_prefix, _CLASSIC_PATH),
                auth,
            ],
        )
        for _arguments, environment in runner.calls:
            self.assertEqual(environment["GH_PROMPT_DISABLED"], "1")
            self.assertEqual(environment["GH_NO_UPDATE_NOTIFIER"], "1")
            self.assertEqual(environment["GH_NO_EXTENSION_UPDATE_NOTIFIER"], "1")
            self.assertEqual(environment["GH_TELEMETRY"], "0")
            self.assertEqual(environment["DO_NOT_TRACK"], "1")
            for name in hostile:
                self.assertNotIn(name, environment)
            self.assertNotIn("secret", "".join(environment.values()).lower())

    def test_unapproved_repository_endpoint_is_rejected_before_process_execution(self) -> None:
        runner = _SequenceRunner()
        adapter = _GhGuardrailReadAdapter(runner)

        with self.assertRaises(SoloMaintainerClosureError):
            adapter._api_json("/repos/Toby0918/email-ai-assistant/issues/38")

        self.assertEqual(runner.calls, [])

    def test_production_runner_keeps_stdout_and_stderr_separate_and_bounded(self) -> None:
        result = _run_process((
            sys.executable,
            "-I",
            "-c",
            "import sys;sys.stdout.buffer.write(b'out');sys.stderr.buffer.write(b'err')",
        ), {})
        self.assertEqual(result.stdout, b"out")
        self.assertEqual(result.stderr, b"err")

        with self.assertRaises(SoloMaintainerClosureError):
            _run_process((
                sys.executable,
                "-I",
                "-c",
                f"import sys;sys.stdout.buffer.write(b'x'*{_MAX_OUTPUT + 1})",
            ), {})

    def test_production_runner_times_out_and_reaps_the_child(self) -> None:
        with patch(
            "backend.r2_solo_maintainer_closure.github_guardrail._TIMEOUT_SECONDS",
            0.05,
        ):
            with self.assertRaises(SoloMaintainerClosureError):
                _run_process((
                    sys.executable,
                    "-I",
                    "-c",
                    "import time;time.sleep(5)",
                ), {})

    def test_authentication_identity_drift_is_rejected(self) -> None:
        runner = _success_runner(final_auth=_auth(login="different-user"))
        self.assert_guardrail_rejected(_GhGuardrailReadAdapter(runner))

    def test_authentication_state_source_and_protocol_must_be_exact(self) -> None:
        values = (
            _auth(state="failure"),
            _auth(active=False),
            _auth(token_source="GH_TOKEN"),
            _auth(protocol="ssh"),
        )
        for payload in values:
            with self.subTest(payload=payload):
                self.assert_guardrail_rejected(
                    _GhGuardrailReadAdapter(_SequenceRunner((0, payload, b"")))
                )

    def test_reader_failure_is_content_free_and_observation_is_never_cached(self) -> None:
        class FailingReader:
            def read(self) -> object:
                raise RuntimeError("sensitive transport detail")

        with self.assertRaises(SoloMaintainerClosureError) as caught:
            collect_verified_guardrail(FailingReader())
        self.assertEqual(str(caught.exception), ClosureErrorCode.GITHUB_GUARDRAIL_REJECTED.value)
        self.assertNotIn("sensitive", str(caught.exception))

        reader = _FakeReader(_observation())
        collect_verified_guardrail(reader)
        collect_verified_guardrail(reader)
        self.assertEqual(reader.call_count, 2)

    def test_transport_status_json_stderr_and_oversize_fail_content_free(self) -> None:
        cases = (
            _SequenceRunner((1, b"", b"auth failed with sensitive detail")),
            _SequenceRunner((0, b"not-json", b"")),
            _SequenceRunner((0, b'{"hosts":{},"hosts":{}}', b"")),
            _SequenceRunner(
                (0, _auth(), b""),
                (0, _api(500, {"message": "sensitive"}), b""),
            ),
            _SequenceRunner((0, b"{" + b"x" * (1024 * 1024) + b"}", b"")),
        )
        for runner in cases:
            with self.subTest(call_count=len(runner.calls)):
                self.assert_guardrail_rejected(_GhGuardrailReadAdapter(runner))

    def test_only_classic_protection_404_is_accepted_as_absent(self) -> None:
        cases = (
            (0, _api(403, {"message": "forbidden"}), b""),
            (1, _api(404, {"message": "Branch not protected"}), b"unexpected\n"),
            (0, _api(404, {"message": "Branch not protected"}), _CLASSIC_MISSING_STDERR),
        )
        for classic_result in cases:
            runner = _SequenceRunner(
                (0, _auth(), b""),
                (0, _api(200, _listing()), b""),
                (0, _api(200, _detail([])), b""),
                classic_result,
            )
            with self.subTest(classic_result=classic_result):
                self.assert_guardrail_rejected(_GhGuardrailReadAdapter(runner))


if __name__ == "__main__":
    unittest.main()
