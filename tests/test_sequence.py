import unittest
import sys
import os

HDA_MODULE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if HDA_MODULE not in sys.path:
    sys.path.insert(0, HDA_MODULE)

from conductor.houdini.lib.sequence import Sequence


from conductor.houdini.lib.clump import (
    Clump,
    RegularClump,
    IrregularClump,
    resolve_start_end_step)


class ResolveStartEndStepTest(unittest.TestCase):

    def test_create_from_start_end_ints(self):
        start, end, step = resolve_start_end_step(1, 5)
        self.assertEqual(start, 1)
        self.assertEqual(end, 5)
        self.assertEqual(step, 1)

    def test_create_from_start_end_strings(self):
        start, end, step = resolve_start_end_step("1", "5")
        self.assertEqual(start, 1)
        self.assertEqual(end, 5)
        self.assertEqual(step, 1)

    def test_create_from_start_end_strings_backwards(self):
        start, end, step = resolve_start_end_step("5", "1")
        self.assertEqual(start, 1)
        self.assertEqual(end, 5)
        self.assertEqual(step, 1)

    def test_create_with_step_ints(self):
        start, end, step = resolve_start_end_step(1, 5, 2)
        self.assertEqual(start, 1)
        self.assertEqual(end, 5)
        self.assertEqual(step, 2)

    def test_create_with_step_strings(self):
        start, end, step = resolve_start_end_step("1", "5", "2")
        self.assertEqual(start, 1)
        self.assertEqual(end, 5)
        self.assertEqual(step, 2)

    def test_create_with_start_string(self):
        start, end, step = resolve_start_end_step("5")
        self.assertEqual(start, 5)
        self.assertEqual(end, 5)
        self.assertEqual(step, 1)

    def test_create_with_single_string(self):
        start, end, step = resolve_start_end_step("1-5")
        self.assertEqual(start, 1)
        self.assertEqual(end, 5)
        self.assertEqual(step, 1)

    def test_create_with_single_string_step(self):
        start, end, step = resolve_start_end_step("1-5x2")
        self.assertEqual(start, 1)
        self.assertEqual(end, 5)
        self.assertEqual(step, 2)

    def test_bad_step_raise(self):
        with self.assertRaises(ValueError):
            resolve_start_end_step(1, 5, 0)

    def test_invalid_specs(self):
        with self.assertRaises(ValueError):
            resolve_start_end_step("10-3x2f")
        with self.assertRaises(ValueError):
            resolve_start_end_step("g10")
        with self.assertRaises(ValueError):
            resolve_start_end_step("10--30")


class ClumpFactoryTest(unittest.TestCase):

    def test_create_regular_clump(self):
        c = Clump.create(xrange(1, 10, 2))
        self.assertIsInstance(c, RegularClump)

    def test_create_irregular_clump(self):
        c = Clump.create([1, 3, 5, 7, 10])
        self.assertIsInstance(c, IrregularClump)

    def test_auto_create_regular_clumps_type(self):
        c = Clump.regular_clumps([1, 3, 5, 7, 10])
        self.assertIsInstance(c, list)

    def test_auto_create_regular_clumps_single(self):
        c = Clump.regular_clumps([1])
        self.assertEqual(repr(c[0]), 'RegularClump("1-1x1")')

    def test_auto_create_regular_clumps_many(self):
        spec = "1, 4, 9-18x3, 26, 28, 46-60, 100"
        s = Sequence.from_spec(spec)
        c = Clump.regular_clumps(s)
        newspec = (", ").join([str(x) for x in c])
        self.assertEqual(newspec, spec)


