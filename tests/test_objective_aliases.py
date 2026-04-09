import json
import unittest

from battery_agent.kb import normalize_objective_key
from battery_agent.tools import design_battery_protocol


class ObjectiveAliasTests(unittest.TestCase):
    def test_capacity_test_alias_maps_to_rate_capability(self) -> None:
        self.assertEqual(normalize_objective_key("capacity_test"), "rate_capability")
        self.assertEqual(normalize_objective_key("capacity test"), "rate_capability")
        self.assertEqual(normalize_objective_key("capacity"), "rate_capability")

    def test_capacity_test_objective_builds_protocol(self) -> None:
        payload = json.loads(
            design_battery_protocol.invoke(
                {
                    "objective": "capacity test",
                    "chemistry": "nca",
                    "instrument": "biologic_bcs815",
                    "form_factor": "cylindrical",
                }
            )
        )

        self.assertEqual(payload["status"], "draft")
        self.assertEqual(payload["method_id"], "capacity_test")
        self.assertEqual(payload["chemistry"], "NCA")
        self.assertEqual(payload["instrument"], "BioLogic BCS-815")


if __name__ == "__main__":
    unittest.main()
