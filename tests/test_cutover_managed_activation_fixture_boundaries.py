from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FIXTURE_PREFIXES = (
    "issue57-approved-python-source-",
    "issue57-synthetic-",
)


@unittest.skipUnless(sys.platform == "win32", "Windows sandbox evidence")
class ManagedActivationFixtureBoundaryTests(unittest.TestCase):
    def test_caller_owned_parent_owns_both_issue57_fixture_directories(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(
            prefix="issue57-boundary-test-",
            dir=ROOT,
        ) as owner_name:
            environment = os.environ.copy()
            environment["ISSUE57_CALLER_PARENT"] = owner_name
            completed = subprocess.run(
                [sys.executable, "-B", "-c", _OBSERVE_FIXTURE_SCRIPT],
                cwd=ROOT,
                env=environment,
                check=True,
                capture_output=True,
                text=True,
                timeout=120,
            )

        observation = json.loads(completed.stdout)
        self.assertEqual(
            observation,
            {
                "drive_root_additions": [],
                "owned_prefixes": [
                    "issue57-approved-python-source-",
                    "issue57-synthetic-",
                ],
                "projects_top_additions": [],
            },
        )

    def test_live_shared_fixture_rejects_a_different_caller_parent(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(
            prefix="issue57-parent-binding-test-",
            dir=ROOT,
        ) as owner_name:
            environment = os.environ.copy()
            environment["ISSUE57_CALLER_PARENT"] = owner_name
            completed = subprocess.run(
                [sys.executable, "-B", "-c", _OBSERVE_PARENT_BINDING_SCRIPT],
                cwd=ROOT,
                env=environment,
                check=True,
                capture_output=True,
                text=True,
                timeout=120,
            )

        self.assertEqual(
            json.loads(completed.stdout),
            {"different_parent_rejected": True},
        )

    def test_default_parent_is_the_current_repository_root(self) -> None:
        completed = subprocess.run(
            [sys.executable, "-B", "-c", _OBSERVE_DEFAULT_PARENT_SCRIPT],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
            timeout=120,
        )

        self.assertEqual(
            json.loads(completed.stdout),
            {"repository_owned_prefixes": list(FIXTURE_PREFIXES)},
        )


_OBSERVE_FIXTURE_SCRIPT = textwrap.dedent(
    """
    import json
    import os
    import sys
    from pathlib import Path

    from tests.cutover_managed_activation_fixtures import build_runtime_scenario

    prefixes = (
        "issue57-approved-python-source-",
        "issue57-synthetic-",
    )
    caller_parent = Path(os.environ["ISSUE57_CALLER_PARENT"])
    drive_root = Path(sys._base_executable).resolve(strict=True).anchor
    repository_root = Path.cwd().resolve(strict=True)
    projects_root = next(
        (
            parent
            for parent in repository_root.parents
            if parent.name.casefold() == "projects"
        ),
        repository_root.parent,
    )
    drive_root_before = {
        child.name
        for child in Path(drive_root).iterdir()
        if child.is_dir() and child.name.startswith(prefixes)
    }
    projects_before = {
        child.name
        for child in projects_root.iterdir()
        if child.is_dir() and child.name.startswith(prefixes)
    }
    scenario = build_runtime_scenario(directory=caller_parent)
    try:
        owned_prefixes = sorted(
            prefix
            for prefix in prefixes
            if any(
                child.is_dir() and child.name.startswith(prefix)
                for child in caller_parent.iterdir()
            )
        )
        drive_root_after = {
            child.name
            for child in Path(drive_root).iterdir()
            if child.is_dir() and child.name.startswith(prefixes)
        }
        projects_after = {
            child.name
            for child in projects_root.iterdir()
            if child.is_dir() and child.name.startswith(prefixes)
        }
        print(
            json.dumps(
                {
                    "drive_root_additions": sorted(
                        drive_root_after - drive_root_before
                    ),
                    "owned_prefixes": owned_prefixes,
                    "projects_top_additions": sorted(
                        projects_after - projects_before
                    ),
                },
                sort_keys=True,
            )
        )
    finally:
        scenario.close()
    """
)


_OBSERVE_PARENT_BINDING_SCRIPT = textwrap.dedent(
    """
    import json
    import os
    from pathlib import Path

    from tests.cutover_managed_activation_fixtures import build_runtime_scenario

    owner = Path(os.environ["ISSUE57_CALLER_PARENT"])
    first_parent = owner / "first"
    second_parent = owner / "second"
    first_parent.mkdir()
    second_parent.mkdir()
    first = build_runtime_scenario(directory=first_parent)
    second = None
    try:
        try:
            second = build_runtime_scenario(directory=second_parent)
        except RuntimeError:
            rejected = True
        else:
            rejected = False
        print(json.dumps({"different_parent_rejected": rejected}))
    finally:
        if second is not None:
            second.close()
        first.close()
    """
)


_OBSERVE_DEFAULT_PARENT_SCRIPT = textwrap.dedent(
    """
    import json
    from pathlib import Path

    from tests.cutover_managed_activation_fixtures import build_runtime_scenario

    prefixes = (
        "issue57-approved-python-source-",
        "issue57-synthetic-",
    )
    repository_root = Path.cwd().resolve(strict=True)
    scenario = build_runtime_scenario()
    try:
        observed = sorted(
            prefix
            for prefix in prefixes
            if any(
                child.is_dir() and child.name.startswith(prefix)
                for child in repository_root.iterdir()
            )
        )
        print(json.dumps({"repository_owned_prefixes": observed}))
    finally:
        scenario.close()
    """
)


if __name__ == "__main__":
    unittest.main()
