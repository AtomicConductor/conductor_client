""" test file_utils

   isort:skip_file
"""
import os

import unittest
import conductor.lib.file_utils as futil
import logging


fixtures_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), "fixtures")


class ProcessDependenciesTest(unittest.TestCase):
    def setUp(self):
        logger = logging.getLogger("conductor")
        logger.setLevel("DEBUG")

    def test_regular_filename(self):
        paths = ["/path/to/filename.txt"]
        deps = futil.process_dependencies(paths)
        self.assertIn("/path/to/filename.txt", deps)

    def test_it_encodes_unicode_chars_in_error_message(self):
        # make sure logging is triggered as it should also encode unicode.
        paths = [u"/path/to/\u0123/name.txt"]
        deps = futil.process_dependencies(paths)
        self.assertIn(u"/path/to/\u0123/name.txt", deps)
        self.assertIn("/path/to/\xc4\xa3/name.txt", deps[u"/path/to/\u0123/name.txt"])

    def test_catches_existing_unicode_files(self):
        unicode_dir = unicode(os.path.join(fixtures_dir, "unicode_files"), "utf8")
        filenames = os.listdir(unicode_dir)
        paths = [
            os.path.join(unicode_dir, f) for f in filenames if not f.startswith(".")
        ]
        deps = futil.process_dependencies(paths)
        for key in deps:
            self.assertIn("Unicode filenames are not supported", deps[key])


if __name__ == "__main__":
    unittest.main()
