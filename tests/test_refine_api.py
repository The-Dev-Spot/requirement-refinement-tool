"""The public controller import documented in the operating contract stays usable."""
import unittest


class PublicApiTests(unittest.TestCase):
    def test_public_controller_is_the_governed_implementation(self):
        from clarity.refine import Controller, VERSION
        from clarity.refine.controller import Controller as Implementation
        self.assertIs(Controller, Implementation)
        self.assertEqual(VERSION, "0.3.0")
