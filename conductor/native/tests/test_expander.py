""" test sequence

   isort:skip_file
"""
import os
import sys
import unittest

from conductor.native.lib.expander import Expander

NATIVE_MODULE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if NATIVE_MODULE not in sys.path:
    sys.path.insert(0, NATIVE_MODULE)


class ExpanderTest(unittest.TestCase):

    def setUp(self):
        self.context = {
            "home": "/users/joebloggs/",
            "shot": "/metropolis/shot01/",
            "ct_dept": "texturing",
            "frames": 20,
            "directories": "/a/b /a/c"}

    def test_expand_value_target(self):
        e = Expander(**self.context)
        result = e.evaluate("x_<home>_y")
        self.assertEqual(result, "x_/users/joebloggs/_y")

    def test_expand_numeric_value_target(self):
        e = Expander(**self.context)
        result = e.evaluate("x_<frames>_y")
        self.assertEqual(result, "x_20_y")

    def test_expand_numeric_value_is_string(self):
        e = Expander(**self.context)
        result = e.evaluate("<frames>")
        self.assertIsInstance(result, str)
        self.assertEqual(result, "20")

    def test_bad_value_raises(self):
        e = Expander(**self.context)
        with self.assertRaises(KeyError):
            e.evaluate("<bad>")

    # lists
    def test_expand_list_target(self):
        e = Expander(**self.context)
        result = e.evaluate(["x_<shot>_y", "x_<ct_dept>_y"])
        self.assertIsInstance(result, list)
        self.assertEqual(result, ["x_/metropolis/shot01/_y", "x_texturing_y"])

    def test_expand_empty_list_target(self):
        e = Expander(**self.context)
        result = e.evaluate([])
        self.assertIsInstance(result, list)
        self.assertEqual(result, [])

    def test_bad_list_value_raises(self):
        e = Expander(**self.context)
        with self.assertRaises(KeyError):
            e.evaluate(["<bad>", "directories"])

    # dicts
    def test_expand_dict_target(self):
        e = Expander(**self.context)
        result = e.evaluate({"foo": "x_<shot>_y", "bar": "x_<ct_dept>_y"})
        self.assertIsInstance(result, dict)
        self.assertEqual(
            result, {"foo": "x_/metropolis/shot01/_y", "bar": "x_texturing_y"})

    def test_expand_empty_dict_target(self):
        e = Expander(**self.context)
        result = e.evaluate({})
        self.assertIsInstance(result, dict)
        self.assertEqual(result, {})

    def test_bad_dict_value_raises(self):
        e = Expander(**self.context)
        with self.assertRaises(KeyError):
            e.evaluate({"foo": "<bad>", "bar": "directories"})


if __name__ == '__main__':
    unittest.main()
