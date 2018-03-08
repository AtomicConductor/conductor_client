import unittest
import json
import sys
import os
import random


HDA_MODULE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if HDA_MODULE not in sys.path:
    sys.path.insert(0, HDA_MODULE)

# mocked api_client returns json fixtures
sys.modules['conductor.lib.api_client'] = __import__(
    'tests.mocks.api_client_mock', fromlist=['dummy'])

from hda import software_data as swd


class RemoveUnreachableTest(unittest.TestCase):

    def test_single_valid_tree_unchanged(self):
        paths = ["a", "a/b", "a/b/c"]
        results = swd.remove_unreachable(paths)
        self.assertEqual(results, paths)

    def test_many_valid_trees_unchanged(self):
        paths = ["a", "a/b", "a/b/c", "b", "b/b", "b/b/c", "c", "c/b", "c/b/c"]
        results = swd.remove_unreachable(paths)
        self.assertEqual(results, paths)

    def test_single_invalid_tree_culled_leaf(self):
        paths = ["a", "a/b", "b/b/c"]
        results = swd.remove_unreachable(paths)
        self.assertEqual(results, ["a", "a/b"])

    def test_single_invalid_tree_culled_below(self):
        paths = ["a", "b/b", "a/b/c"]
        results = swd.remove_unreachable(paths)
        self.assertEqual(results, ["a"])

    def test_multiple_invalid_tree_culled(self):
        paths = ["a", "a/b", "a/b/c", "b", "b/b", "b/b/c", "d", "c/b", "c/b/c"]
        results = swd.remove_unreachable(paths)
        self.assertEqual(
            results, [
                "a", "a/b", "a/b/c", "b", "b/b", "b/b/c", "d"])

    def test_random_input_order(self):
        paths = ["a", "a/b", "a/b/c", "b", "b/b", "b/b/c", "d", "c/b", "c/b/c"]
        random.shuffle(paths)
        results = swd.remove_unreachable(paths)
        self.assertEqual(
            results, [
                "a", "a/b", "a/b/c", "b", "b/b", "b/b/c", "d"])


class ToNameTest(unittest.TestCase):

    def test_major_only(self):
        pkg = {
            "product": "foo-bar",
            "major_version": "1",
            "minor_version": "",
            "release_version": "",
            "build_version": ""
        }
        expected = "foo-bar 1"
        self.assertEqual(swd.to_name(pkg), expected)

    def test_major_minor(self):
        pkg = {
            "product": "foo-bar",
            "major_version": "1",
            "minor_version": "3",
            "release_version": "",
            "build_version": ""
        }
        expected = "foo-bar 1.3"
        self.assertEqual(swd.to_name(pkg), expected)

    def test_major_minor_release(self):
        pkg = {
            "product": "foo-bar",
            "major_version": "1",
            "minor_version": "3",
            "release_version": "62",
            "build_version": ""
        }
        expected = "foo-bar 1.3.62"
        self.assertEqual(swd.to_name(pkg), expected)

    def test_major_minor_release_build(self):
        pkg = {
            "product": "foo-bar",
            "major_version": "1",
            "minor_version": "3",
            "release_version": "62",
            "build_version": "876"
        }
        expected = "foo-bar 1.3.62.876"
        self.assertEqual(swd.to_name(pkg), expected)


class SoftwareDataInitTest(unittest.TestCase):

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


class SoftwareDataFindByKeysTest(unittest.TestCase):

    def test_find_host_by_keys(self):
        keys = {
            'product': 'houdini',
            'major_version': '16',
            'minor_version': '5',
            'release_version': '323',
            'build_version': '',
            'plugin_host_product': '',
            'plugin_host_version': ''
        }
        pt = swd.PackageTree(product="houdini")
        pkg = pt.find_by_keys(**keys)
        self.assertEqual(pkg["product"], 'houdini')
        self.assertEqual(pkg["major_version"], '16')
        self.assertEqual(pkg["minor_version"], '5')
        self.assertEqual(pkg["release_version"], '323')

    def test_find_leaf_by_keys(self):
        keys = {
            'product': 'al-shaders',
            'major_version': '1',
            'minor_version': '1',
            'release_version': '',
            'build_version': '',
            'plugin_host_product': '',
            'plugin_host_version': ''
        }
        pt = swd.PackageTree(product="houdini")
        pkg = pt.find_by_keys(**keys)
        self.assertEqual(pkg["product"], 'al-shaders')
        self.assertEqual(pkg["major_version"], '1')
        self.assertEqual(pkg["minor_version"], '1')

    def test_find_nonexistent_package_returns_none(self):
        keys = {
            'product': 'arnold-houdini',
            'major_version': '7',
            'minor_version': '1',
            'release_version': '',
            'build_version': '',
            'plugin_host_product': '',
            'plugin_host_version': ''
        }
        pt = swd.PackageTree(product="houdini")
        pkg = pt.find_by_keys(**keys)
        self.assertEqual(pkg, None)


