import sys
import os
import unittest
import mock

sys.modules['glob'] = __import__(
    'conductor.native.lib.mocks.glob', fromlist=['dummy'])

import glob

from conductor.native.lib.gpath_list import PathList
from conductor.native.lib.sequence import Sequence
from conductor.native.lib.gpath import Path


NATIVE_MODULE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if NATIVE_MODULE not in sys.path:
    sys.path.insert(0, NATIVE_MODULE)


class PathListTest(unittest.TestCase):
    
    def setUp(self):
        self.env =  {
        "HOME": "/users/joebloggs",
        "SHOT": "/metropolis/shot01",
        "DEPT": "texturing"}


    def test_init_empty(self):
        d = PathList()
        self.assertEqual(list(d), [])

    def test_adds_paths(self):
        d = PathList()
        d.add(Path("/a/file1"), Path("/a/file2"))
        self.assertEqual(len(d), 2)

    def test_adds_strings(self):
        d = PathList()
        d.add("/a/file1", "/a/file2")
        self.assertEqual(len(d), 2)

    def test_adds_mix(self):
        d = PathList()
        d.add("/a/file1", "/a/file2", Path("/a/file3"))
        self.assertEqual(len(d), 3)

    # just want to make sure expansion works here
    # even though it's tested in gpath_test
    def test_expand_tilde(self):
        with mock.patch.dict('os.environ', self.env):
            d = PathList()
            d.add("~/file1", "~/file2")

            self.assertIn("/users/joebloggs/file1", d)

    def test_expand_envvar(self):
        with mock.patch.dict('os.environ', self.env):
            d = PathList()
            d.add("$SHOT/file1", "$HOME/file2")
            self.assertIn("/metropolis/shot01/file1", d)
            self.assertIn("/users/joebloggs/file2", d)

    def test_dedup_same_paths(self):
        d = PathList()
        d.add(Path("/file1"), Path("/file2"), Path("/file2"))
        self.assertEqual(len(d), 2)
        self.assertIn(Path("/file1"), d)
        self.assertIn(Path("/file2"), d)

    def test_dedup_same_strings(self):
        d = PathList()
        d.add("/file1", "/file2", "/file2")
        self.assertEqual(len(d), 2)
        self.assertIn("/file1", d)
        self.assertIn("/file2", d)

    def test_dedup_contained_file(self):
        d = PathList()
        d.add(
            "/dir1/",
            "/dir1/file1",
            "/dir2/file1",
            "/dir3/file2")
        self.assertEqual(len(d), 3)

    def test_dedup_dirtied_on_add(self):
        d = PathList()
        d.add("/file1")
        self.assertFalse(d._clean)

    def test_dedup_cleaned_on_access_iter(self):
        d = PathList()
        d.add("/file1")
        ls = list(d)
        self.assertTrue(d._clean)

    def test_dedup_cleaned_on_access_len(self):
        d = PathList()
        d.add("/file1")
        ls = len(d)
        self.assertTrue(d._clean)

    def test_dedup_cleaned_on_access_next(self):
        d = PathList()
        d.add("/file1", "/file2", "/file3")
        n = next(d)
        self.assertTrue(d._clean)

    def test_next(self):
        d = PathList()
        d.add("/file1", "/file2", "/file3")
        self.assertEqual(next(d), Path("/file1"))
        self.assertEqual(next(d), Path("/file2"))

    def test_next_fails_after_last(self):
        d = PathList()
        d.add("/file1", "/file2", "/file3")
        next(d)
        next(d)
        next(d)
        with self.assertRaises(StopIteration):
            next(d)

    def test_next_reset_after_add(self):
        d = PathList()
        d.add("/file1", "/file2", "/file3")
        next(d)
        next(d)
        d.add("/file4")
        self.assertEqual(next(d), Path("/file1"))

    def test_common_path_when_common_prefix_in_filename(self):
        d = PathList()
        files = ["/users/joebloggs/tmp/dissention/perfect",
                 "/users/joebloggs/tmp/disagreement/crimson",
                 "/users/joebloggs/tmp/diatribe/belew"]
        d.add(*files)
        self.assertEqual(d.common_path(), Path("/users/joebloggs/tmp"))

    def test_common_path(self):
        d = PathList()
        files = ["/users/joebloggs/tmp/foobar/test",
                 "/users/joebloggs/tmp/baz/fripp",
                 "/users/joebloggs/tmp/elephant/corner"]
        d.add(*files)
        self.assertEqual(d.common_path(), Path("/users/joebloggs/tmp"))

    def test_common_path_when_one_path_is_the_common_path(self):
        d = PathList()
        files = [
            "/users/joebloggs/tmp",
            "/users/joebloggs/tmp/bolly/operation",
            "/users/joebloggs/tmp/stay/go"]
        d.add(*files)
        self.assertEqual(d.common_path(), Path("/users/joebloggs/tmp"))

    def test_common_path_when_lowest_path_is_the_common_path(self):
        d = PathList()
        files = [
            "/users/joebloggs/tmp/foo.txt",
            "/users/joebloggs/tmp/modelman.jpg",
            "/users/joebloggs/tmp/ration.cpp",
            "/users/joebloggs/tmp/bill.project"]
        d.add(*files)
        self.assertEqual(d.common_path(), Path("/users/joebloggs/tmp"))

    def test_common_path_drive_letter(self):
        d = PathList()
        files = [
            "C://users/joebloggs/hello/foo.txt",
            "C://users/joebloggs/tmp/modelman.jpg",
            "C://users/joebloggs/tmp/ration.cpp",
            "C://users/joebloggs/tmp/bill.project"]
        d.add(*files)
        self.assertEqual(d.common_path(), Path("C://users/joebloggs"))

    # This is not right. There is no common path if drive letters 
    # are involved. Need to revisit, and hope that in the
    # meantime  no one is dumb enough to render to tewo different 
    # filesystems in the same render job.  
    def test_common_different_drive_letter(self):
        d = PathList()
        files = [
            "D://users/joebloggs/tmp/foo.txt",
            "D://users/joebloggs/tmp/modelman.jpg",
            "C://users/joebloggs/tmp/ration.cpp",
            "C://users/joebloggs/tmp/bill.project"]
        d.add(*files)
        self.assertEqual(d.common_path(), Path("/"))


    def test_common_path_when_single_path(self):
        d = PathList()
        files = ["/users/joebloggs/tmp/foo.txt"]
        d.add(*files)
        self.assertEqual(d.common_path(), Path("/users/joebloggs/tmp/foo.txt"))

    def test_common_path_when_duplicate_entries_of_single_path(self):
        d = PathList()
        files = [
            "/users/joebloggs/tmp/foo.txt",
            "/users/joebloggs/tmp/foo.txt"]
        d.add(*files)
        self.assertEqual(d.common_path(), Path("/users/joebloggs/tmp/foo.txt"))

    def test_common_path_is_none_when_no_entries(self):
        d = PathList()
        self.assertIsNone(d.common_path())

    def test_common_path_is_slash_when_root(self):
        d = PathList()
        files = [
            "/users/joebloggs/tmp/foo.txt",
            "/dev/joebloggs/tmp/foo.txt"]
        d.add(*files)
        self.assertEqual(d.common_path(), Path("/"))

    def test_glob_when_files_match_with_asterisk(self):
        glob.populate(Sequence.create("1-20").expand("/some/file.####.exr"))
        d = PathList()
        file = "/some/file.*.exr"
        d.add(file)
        d.glob()
        self.assertEqual(len(d), 20)


    def test_glob_when_files_match_with_range(self):
        glob.populate(Sequence.create("1-20").expand("/some/file.####.exr"))
        d = PathList()
        file = "/some/file.000[0-9].exr"
        d.add(file)
        d.glob()
        self.assertEqual(len(d), 9)

    def test_glob_when_files_match_with_questoion_mark(self):
        glob.populate(Sequence.create("1-20").expand("/some/file.####.exr"))
        d = PathList()
        file = "/some/file.00?0.exr"
        d.add(file)
        d.glob()
        self.assertEqual(len(d), 2)

    def test_glob_dedups_when_many_files_match(self):
        glob.populate(Sequence.create("1-20").expand("/some/file.####.exr"))
        d = PathList()
        files = ["/some/file.*.exr", "/some/*.exr"]
        d.add(*files)
        d.glob()
        self.assertEqual(len(d), 20)

    def test_glob_when_files_dont_match(self):
        glob.populate(Sequence.create("1-20").expand("/other/file.####.exr"))
        d = PathList()
        file = "/some/file.*.exr"
        d.add(file)
        d.glob()
        self.assertEqual(len(d), 0)

    def test_unpacking(self):
        d = PathList()
        d.add(Path("/a/file1"), Path("/a/file2"))
        a, b = d
        self.assertEqual(type(a), Path)



    def test_glob_leaves_non_existent_unglobbable_entries_untouched(self):
        glob.populate(Sequence.create("1-3").expand("/some/file.####.exr"))
        d = PathList()
        d.add("/some/file.*.exr", "/other/file1.exr",  "/other/file2.exr")
        d.glob()
        self.assertEqual(len(d), 5)

 
    def test_unpacking(self):
        d = PathList()
        d.add(Path("/a/file1"), Path("/a/file2"))
        a, b = d
        self.assertEqual(type(a), Path)


if __name__ == '__main__':
    unittest.main()
