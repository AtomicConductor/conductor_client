""" test gpath

   isort:skip_file
"""
from conductor.native.lib.gpath import Path
import os
import sys
import mock
import unittest


sys.modules["glob"] = __import__("conductor.native.lib.mocks.glob", fromlist=["dummy"])


NATIVE_MODULE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if NATIVE_MODULE not in sys.path:
    sys.path.insert(0, NATIVE_MODULE)

sys.modules["glob"] = __import__("conductor.native.lib.mocks.glob", fromlist=["dummy"])


class BadInputTest(unittest.TestCase):
    def test_badly_formed_drive_letter(self):
        with self.assertRaises(ValueError):
            self.p = Path("CZ:\\a\\b\\c")

    def test_empty_input(self):
        with self.assertRaises(ValueError):
            self.p = Path("")

    def test_many_colons_input(self):
        with self.assertRaises(ValueError):
            self.p = Path("A:a\\b:c")

    def test_relative_input_literal(self):
        with self.assertRaises(ValueError):
            self.p = Path("a/b/c")

    def test_relative_input_var(self):
        env = {"DEPT": "texturing"}
        with mock.patch.dict("os.environ", env):
            with self.assertRaises(ValueError):
                self.p = Path("$DEPT/a/b/c")


class RootPath(unittest.TestCase):
    def test_root_path(self):
        self.p = Path("/")
        self.assertEqual(self.p.posix_path(), "/")
        self.assertEqual(self.p.windows_path(), "\\")

    def test_drive_letter_root_path(self):
        self.p = Path("C:\\")
        self.assertEqual(self.p.posix_path(), "C:/")
        self.assertEqual(self.p.windows_path(), "C:\\")


class SpecifyDriveLetterUse(unittest.TestCase):
    def test_remove_from_path(self):
        self.p = Path("C:\\a\\b\\c")
        self.assertEqual(self.p.posix_path(with_drive=False), "/a/b/c")
        self.assertEqual(self.p.windows_path(with_drive=False), "\\a\\b\\c")

    def test_remove_from_root_path(self):
        self.p = Path("C:\\")
        self.assertEqual(self.p.posix_path(with_drive=False), "/")
        self.assertEqual(self.p.windows_path(with_drive=False), "\\")


class AbsPosixPathTest(unittest.TestCase):
    def setUp(self):
        self.p = Path("/a/b/c")

    def test_posix_path_out(self):
        self.assertEqual(self.p.posix_path(), "/a/b/c")

    def test_win_path_out(self):
        self.assertEqual(self.p.windows_path(), "\\a\\b\\c")


class AbsWindowsPathTest(unittest.TestCase):
    def setUp(self):
        self.p = Path("C:\\a\\b\\c")

    def test_posix_path_out(self):
        self.assertEqual(self.p.posix_path(), "C:/a/b/c")

    def test_win_path_out(self):
        self.assertEqual(self.p.windows_path(), "C:\\a\\b\\c")

    # consider just testing on both platforms
    def test_os_path_out(self):
        with mock.patch("os.name", "posix"):
            self.assertEqual(self.p.os_path(), "C:/a/b/c")
        with mock.patch("os.name", "nt"):
            self.assertEqual(self.p.os_path(), "C:\\a\\b\\c")


class WindowsMixedPathTest(unittest.TestCase):
    def test_abs_in_posix_path_out(self):
        self.p = Path("\\a\\b\\c/d/e")
        self.assertEqual(self.p.posix_path(), "/a/b/c/d/e")

    def test_abs_in_windows_path_out(self):
        self.p = Path("\\a\\b\\c/d/e")
        self.assertEqual(self.p.windows_path(), "\\a\\b\\c\\d\\e")

    def test_letter_abs_in_posix_path_out(self):
        self.p = Path("C:\\a\\b\\c/d/e")
        self.assertEqual(self.p.posix_path(), "C:/a/b/c/d/e")

    def test_letter_abs_in_windows_path_out(self):
        self.p = Path("C:\\a\\b\\c/d/e")
        self.assertEqual(self.p.windows_path(), "C:\\a\\b\\c\\d\\e")


class MiscPathTest(unittest.TestCase):
    def test_many_to_single_backslashes_windows_path_out(self):
        self.p = Path("C:\\\\a\\b///c")
        self.assertEqual(self.p.windows_path(), "C:\\a\\b\\c")


