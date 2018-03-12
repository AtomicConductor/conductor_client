import unittest
import sys
import os

HDA_MODULE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if HDA_MODULE not in sys.path:
    sys.path.insert(0, HDA_MODULE)

import conductor.houdini.lib.progressions as prog


class ProgressionsTest(unittest.TestCase):

    def test_empty(self):
        result = prog.create([])
        self.assertEqual(result, [])

    def test_single(self):
        result = prog.create([3])
        self.assertEqual(result, [[3]])

    def test_two(self):
        result = prog.create([3, 7])
        self.assertEqual(result, [[3], [7]])

    def test_progression_at_start(self):
        result = prog.create([3, 5, 7, 10, 15])
        self.assertEqual(result, [[3, 5, 7], [10], [15]])

    def test_progression_at_end(self):
        result = prog.create([3, 5, 8, 10, 12])
        self.assertEqual(result, [[3], [5], [8, 10, 12]])

    def test_order(self):
        numbers = [3, 5, 8, 10, 12]
        numbers.reverse()
        result = prog.create(numbers)
        self.assertEqual(result, [[3], [5], [8, 10, 12]])

    def test_from_range(self):
        result = prog.create(xrange(2, 97, 3))
        self.assertEqual(len(result), 1)
        self.assertEqual(len(result[0]), 32)

    def test_max_size_one(self):
        result = prog.create([2, 4, 6, 8, 10], 2)
        self.assertEqual(len(result), 5)
        # self.assertEqual(len(result[0]), [2, 4])


if __name__ == '__main__':
    unittest.main()