class RegularClumpTest(unittest.TestCase):

    def test_start_end_step_properties(self):
        c = RegularClump(3, 10, 2)
        self.assertEqual(c.start, 3)
        self.assertEqual(c.end, 10)
        self.assertEqual(c.step, 2)

    def test_length(self):
        c = RegularClump(3, 5, 1)
        self.assertEqual(len(c), 3)
        c = RegularClump(0, 10, 4)
        self.assertEqual(len(c), 3)

    def test_single_frame(self):
        c = RegularClump(2, 2)
        self.assertEqual(len(c), 1)

    def test_str_with_step(self):
        c = RegularClump(3, 5, 2)
        self.assertEqual(str(c), "3-5x2")

    def test_str_with_1_step(self):
        c = RegularClump(3, 5, 1)
        self.assertEqual(str(c), "3-5")

    def test_str_with_single_value(self):
        c = RegularClump(3, 3, 1)
        self.assertEqual(str(c), "3")

    def test_repr(self):
        c = RegularClump(3, 5, 2)
        self.assertEqual(repr(c), 'RegularClump("3-5x2")')

    def test_iterable(self):
        self.assertEqual([x for x in RegularClump(3, 6, 1)], [3, 4, 5, 6])

    def test_not_enough_args_raise(self):
        with self.assertRaises(IndexError):
            RegularClump()

    def test_format(self):
        c = RegularClump(1, 10, 3)
        template = "root/%02d/name.%04d.ext"
        result = c.format(template)
        self.assertEqual(result[1], "root/04/name.0004.ext")
        self.assertEqual(len(result), 4)

    def test_start_end_step_properties_spec_args(self):
        c = RegularClump("3-10x2")
        self.assertEqual(c.start, 3)
        self.assertEqual(c.end, 10)
        self.assertEqual(c.step, 2)


class IrregularClumpTest(unittest.TestCase):

    def test_iterable(self):
        c = IrregularClump([1, 3, 2])
        self.assertEqual([x for x in c], [1, 2, 3])

    def test_length(self):
        c = IrregularClump([1, 7, 12])
        self.assertEqual(len(c), 3)

    def test_str(self):
        c = IrregularClump([1, 2, 5])
        self.assertEqual(str(c), "1,2,5")
        c = IrregularClump([1, 2, 5, 10, 15, 20, 45, 89, 92, 95])
        self.assertEqual(str(c), "1,2,5-20x5,45,89-95x3")

    def test_repr(self):
        c = IrregularClump([1, 2, 5])
        self.assertEqual(repr(c), "IrregularClump([1, 2, 5])")


