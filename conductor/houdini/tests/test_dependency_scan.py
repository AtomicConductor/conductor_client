"""This module tests dependency scanning."""


import os
import json

import sys
import unittest
from unittest import TestCase

from conductor.houdini.lib.sequence import Sequence


HDA_MODULE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if HDA_MODULE not in sys.path:
    sys.path.insert(0, HDA_MODULE)

# use a mocked hou and glob
sys.modules['hou'] = __import__(
    'conductor.houdini.lib.mocks.hou', fromlist=['dummy'])

sys.modules['glob'] = __import__(
    'conductor.houdini.lib.mocks.glob', fromlist=['dummy'])


# import hou and dependency_scan after mocking houdini
import hou
import glob

from conductor.houdini.hda import dependency_scan

json_file = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "lib",
    "fixtures",
    "dependency_scan.json")

with open(json_file, 'r') as content:
    data = json.loads(content.read())
    hou.initialize(data)
    glob.initialize(data)


class DependencyScanTest(TestCase):

    def setUp(self):
        self.seq = Sequence.create("1-10")
        self.node = hou.node("job1")

    def test_include_extra_uploads_in_job(self):
        result = dependency_scan.fetch(self.node, self.seq)
        self.assertIn(self.node.parm("upload_1").eval(), result)

    def test_exclude_extra_uploads_in_other_jobs(self):
        result = dependency_scan.fetch(self.node, self.seq)
        self.assertNotIn(hou.node("job2").parm("upload_1").eval(), result)

    def test_include_simple_file_if_exists(self):
        result = dependency_scan.fetch(self.node, self.seq)
        fn = hou.node("shader1").parm("texture_file").eval()
        self.assertIn(fn, result)

    def test_exclude_simple_file_if_not_exists(self):
        result = dependency_scan.fetch(self.node, self.seq)
        fn = hou.node("shader2").parm("texture_file").eval()
        self.assertNotIn(fn, result)

    def test_include_sequence_if_exists(self):
        result = [
            f for f in dependency_scan.fetch(
                self.node,
                self.seq) if f.startswith("/path/to/shader3")]

        self.assertIn("/path/to/shader3/tex.0010.jpg", result)
        self.assertEqual(len(result), 10)

    def test_include_parts_of_sequence_that_exist(self):
        seq = Sequence.create("96-105")
        result = [
            f for f in dependency_scan.fetch(
                self.node, seq) if f.startswith("/path/to/shader3")]

        self.assertIn("/path/to/shader3/tex.0097.jpg", result)
        self.assertEqual(len(result), 5)

    def test_remove_file_if_directory_exists(self):
        result = dependency_scan.fetch(self.node, self.seq)
        self.assertIn("/path/to/shader4", result)
        self.assertNotIn("/path/to/shader4/tex.0097.jpg", result)

    def test_dont_remove_file_if_shorter_name_file_exists(self):
        """This is to ensure _remove_redundant_entries works."""
        result = dependency_scan.fetch(self.node, self.seq)
        self.assertIn("/path/to/shader5/tex.0097.jpg.BAK", result)
        self.assertIn("/path/to/shader5/tex.0097.jpg", result)
        self.assertIn("/path/to/shader5/tex.0097.jpg.BAK.final", result)

    def test_find_files_with_udims(self):
        result = [
            f for f in dependency_scan.fetch(
                self.node, self.seq) if f.startswith("/path/to/shader6")]
        self.assertIn("/path/to/shader6/tex_01_03.0010.jpg", result)
        self.assertEqual(len(result), 90)

    def test_find_sequence_with_us_and_vs(self):
        result = [
            f for f in dependency_scan.fetch(
                self.node,
                self.seq) if f.startswith("/path/to/shader6")]
        self.assertIn("/path/to/shader6/tex_01_03.0010.jpg", result)
        self.assertEqual(len(result), 90)

    def test_dont_find_files_outside_sequence_with_Us_and_Vs(self):
        result = [
            f for f in dependency_scan.fetch(
                self.node,
                self.seq) if f.startswith("/path/to/shader6")]
        self.assertNotIn("/path/to/shader6/tex_01_03.0011.jpg", result)


def suite():
    """Convenient way to run subset of tests.

    To run one test, use the second addTest statement and
    enter the name of test to run
    """
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(DependencyScanTest))
    # suite.addTest(DependencyScanTest(
    #    "test_dont_find_files_outside_sequence_with_Us_and_Vs"))
    return suite


if __name__ == '__main__':
    # unittest.main()
    runner = unittest.TextTestRunner()
    runner.run(suite())
