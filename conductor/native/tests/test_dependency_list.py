"""Test DependencyList. Assume run on posix filesystem"""

import os
import sys
import unittest
import mock

from conductor.native.lib.dependency_list import DependencyList

NATIVE_MODULE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if NATIVE_MODULE not in sys.path:
    sys.path.insert(0, NATIVE_MODULE)


@mock.patch.dict(os.environ, {
    "HOME": "/users/joebloggs",
    "SHOT": "/metropolis/shot01"
})
class DepListTest(unittest.TestCase):

    def test_init_empty(self):
        d = DependencyList()
        self.assertEqual(list(d), [])

    def test_adds_files(self):
        d = DependencyList()
        d.add("file1", "file2", must_exist=False)
        self.assertEqual(len(d), 2)

    def test_expand_tilde(self):
        d = DependencyList()
        d.add("~/file1", "~/file2", must_exist=False)
        self.assertIn("/users/joebloggs/file1", d)

    def test_expand_envvar(self):
        d = DependencyList()
        d.add("$SHOT/file1", "$HOME/file2", must_exist=False)
        self.assertIn("/metropolis/shot01/file1", d)
        self.assertIn("/users/joebloggs/file2", d)

    def test_dedup_same_filenames(self):
        d = DependencyList()
        d.add("/file1", "/file2", "/file2", must_exist=False)
        self.assertEqual(len(d), 2)
        self.assertIn("/file1", d)
        self.assertIn("/file2", d)

    def test_dedup_contained_file(self):
        d = DependencyList()
        d.add(
            "/dir1/",
            "/dir1/file1",
            "/dir2/file1",
            "file2",
            must_exist=False)
        self.assertEqual(len(d), 3)

    def test_dedup_dirtied_on_add(self):
        d = DependencyList()
        d.add("/file1", must_exist=False)
        self.assertFalse(d._clean)

    def test_dedup_cleaned_on_access_iter(self):
        d = DependencyList()
        d.add("/file1", must_exist=False)
        ls = list(d)
        self.assertTrue(d._clean)

    def test_dedup_cleaned_on_access_len(self):
        d = DependencyList()
        d.add("/file1", must_exist=False)
        ls = len(d)
        self.assertTrue(d._clean)

    def test_dedup_cleaned_on_access_next(self):
        d = DependencyList()
        d.add("/file1", "/file2", "/file3", must_exist=False)
        n = next(d)
        self.assertTrue(d._clean)

    def test_next(self):
        d = DependencyList()
        d.add("/file1", "/file2", "/file3", must_exist=False)
        self.assertEqual(next(d), "/file1")
        self.assertEqual(next(d), "/file2")

    def test_next_fails_after_last(self):
        d = DependencyList()
        d.add("/file1", "/file2", "/file3", must_exist=False)
        next(d)
        next(d)
        next(d)
        with self.assertRaises(StopIteration):
            next(d)

    def test_next_reset_after_add(self):
        d = DependencyList()
        d.add("/file1", "/file2", "/file3", must_exist=False)
        next(d)
        next(d)
        d.add("/file4")
        self.assertEqual(next(d), "/file1")

    def test_common_path_when_common_prefix_in_filename(self):
        d = DependencyList()
        files = ["/users/joebloggs/tmp/dissention/perfect",
                 "/users/joebloggs/tmp/disagreement/crimson",
                 "/users/joebloggs/tmp/diatribe/belew"]
        d.add(*files, must_exist=False)
        self.assertEqual(d.common_path(), "/users/joebloggs/tmp")

    def test_common_path(self):
        d = DependencyList()
        files = ["/users/joebloggs/tmp/foobar/test",
                 "/users/joebloggs/tmp/baz/fripp",
                 "/users/joebloggs/tmp/elephant/corner"]
        d.add(*files, must_exist=False)
        self.assertEqual(d.common_path(), "/users/joebloggs/tmp")

    def test_common_path_when_one_path_is_the_common_path(self):
        d = DependencyList()
        files = [
            "/users/joebloggs/tmp",
            "/users/joebloggs/tmp/bolly/operation",
            "/users/joebloggs/tmp/stay/go"]
        d.add(*files, must_exist=False)
        self.assertEqual(d.common_path(), "/users/joebloggs/tmp")

    def test_common_path_when_lowest_path_is_the_common_path(self):
        d = DependencyList()
        files = [
            "/users/joebloggs/tmp/foo.txt",
            "/users/joebloggs/tmp/modelman.jpg",
            "/users/joebloggs/tmp/ration.cpp",
            "/users/joebloggs/tmp/bill.project"]
        d.add(*files, must_exist=False)
        self.assertEqual(d.common_path(), "/users/joebloggs/tmp")

    def test_common_path_when_single_path(self):
        d = DependencyList()
        files = ["/users/joebloggs/tmp/foo.txt"]
        d.add(*files, must_exist=False)
        self.assertEqual(d.common_path(), "/users/joebloggs/tmp/foo.txt")

    def test_common_path_when_duplicate_entries_of_single_path(self):
        d = DependencyList()
        files = [
            "/users/joebloggs/tmp/foo.txt",
            "/users/joebloggs/tmp/foo.txt"]
        d.add(*files, must_exist=False)
        self.assertEqual(d.common_path(), "/users/joebloggs/tmp/foo.txt")

    def test_common_path_is_none_when_no_entries(self):
        d = DependencyList()
        self.assertIsNone(d.common_path())

    def test_common_path_is_slash_when_root(self):
        d = DependencyList()
        files = [
            "/users/joebloggs/tmp/foo.txt",
            "/dev/joebloggs/tmp/foo.txt"]
        d.add(*files, must_exist=False)
        self.assertEqual(d.common_path(), "/")


if __name__ == '__main__':
    unittest.main()
