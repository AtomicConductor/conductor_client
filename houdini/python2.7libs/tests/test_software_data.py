import unittest
import json
import sys
import os

HDA_MODULE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if HDA_MODULE not in sys.path:
    sys.path.insert(0, HDA_MODULE)

# mocked api_client returns json fixtures in
sys.modules['conductor.lib.api_client'] = __import__(
    'tests.mocks.api_client_mock', fromlist=['dummy'])

from hda import software_data as swd


class SoftwareDataTest(unittest.TestCase):

    def test_smoke(self):
        pt = swd.PackageTree()
        self.assertIsInstance(pt, swd.PackageTree)

    def test_init_from_json(self):
        obj = {"some": "object"}
        tree = json.dumps(obj)
        pt = swd.PackageTree(json=tree)
        self.assertEqual(pt.tree, obj)

    def test_init_with_product(self):
        pt = swd.PackageTree(product="houdini")
        self.assertEqual(len(pt.tree["children"]), 2)
        pt = swd.PackageTree(product="maya-io")
        self.assertEqual(len(pt.tree["children"]), 9)

    def test_init_with_no_product(self):
        pt = swd.PackageTree()
        self.assertEqual(len(pt.tree["children"]), 72)

    def test_init_with_sub_product(self):
        pt = swd.PackageTree(product="arnold-houdini")
        self.assertEqual(len(pt.tree["children"]), 4)


# def test_replace_context(self):
#     exp = Expander(toka="foo", tokb="bar")
#     exp.context = {"tokc": "baz", "tokb": "bar"}
#     self.assertEqual(exp.context, {"tokc": "baz", "tokb": "bar"})

# def test_evaluate_string(self):
#     exp = Expander(toka="foo", tokb="bar")
#     result = exp.evaluate("Hello <toka> --<tokb>--")
#     self.assertEqual(result, "Hello foo --bar--")

# def test_multiple_occurrences(self):
#     exp = Expander(toka="foo", tokb="bar")
#     result = exp.evaluate("Hello <toka> --<tokb>--<toka><toka>-s")
#     self.assertEqual(result, "Hello foo --bar--foofoo-s")

# def test_evaluate_bad_string_raises(self):
#     exp = Expander(toka="foo", tokb="bar")
#     with self.assertRaises(ValueError):
#         exp.evaluate("Hello <tokc> --<tokb>--")

# def test_evaluate_list(self):
#     exp = Expander(toka="foo", tokb="bar")
#     result = exp.evaluate(["Hello <toka> --<tokb>--", "Goodbye <tokb>"])
#     self.assertIn("Hello foo --bar--", result)
#     self.assertEqual(len(result), 2)

# def test_evaluate_bad_list_raises(self):
#     exp = Expander(toka="foo", tokb="bar")
#     with self.assertRaises(ValueError):
#         exp.evaluate(["Hello <toka>", "Goodbye <tokc>"])

# def test_evaluate_dict(self):
#     exp = Expander(toka="foo", tokb="bar")
#     result = exp.evaluate(
#         {"a": "Hello <toka> --<tokb>--", "b": "Goodbye <tokb>"})
#     self.assertDictContainsSubset({"a": "Hello foo --bar--"}, result)
#     self.assertEqual(len(result.keys()), 2)

# def test_evaluate_bad_dict_raises(self):
#     exp = Expander(toka="foo", tokb="bar")
#     with self.assertRaises(ValueError):
#         exp.evaluate(
#             {"a": "Hello <toka> --<tokb>--", "b": "Goodbye <tokc>"})


if __name__ == '__main__':
    unittest.main()