class SoftwareDataFindByPathTest(unittest.TestCase):

    def test_find_root_path(self):
        pt = swd.PackageTree(product="houdini")
        path = "houdini 16.0.736"
        pkgs = pt.find_by_path(path)

        self.assertEqual(len(pkgs), 1)
        self.assertEqual(swd.to_name(pkgs[0]), path)

    def test_find_leaf_path(self):
        pt = swd.PackageTree(product="houdini")
        path = "houdini 16.0.736/arnold-houdini 2.0.2.2/al-shaders 1.0"
        pkgs = pt.find_by_path(path)
        self.assertEqual(len(pkgs), 3)
        self.assertEqual(swd.to_name(pkgs[0]), "houdini 16.0.736")
        self.assertEqual(swd.to_name(pkgs[-1]), "al-shaders 1.0")

    def test_find_path_no_ancestors(self):
        pt = swd.PackageTree(product="houdini")
        path = "houdini 16.0.736/arnold-houdini 2.0.2.2"
        pkgs = pt.find_by_path(path, with_ancestors=False)
        self.assertEqual(len(pkgs), 1)
        self.assertEqual(
            swd.to_name(
                pkgs[0]),
            "arnold-houdini 2.0.2.2")

    def test_find_nonexistent_path_return_empty(self):
        pt = swd.PackageTree(product="houdini")
        path = "houdini 16.0.736/arnold-houdini 9.0.2.2"
        pkgs = pt.find_by_path(path)
        self.assertEqual(pkgs, [])
        pkgs = pt.find_by_path(path, with_ancestors=False)
        self.assertEqual(pkgs, [])

    def test_find_empty_path_return_empty(self):
        pt = swd.PackageTree(product="houdini")
        path = ""
        pkgs = pt.find_by_path(path)
        self.assertEqual(pkgs, [])
        pkgs = pt.find_by_path(path, with_ancestors=False)
        self.assertEqual(pkgs, [])


class FindByNameTest(unittest.TestCase):

    def test_find_root(self):
        pt = swd.PackageTree(product="houdini")
        name = 'houdini 16.5.323'
        result = pt.find_by_name(name)
        self.assertEqual(swd.to_name(result), name)

    def test_find_root_when_limit_1(self):
        pt = swd.PackageTree(product="houdini")
        name = 'houdini 16.5.323'
        result = pt.find_by_name(name, 1)
        self.assertEqual(swd.to_name(result), name)

    def test_find_plugin_level(self):
        pt = swd.PackageTree(product="houdini")
        name = "arnold-houdini 2.0.2.2"
        result = pt.find_by_name(name)
        self.assertEqual(swd.to_name(result), name)

    def test_find_plugin_level_high_limit(self):
        pt = swd.PackageTree(product="houdini")
        name = "arnold-houdini 2.0.2.2"
        result = pt.find_by_name(name, 2)
        self.assertEqual(swd.to_name(result), name)

    def test_dont_find_plugin_level_when_limited(self):
        pt = swd.PackageTree(product="houdini")
        name = "arnold-houdini 2.0.2.2"
        result = pt.find_by_name(name, 1)
        self.assertEqual(result, None)


class SoftwareDataGetAllPathsTest(unittest.TestCase):

    def test_get_all_paths_to_root(self):
        pt = swd.PackageTree(product="houdini")
        keys = {
            'product': 'houdini',
            'major_version': '16',
            'minor_version': '5',
            'release_version': '323',
            'build_version': '',
            'plugin_host_product': '',
            'plugin_host_version': ''
        }
        paths = pt.get_all_paths_to(**keys)
        self.assertTrue(
            'houdini 16.5.323' in paths)
        self.assertEqual(len(paths), 1)

    def test_get_all_paths_to_leaf(self):
        pt = swd.PackageTree(product="houdini")
        keys = {
            'product': 'al-shaders',
            'major_version': '1',
            'minor_version': '0',
            'release_version': '',
            'build_version': '',
            'plugin_host_product': '',
            'plugin_host_version': ''
        }
        paths = pt.get_all_paths_to(**keys)
        self.assertTrue(
            'houdini 16.0.736/arnold-houdini 2.0.1/al-shaders 1.0' in paths)
        self.assertEqual(len(paths), 2)

    def test_get_all_paths_to_nonexistent(self):
        pt = swd.PackageTree(product="houdini")
        keys = {
            'product': 'foo',
            'major_version': '1',
            'minor_version': '0',
            'release_version': '',
            'build_version': '',
            'plugin_host_product': '',
            'plugin_host_version': ''
        }
        paths = pt.get_all_paths_to(**keys)
        self.assertEqual(paths, [])


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
