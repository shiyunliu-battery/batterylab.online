import unittest

from battery_agent.kb import get_safety_checklist, get_thermal_chamber_rule, list_instrument_rule_keys


class ChamberConstraintTests(unittest.TestCase):
    def test_thermal_chamber_rule_is_separate_from_instrument_rules(self) -> None:
        self.assertNotIn("thermal_chambers", list_instrument_rule_keys())

        chamber_rule = get_thermal_chamber_rule("binder_lit_mk")
        self.assertEqual(chamber_rule["temperature_range_c"], [-40, 110])
        self.assertIn("CO2 fire suppression", chamber_rule["integrated_safety_systems"])

    def test_curated_neware_tester_rules_are_available_for_planning(self) -> None:
        instrument_keys = list_instrument_rule_keys()
        self.assertIn("neware_bts4000_5v6a_8ch", instrument_keys)
        self.assertIn("neware_ct4008_5v30a_na", instrument_keys)
        self.assertIn("neware_bts4000_100v60a_1ch", instrument_keys)

    def test_chamber_checklist_items_only_appear_when_chamber_is_selected(self) -> None:
        base_checklist = get_safety_checklist("cycle_life")
        chamber_checklist = get_safety_checklist("cycle_life", thermal_chamber="binder_lit_mk")

        self.assertFalse(any("defined-load rule" in item for item in base_checklist))
        self.assertTrue(any("defined-load rule" in item for item in chamber_checklist))
        self.assertTrue(any("gas detection" in item.lower() for item in chamber_checklist))


if __name__ == "__main__":
    unittest.main()
