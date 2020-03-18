""" test file_utils

   isort:skip_file
"""

import unittest
import conductor.lib.file_utils as futil
import logging


class ProcessDependenciesTest(unittest.TestCase):
    def test_regular_filename(self):
        paths = ["/path/to/filename.txt"]
        deps = futil.process_dependencies(paths)
        self.assertTrue("/path/to/filename.txt" in deps)

    def test_it_encodes_unicode_chars_in_error_message(self):
        # make sure logging is triggered as it should also encode unicode.
        logger = logging.getLogger("conductor")
        logger.setLevel("DEBUG")

        paths = [u"/path/to/\u0123/name.txt"]
        deps = futil.process_dependencies(paths)
        self.assertTrue(u"/path/to/\u0123/name.txt" in deps)
        self.assertTrue(
            "/path/to/\xc4\xa3/name.txt" in deps[u"/path/to/\u0123/name.txt"]
        )


if __name__ == "__main__":
    unittest.main()
