import unittest

from fbhub.topology import (
    Location,
    location_matches,
    matches_selector,
    parse_location,
)


class TopologyTests(unittest.TestCase):
    def test_parse_full_location(self):
        loc = parse_location("1D00:0-1.3")
        self.assertEqual(loc.prefix, "1D00")
        self.assertEqual(loc.root_hub, 0)
        self.assertEqual(loc.ports, (1, 3))
        self.assertEqual(loc.hub_port, 1)
        self.assertEqual(loc.index, 3)
        self.assertEqual(str(loc), "1D00:0-1.3")

    def test_parse_short_chain(self):
        loc = parse_location("1.3")
        self.assertEqual(loc.ports, (1, 3))
        self.assertEqual(loc.prefix, "USB")

    def test_location_matching(self):
        self.assertTrue(location_matches("1D00:0-1.3", "1D00:0-1.3"))
        self.assertTrue(location_matches("1D00:0-1.3", "0-1.3"))
        self.assertTrue(location_matches("1D00:0-1.3", "1.3"))
        self.assertFalse(location_matches("1D00:0-1.3", "1D00:0-1.4"))
        self.assertFalse(location_matches("1D00:0-1.3", "1A00:0-1.3"))

    def test_selector_hub_index(self):
        self.assertTrue(
            matches_selector(location="1D00:0-1.3", serial=None, hub=1, index=3)
        )
        self.assertFalse(
            matches_selector(location="1D00:0-1.3", serial=None, hub=2, index=3)
        )

    def test_selector_serial_and_alias(self):
        self.assertTrue(matches_selector(location="1D00:0-1.3", serial="ABC",
                                         serials=["abc"]))
        self.assertTrue(matches_selector(location="1D00:0-1.3", serial=None,
                                         alias="工位A", aliases=["工位a"]))
        self.assertFalse(matches_selector(location="1D00:0-1.3", serial=None,
                                          aliases=["工位B"]))

    def test_invalid_location(self):
        with self.assertRaises(ValueError):
            parse_location("not-a-port")


if __name__ == "__main__":
    unittest.main()