class PathExpansionTest(unittest.TestCase):
    def setUp(self):
        self.env = {
            "HOME": "/users/joebloggs",
            "SHOT": "/metropolis/shot01",
            "DEPT": "texturing",
        }

    def test_posix_tilde_input(self):
        with mock.patch.dict("os.environ", self.env):
            self.p = Path("~/a/b/c")
            self.assertEqual(self.p.posix_path(), "/users/joebloggs/a/b/c")

    def test_posix_var_input(self):
        with mock.patch.dict("os.environ", self.env):
            self.p = Path("$SHOT/a/b/c")
            self.assertEqual(self.p.posix_path(), "/metropolis/shot01/a/b/c")

    def test_posix_two_var_input(self):
        with mock.patch.dict("os.environ", self.env):
            self.p = Path("$SHOT/a/b/$DEPT/c")
            self.assertEqual(self.p.posix_path(), "/metropolis/shot01/a/b/texturing/c")

    def test_windows_var_input(self):
        with mock.patch.dict("os.environ", self.env):
            self.p = Path("$HOME\\a\\b\\c")
            self.assertEqual(self.p.windows_path(), "\\users\\joebloggs\\a\\b\\c")
            self.assertEqual(self.p.posix_path(), "/users/joebloggs/a/b/c")


class PathContextExpansionTest(unittest.TestCase):
    def setUp(self):

        self.env = {
            "HOME": "/users/joebloggs",
            "SHOT": "/metropolis/shot01",
            "DEPT": "texturing",
        }

        self.context = {
            "HOME": "/users/janedoe",
            "FOO": "fooval",
            "BAR_FLY1_": "bar_fly1_val",
            "ROOT_DIR": "/some/root",
        }

    def test_path_replaces_context(self):
        self.p = Path("$ROOT_DIR/thefile.jpg", context=self.context)
        self.assertEqual(self.p.posix_path(), "/some/root/thefile.jpg")

    def test_path_replaces_multiple_context(self):
        self.p = Path("$ROOT_DIR/$BAR_FLY1_/thefile.jpg", context=self.context)
        self.assertEqual(self.p.posix_path(), "/some/root/bar_fly1_val/thefile.jpg")

    def test_path_context_overrides_env(self):
        self.p = Path("$HOME/thefile.jpg", context=self.context)
        self.assertEqual(self.p.posix_path(), "/users/janedoe/thefile.jpg")

    def test_path_leave_unknown_variable_in_tact(self):
        self.p = Path("$ROOT_DIR/$BAR_FLY1_/$FOO/thefile.$F.jpg", context=self.context)
        self.assertEqual(
            self.p.posix_path(), "/some/root/bar_fly1_val/fooval/thefile.$F.jpg"
        )

    def test_relative_path_var_fails(self):
        with self.assertRaises(ValueError):
            self.p = Path("$FOO/a/b/c", context=self.context)


class PathLengthTest(unittest.TestCase):
    def test_len_with_drive_letter(self):
        self.p = Path("C:\\aaa\\bbb/c")
        self.assertEqual(len(self.p), 12)

    def test_len_with_no_drive_letter(self):
        self.p = Path("\\aaa\\bbb/c")
        self.assertEqual(len(self.p), 10)

    def test_depth_with_drive_letter(self):
        self.p = Path("C:\\aaa\\bbb/c")
        self.assertEqual(self.p.depth, 3)

    def test_depth_with_no_drive_letter(self):
        self.p = Path("\\aaa\\bbb/c")
        self.assertEqual(self.p.depth, 3)


class PathCollapseDotsTest(unittest.TestCase):
    def test_path_collapses_single_dot(self):
        p = Path("/a/b/./c")
        self.assertEqual(p.posix_path(), "/a/b/c")

    def test_path_collapses_double_dot(self):
        p = Path("/a/b/../c")
        self.assertEqual(p.posix_path(), "/a/c")

    def test_path_collapses_many_single_dots(self):
        p = Path("/a/b/./c/././d")
        self.assertEqual(p.posix_path(), "/a/b/c/d")

    def test_path_collapses_many_consecutive_double_dots(self):
        p = Path("/a/b/c/../../d")
        self.assertEqual(p.posix_path(), "/a/d")

    def test_path_collapses_many_non_consecutive_double_dots(self):
        p = Path("/a/b/c/../../d/../e/f/../g")
        self.assertEqual(p.posix_path(), "/a/e/g")

    def test_path_collapses_many_non_consecutive_mixed_dots(self):
        p = Path("/a/./b/c/../.././d/../././e/f/../g/./")
        self.assertEqual(p.posix_path(), "/a/e/g")
        self.assertEqual(p.depth, 3)

    def test_path_collapses_to_root(self):
        p = Path("/a/b/../../")
        self.assertEqual(p.posix_path(), "/")
        self.assertEqual(p.depth, 0)

    def test_raise_when_collapse_too_many_dots(self):
        with self.assertRaises(ValueError):
            Path("/a/b/../../../")


if __name__ == "__main__":
    unittest.main()
