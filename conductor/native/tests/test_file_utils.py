""" test file_utils
   isort:skip_file
"""
from conductor.lib import file_utils as fu
import unittest


class ReplaceRootTest(unittest.TestCase):
    def test_replace_simple_same_level_root(self):
        p1 = '/a/renders/render_0001_large.exr'
        p2 = '/b/renders/render_0001_large.exr'
        expected = '/b/renders/render_0001_large.exr'
        result = fu.replace_root(p1, p2)
        self.assertEqual(result, expected)

    def test_replace_simple_differing_level_root(self):
        p1 = '/a/renders/render_0001_large.exr'
        p2 = '/b/renders/c/d/render_0001_large.exr'
        expected = '/b/renders/c/d/render_0001_large.exr'
        result = fu.replace_root(p1, p2)
        self.assertEqual(result, expected)

    def test_replace_root_retains_original_filename(self):
        p1 = '/a/renders/render_0001_large.0%4d.exr'
        p2 = '/b/renders/c/d/render_0001_large.0786.exr'
        expected = '/b/renders/c/d/render_0001_large.0%4d.exr'
        result = fu.replace_root(p1, p2)
        self.assertEqual(result, expected)

    def test_replace_root_when_orig_contain_drive_letter(self):
        p1 = 'Z:/a/renders/render_0001_large.exr'
        p2 = '/b/renders/c/d/render_0001_large.exr'
        expected = '/b/renders/c/d/render_0001_large.exr'
        result = fu.replace_root(p1, p2)
        self.assertEqual(result, expected)

    def test_replace_root_when_replacement_contains_drive_letter(self):
        p1 = '/a/renders/render_0001_large.exr'
        p2 = 'C:/b/renders/c/d/render_0001_large.exr'
        expected = 'C:/b/renders/c/d/render_0001_large.exr'
        result = fu.replace_root(p1, p2)
        self.assertEqual(result, expected)

    def test_replace_root_when_both_contain_drive_letter(self):
        p1 = 'Z:/a/renders/render_0001_large.exr'
        p2 = 'C:/b/renders/c/d/render_0001_large.exr'
        expected = 'C:/b/renders/c/d/render_0001_large.exr'
        result = fu.replace_root(p1, p2)
        self.assertEqual(result, expected)

    def test_replace_root_when_orig_contain_unc_ip(self):
        p1 = '//192.168.0.1/renders/render_0001_large.exr'
        p2 = '/Volumes/renders/c/d/render_0001_large.exr'
        expected = '/Volumes/renders/c/d/render_0001_large.exr'
        result = fu.replace_root(p1, p2)
        self.assertEqual(result, expected)

    def test_replace_root_when_replacement_contain_unc_ip(self):
        p1 = '/Volumes/renders/render_0001_large.exr'
        p2 = '//192.168.0.1/renders/c/d/render_0001_large.exr'
        expected = '//192.168.0.1/renders/c/d/render_0001_large.exr'
        result = fu.replace_root(p1, p2)
        self.assertEqual(result, expected)

    def test_replace_root_when_both_contain_unc_ip(self):
        p1 = '//192.168.0.1/renders/render_0001_large.exr'
        p2 = '//192.168.0.2/renders/c/d/render_0001_large.exr'
        expected = '//192.168.0.2/renders/c/d/render_0001_large.exr'
        result = fu.replace_root(p1, p2)
        self.assertEqual(result, expected)

    def test_dont_replace_when_different_roots_but_first_part_the_same(self):
        p1 = '//192.168.0.1/renders/0%4d/render_0001_large.exr'
        p2 = '//192.168.0.1/renders/0023/render_0001_large.exr'
        expected = '//192.168.0.1/renders/0%4d/render_0001_large.exr'
        result = fu.replace_root(p1, p2)
        self.assertEqual(result, expected)

    def test_replace_root_when_everything_different(self):
        p1 = '/Volumes/e/f/render_0001_large.0%4d.exr'
        p2 = '//192.168.0.1/renders/c/d/render_0001_large.0001.exr'
        expected = '//192.168.0.1/renders/c/d/render_0001_large.0%4d.exr'
        result = fu.replace_root(p1, p2)
        self.assertEqual(result, expected)

    def test_replace_root_when_single_root_part_and_different_filename(self):
        p1 = '/Volumes/render_0001_large.0%4d.exr'
        p2 = '//192.168.0.1/render_0001_large.0001.exr'
        expected = '//192.168.0.1/render_0001_large.0%4d.exr'
        result = fu.replace_root(p1, p2)
        self.assertEqual(result, expected)


if __name__ == "__main__":
    unittest.main()
