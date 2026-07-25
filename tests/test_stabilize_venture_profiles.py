from __future__ import annotations

import copy
import unittest
from unittest.mock import patch

from tools import stabilize_venture_profiles as stabilizer


class VentureProfileStabilizerTests(unittest.TestCase):
    def test_converges_when_gates_need_multiple_passes(self) -> None:
        payload = {"value": 0}

        def finalize(value, _catalog):
            result = copy.deepcopy(value)
            result["value"] = max(1, int(result.get("value", 0)))
            return result, {"changedCompanies": int(result != value)}

        def enforce(value, _catalog):
            result = copy.deepcopy(value)
            result["value"] = max(2, int(result.get("value", 0)))
            return result, {"changedCompanies": int(result != value)}

        with patch.object(stabilizer, "finalize_snapshot", side_effect=finalize), patch.object(
            stabilizer, "enforce_snapshot", side_effect=enforce
        ):
            stabilized, diagnostics = stabilizer.stabilize_snapshot(payload, "catalog")

        self.assertEqual(stabilized, {"value": 2})
        self.assertTrue(diagnostics["converged"])
        self.assertGreaterEqual(diagnostics["passes"], 1)

    def test_rejects_a_cross_gate_cycle(self) -> None:
        payload = {"state": "a"}

        def finalize(value, _catalog):
            result = copy.deepcopy(value)
            result["state"] = "b"
            return result, {}

        def enforce(value, _catalog):
            result = copy.deepcopy(value)
            result["state"] = "a"
            return result, {}

        with patch.object(stabilizer, "finalize_snapshot", side_effect=finalize), patch.object(
            stabilizer, "enforce_snapshot", side_effect=enforce
        ):
            with self.assertRaisesRegex(RuntimeError, "cycle"):
                stabilizer.stabilize_snapshot(payload, "catalog", max_passes=4)

    def test_rejects_non_positive_pass_limit(self) -> None:
        with self.assertRaisesRegex(ValueError, "positive"):
            stabilizer.stabilize_snapshot({}, "catalog", max_passes=0)


if __name__ == "__main__":
    unittest.main()
