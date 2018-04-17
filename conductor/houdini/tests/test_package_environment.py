import os
import sys
import unittest

from conductor.houdini.lib.package_environment import PackageEnvironment

HDA_MODULE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if HDA_MODULE not in sys.path:
    sys.path.insert(0, HDA_MODULE)


class InitEnvTest(unittest.TestCase):

    def test_init_empty_env(self):
        p = PackageEnvironment({})
        self.assertEqual(dict(p), {})

    def test_init_copy_env(self):
        orig = {"a": 1}
        p = PackageEnvironment(orig)
        self.assertIsNot(dict(p), orig)

    def test_extend_when_empty(self):
        p = PackageEnvironment()
        package = {"environment": [
            {"name": "VAR1", "value": "a", "merge_policy": "append"}
        ]}
        p.extend(package)
        self.assertEqual(p["VAR1"], "a")

    def test_extend_append(self):
        p = PackageEnvironment({"VAR1": "foo"})
        package = {"environment": [
            {"name": "VAR1", "value": "bar", "merge_policy": "append"}
        ]}
        p.extend(package)
        self.assertEqual(p["VAR1"], "foo:bar")

    def test_extend_append_many(self):
        p = PackageEnvironment({"VAR1": "foo"})
        package = {"environment": [
            {"name": "VAR1", "value": "bar", "merge_policy": "append"},
            {"name": "VAR1", "value": "baz", "merge_policy": "append"}
        ]}
        p.extend(package)
        self.assertEqual(p["VAR1"], "foo:bar:baz")

    def test_extend_exclusive_when_empty(self):
        p = PackageEnvironment()
        package = {"environment": [
            {"name": "VAR1", "value": "foo", "merge_policy": "exclusive"}
        ]}
        p.extend(package)
        self.assertEqual(p["VAR1"], "foo")

    def test_extend_exclusive_noop_when_equal(self):
        p = PackageEnvironment({"VAR1": "foo"})
        package = {"environment": [
            {"name": "VAR1", "value": "foo", "merge_policy": "exclusive"}
        ]}
        p.extend(package)
        self.assertEqual(p["VAR1"], "foo")

    def test_extend_exclusive_fail_when_different(self):
        p = PackageEnvironment({"VAR1": "foo"})
        package = {"environment": [
            {"name": "VAR1", "value": "bar", "merge_policy": "exclusive"}
        ]}
        with self.assertRaises(ValueError):
            p.extend(package)

    def test_fail_when_invalid_merge_policy(self):
        p = PackageEnvironment()
        package = {"environment": [
            {"name": "VAR1", "value": "bar", "merge_policy": "foo"}
        ]}
        with self.assertRaises(ValueError):
            p.extend(package)

    def test_many(self):
        p = PackageEnvironment({"VAR1": "foo", "VAR2": "bar"})
        package = {"environment": [
            {"name": "VAR2", "value": "gob", "merge_policy": "append"},
            {"name": "VAR3", "value": "baz", "merge_policy": "exclusive"},
            {"name": "VAR4", "value": "tik", "merge_policy": "append"}
        ]}
        p.extend(package)
        self.assertEqual(p["VAR1"], "foo")
        self.assertEqual(p["VAR2"], "bar:gob")
        self.assertEqual(p["VAR3"], "baz")
        self.assertEqual(p["VAR4"], "tik")

    def test_cast_to_dict(self):
        d = {"VAR1": "foo", "VAR2": "bar"}
        p = PackageEnvironment(d)
        self.assertEqual(dict(p), d)


if __name__ == '__main__':
    unittest.main()