class SequenceFromRangeTest(unittest.TestCase):

    def setUp(self):
        self.s = Sequence.from_range(1, 20, step=2, clump_size=3)

    def test_clump_count(self):
        self.assertEqual(self.s.clump_count(), 4)
        self.assertEqual(len(self.s.clumps()), 4)

    def test_linear_clumps(self):
        clumps = self.s.clumps()
        self.assertEqual(str(clumps[0]), '1-5x2')
        self.assertEqual(str(clumps[3]), '19')

    def test_length(self):
        self.assertEqual(len(self.s), 10)

    def test_new_clump_size(self):
        self.s.clump_size = 5
        self.assertEqual(len(self.s.clumps()), 2)
        self.assertEqual(str(self.s),
                         '[RegularClump("1-9x2"), RegularClump("11-19x2")]')

    def test_clump_size_1(self):
        self.s.clump_size = 1
        self.assertEqual(len(self.s.clumps()), 10)

    def test_oversize_clump(self):
        self.s.clump_size = 100
        self.assertEqual(len(self.s.clumps()), 1)

    def test_invalid_clump_size(self):
        with self.assertRaises(ValueError):
            self.s.clump_size = 0

    def test_iterator_linear(self):
        self.assertEqual([x for x in self.s], [x for x in xrange(1, 21, 2)])

    def test_cycle_clumps(self):
        self.s.cycle = True
        self.s.clump_size = 4
        expected = '[RegularClump("1-19x6"), RegularClump("3-15x6"), RegularClump("5-17x6")]'
        self.assertEqual(str(self.s), expected)

    def test_iterator_cycle(self):
        self.s.cycle = True
        self.s.clump_size = 4
        expected = [1, 7, 13, 19, 3, 9, 15, 5, 11, 17]
        self.assertEqual([x for x in self.s], expected)

    def test_iterator_cycle_step_1(self):
        s = Sequence.from_range(1, 10)
        s.clump_size = 4
        s.cycle = True
        expected = [1, 4, 7, 10, 2, 5, 8, 3, 6, 9]
        self.assertEqual([x for x in s], expected)

    def test_cycle_clumps_step_1(self):
        s = Sequence.from_range(1, 10)
        s.clump_size = 4
        s.cycle = True
        expected = '[RegularClump("1-10x3"), RegularClump("2-8x3"), RegularClump("3-9x3")]'
        self.assertEqual(str(s), expected)

    def test_str(self):
        s = Sequence.from_range(1, 10)
        s.clump_size = 5
        s.cycle = False
        expected = '[RegularClump("1-5x1"), RegularClump("6-10x1")]'
        self.assertEqual(str(s), expected)

    def test_repr(self):
        s = Sequence.from_range(1, 5)
        s.clump_size = 2
        s.cycle = False
        expected = 'Sequence([1, 2, 3, 4, 5], clump_size=2, cycle=False)'
        self.assertEqual(repr(s), expected)

    def test_intersection(self):
        s = Sequence.from_range(1, 10)
        t = Sequence.from_range(5, 15)
        st = s.intersection(t)
        self.assertEqual(len(st), 6)

    def test_no_intersection(self):
        s = Sequence.from_range(1, 10)
        t = Sequence.from_range(15, 25)
        st = s.intersection(t)
        self.assertEqual(len(st), 0)

    def test_best_clump_size(self):
        s = Sequence.from_range(1, 100, clump_size=77)
        self.assertEqual(s.best_clump_size(), 50)
        s.clump_size = 37
        self.assertEqual(s.best_clump_size(), 34)
        s.clump_size = 100
        self.assertEqual(s.best_clump_size(), 100)


class SequenceFromSpecTest(unittest.TestCase):

    def setUp(self):
        self.s = Sequence.from_spec("12-26x3, 1,7,8,2,4-9")

    def test_iterator_linear_sorted_no_dups(self):
        expected = [1, 2, 4, 5, 6, 7, 8, 9, 12, 15, 18, 21, 24]
        self.assertEqual(list(self.s), expected)

    def test_clump_count(self):
        self.s.clump_size = 5
        self.assertEqual(self.s.clump_count(), 3)
        self.assertEqual(len(self.s.clumps()), 3)

    def test_makes_regular_and_irregular_clumps(self):
        self.s.clump_size = 5
        r = self.s.clumps()
        self.assertIsInstance(r[0], IrregularClump)
        self.assertIsInstance(r[1], IrregularClump)
        self.assertIsInstance(r[2], RegularClump)

    def test_iterator_cycle(self):
        self.s.cycle = True
        self.s.clump_size = 5
        expected = [1, 5, 8, 15, 24, 2, 6, 9, 18, 4, 7, 12, 21]
        self.assertEqual([x for x in self.s], expected)

    def test_create_empty_sequence(self):
        self.s = Sequence([])
        self.assertEqual(len(self.s.clumps()), 0)
        self.assertEqual(list(self.s), [])

    def test_is_valid_method_true(self):
        self.assertTrue(Sequence.is_valid_spec("12-26x3, 1,7,8,2,4-9"))
        self.assertTrue(Sequence.is_valid_spec("1"))
        self.assertTrue(Sequence.is_valid_spec(",4-9,2,"))

    def test_is_valid_method_false(self):
        self.assertFalse(Sequence.is_valid_spec("12-26x3d, 1,7,8,2,4-9"))
        self.assertFalse(Sequence.is_valid_spec(",4x9,2,"))

    def test_is_valid_method_bad_type(self):
        with self.assertRaises(TypeError):
            Sequence.is_valid_spec(1)


if __name__ == '__main__':
    unittest.main()
