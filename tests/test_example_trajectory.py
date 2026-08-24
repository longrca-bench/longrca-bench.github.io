from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = REPO_ROOT / "data" / "example_trajectory.json"
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import validate_data as validator  # noqa: E402


class ExampleTrajectoryTest(unittest.TestCase):
    def test_example_data_and_validator_are_part_of_the_site_contract(self) -> None:
        self.assertTrue(DATA_PATH.is_file())
        self.assertTrue(hasattr(validator, "validate_example_trajectory"))

    @unittest.skipUnless(DATA_PATH.is_file(), "example trajectory is not implemented yet")
    def test_example_preserves_the_failed_77_step_trace(self) -> None:
        payload = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        validator.validate_example_trajectory(payload)

        self.assertEqual("TravelPlanner", payload["benchmark"])
        self.assertEqual("TASK_COMPLETE", payload["agent_status"])
        self.assertEqual("Failed", payload["outcome"])
        self.assertEqual(8, len(payload["actors"]))
        self.assertEqual(77, len(payload["events"]))
        self.assertEqual(list(range(77)), [event["index"] for event in payload["events"]])
        self.assertNotIn("failure_path", payload)
        self.assertNotIn("final_failure", payload)

        final_error = payload["events"][74]
        self.assertEqual("writer", final_error["actor"])
        self.assertEqual("error", final_error["tone"])
        self.assertIn("caveat", final_error["detail"].casefold())

    @unittest.skipUnless(DATA_PATH.is_file(), "example trajectory is not implemented yet")
    def test_nonsequential_event_indices_are_rejected(self) -> None:
        payload = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        payload["events"][20]["index"] = 21
        with self.assertRaisesRegex(ValueError, "sequential"):
            validator.validate_example_trajectory(payload)

    @unittest.skipUnless(DATA_PATH.is_file(), "example trajectory is not implemented yet")
    def test_unknown_actor_is_rejected(self) -> None:
        payload = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        payload["events"][0]["actor"] = "unknown"
        with self.assertRaisesRegex(ValueError, "unknown actor"):
            validator.validate_example_trajectory(payload)

    @unittest.skipUnless(DATA_PATH.is_file(), "example trajectory is not implemented yet")
    def test_gold_root_claim_is_rejected(self) -> None:
        payload = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        payload["gold_root_step"] = 24
        with self.assertRaisesRegex(ValueError, "gold root"):
            validator.validate_example_trajectory(payload)

    @unittest.skipUnless(DATA_PATH.is_file(), "example trajectory is not implemented yet")
    def test_source_event_taxonomy_and_blackboard_totals_are_preserved(self) -> None:
        payload = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        kinds = {event["kind"] for event in payload["events"]}
        self.assertTrue({"handoff", "tool", "verify", "error", "final"}.issubset(kinds))
        self.assertEqual(
            {"candidates": 23, "checks": 8, "notes": 4},
            payload["events"][-1]["state"],
        )
        self.assertEqual("error", payload["events"][55]["kind"])
        self.assertIn("parse", payload["events"][55]["detail"].casefold())


if __name__ == "__main__":
    unittest.main()
