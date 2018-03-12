import unittest
import sys
import os

HDA_MODULE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if HDA_MODULE not in sys.path:
    sys.path.insert(0, HDA_MODULE)

from conductor.houdini.lib.expansion import Expander


class ExpanderTest(unittest.TestCase):

    def test_smoke(self):
        exp = Expander()
        self.assertIsInstance(exp, Expander)

    def test_init_empty_context(self):
        exp = Expander()
        self.assertEqual(exp.context, {})

    def test_init_with_context(self):
        exp = Expander(toka="foo", tokb="bar")
        self.assertEqual(exp.context, {"toka": "foo", "tokb": "bar"})

    def test_replace_context(self):
        exp = Expander(toka="foo", tokb="bar")
        exp.context = {"tokc": "baz", "tokb": "bar"}
        self.assertEqual(exp.context, {"tokc": "baz", "tokb": "bar"})

    def test_evaluate_string(self):
        exp = Expander(toka="foo", tokb="bar")
        result = exp.evaluate("Hello <toka> --<tokb>--")
        self.assertEqual(result, "Hello foo --bar--")

    def test_multiple_occurrences(self):
        exp = Expander(toka="foo", tokb="bar")
        result = exp.evaluate("Hello <toka> --<tokb>--<toka><toka>-s")
        self.assertEqual(result, "Hello foo --bar--foofoo-s")

    def test_evaluate_bad_string_raises(self):
        exp = Expander(toka="foo", tokb="bar")
        result = exp.evaluate("Hello <tokc> --<tokb>--")
        self.assertEqual(result, "Hello <tokc> --bar--")

    def test_evaluate_list(self):
        exp = Expander(toka="foo", tokb="bar")
        result = exp.evaluate(["Hello <toka> --<tokb>--", "Goodbye <tokb>"])
        self.assertIn("Hello foo --bar--", result)
        self.assertEqual(len(result), 2)

    def test_evaluate_bad_list_raises(self):
        exp = Expander(toka="foo", tokb="bar")
        result = exp.evaluate(["Hello <toka>", "Goodbye <tokc>"])
        self.assertIn("Goodbye <tokc>", result)

    def test_evaluate_dict(self):
        exp = Expander(toka="foo", tokb="bar")
        result = exp.evaluate(
            {"a": "Hello <toka> --<tokb>--", "b": "Goodbye <tokb>"})
        self.assertDictContainsSubset({"a": "Hello foo --bar--"}, result)
        self.assertEqual(len(result.keys()), 2)

    def test_evaluate_bad_dict_leaves_token_in_place(self):
        exp = Expander(toka="foo", tokb="bar")
        result = exp.evaluate(
            {"a": "Hello <toka> --<tokb>--", "b": "Goodbye <tokc>"})
        self.assertDictContainsSubset({"b": "Goodbye <tokc>"}, result)


if __name__ == '__main__':
    unittest.main()
