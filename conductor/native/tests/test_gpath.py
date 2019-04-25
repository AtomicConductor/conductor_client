import os
import sys
import mock
import unittest


sys.modules['glob'] = __import__(
    'conductor.native.lib.mocks.glob', fromlist=['dummy'])

from conductor.native.lib.gpath import Path, GPathError


NATIVE_MODULE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if NATIVE_MODULE not in sys.path:
    sys.path.insert(0, NATIVE_MODULE)

sys.modules['glob'] = __import__(
    'conductor.native.lib.mocks.glob', fromlist=['dummy'])


class BadInputTest(unittest.TestCase):

    def test_badly_formed_drive_letter(self):
        with self.assertRaises(GPathError):
            self.p = Path("CZ:\\a\\b\\c")

    def test_empty_input(self):
        with self.assertRaises(GPathError):
            self.p = Path("")

    def test_many_colons_input(self):
        with self.assertRaises(GPathError):
            self.p = Path("A:a\\b:c")

    def test_relative_input_literal(self):
        with self.assertRaises(GPathError):
            self.p = Path("a/b/c")

    def test_relative_input_var(self):
        env =  {"DEPT": "texturing"}
        with mock.patch.dict('os.environ', env):
            with self.assertRaises(GPathError):
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

    def test_win_path_out_remove_drive_letter(self):
        self.assertEqual(self.p.windows_path(False), "\\a\\b\\c")


    # consider just testing on both platforms
    def test_os_path_out(self):
        with mock.patch('os.name', 'posix'):
            self.assertEqual(self.p.os_path(), "C:/a/b/c")
        with mock.patch('os.name', 'nt'):
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

    def test_double_to_single_backslashes_windows_path_out(self):
        self.p = Path("C:\\\\a\\b//c")
        self.assertEqual(self.p.windows_path(), "C:\\a\\b\\c")


class PathExpansionTest(unittest.TestCase):
    
    def setUp(self):
        self.env =  {
        "HOME": "/users/joebloggs",
        "SHOT": "/metropolis/shot01",
        "DEPT": "texturing"}

    def test_posix_tilde_input(self):
        with mock.patch.dict('os.environ', self.env):
            self.p = Path("~/a/b/c")
            self.assertEqual(self.p.posix_path(), "/users/joebloggs/a/b/c")

    def test_posix_var_input(self):
        with mock.patch.dict('os.environ', self.env):
            self.p = Path("$SHOT/a/b/c")
            self.assertEqual(self.p.posix_path(), "/metropolis/shot01/a/b/c")
    
    def test_posix_var_input(self):
        with mock.patch.dict('os.environ', self.env):
            self.p = Path("$SHOT/a/b/$DEPT/c")
            self.assertEqual(self.p.posix_path(), "/metropolis/shot01/a/b/texturing/c")

    def test_windows_var_input(self):
        with mock.patch.dict('os.environ', self.env):
            self.p = Path("$HOME\\a\\b\\c")
            self.assertEqual(self.p.windows_path(), "\\users\\joebloggs\\a\\b\\c")
            self.assertEqual(self.p.posix_path(), "/users/joebloggs/a/b/c")
 

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
        self.assertEqual( self.p.depth, 3)







if __name__ == '__main__':
    unittest.main()
