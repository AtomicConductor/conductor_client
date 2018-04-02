import unittest
import sys
import os

HDA_MODULE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if HDA_MODULE not in sys.path:
    sys.path.insert(0, HDA_MODULE)

from conductor.houdini.lib.sequence import (Sequence, Progression)


class SequenceFactoryTest(unittest.TestCase):

    def test_single_number_is_progression(self):
        s = Sequence.create(1)
        self.assertIsInstance(s, Progression)

    def test_range_is_progression(self):
        s = Sequence.create(1, 10)
        self.assertIsInstance(s, Progression)

    def test_range_step_is_progression(self):
        s = Sequence.create(1, 10, 2)
        self.assertIsInstance(s, Progression)

    def test_single_number_string_is_progression(self):
        s = Sequence.create("1")
        self.assertIsInstance(s, Progression)

    def test_range_string_is_progression(self):
        s = Sequence.create("1-10x2")
        self.assertIsInstance(s, Progression)

    def test_frame_spec_is_not_progression(self):
        s = Sequence.create("1-10, 14, 20-50x4")
        self.assertIsInstance(s, Sequence)
        self.assertNotIsInstance(s, Progression)

    def test_list_sequence_is_not_progression(self):
        s = Sequence.create([1, 3, 4, 6, 8, 9])
        self.assertIsInstance(s, Sequence)
        self.assertNotIsInstance(s, Progression)

    def test_progressive_list_is_progression(self):
        s = Sequence.create([1, 3, 5, 7, 9])
        self.assertIsInstance(s, Progression)

    def test_is_progression_method(self):
        s = Sequence.create([1, 3, 5, 7, 9])
        self.assertTrue(s.is_progression())
        s = Sequence.create([1, 3, 5, 7, 9, 10])
        self.assertFalse(s.is_progression())


class SequenceFactoryFailTest(unittest.TestCase):

    def test_negative_number(self):
        with self.assertRaises(ValueError):
            s = Sequence.create(-1)

    def test_negative_end(self):
        with self.assertRaises(ValueError):
            s = Sequence.create(1, -10, 1)

    def test_negative_step(self):
        with self.assertRaises(ValueError):
            s = Sequence.create(1, 10, -1)

    def test_negative_end(self):
        with self.assertRaises(ValueError):
            s = Sequence.create("10--30")

    def test_bad_spec(self):
        with self.assertRaises(ValueError):
            s = Sequence.create("f")

    def test_bad_spec_step(self):
        with self.assertRaises(ValueError):
            s = Sequence.create("1-10xf")


class StartEndStepValuesTest(unittest.TestCase):

    def test_create_from_start_only(self):
        s = Sequence.create(1)
        self.assertEqual(s.start, 1)
        self.assertEqual(s.end, 1)
        self.assertEqual(s.step, 1)

    def test_create_from_start_end_ints(self):
        s = Sequence.create(1, 5)
        self.assertEqual(s.start, 1)
        self.assertEqual(s.end, 5)
        self.assertEqual(s.step, 1)

    def test_create_from_start_end_strings(self):
        s = Sequence.create("1-5")
        self.assertEqual(s.start, 1)
        self.assertEqual(s.end, 5)
        self.assertEqual(s.step, 1)

    def test_create_from_start_end_strings_backwards(self):
        s = Sequence.create("5-1")
        self.assertEqual(s.start, 1)
        self.assertEqual(s.end, 5)
        self.assertEqual(s.step, 1)

    def test_create_with_step_ints(self):
        s = Sequence.create(1, 5, 2)
        self.assertEqual(s.start, 1)
        self.assertEqual(s.end, 5)
        self.assertEqual(s.step, 2)

    def test_create_with_step_strings(self):
        s = Sequence.create("1-5x2")
        self.assertEqual(s.start, 1)
        self.assertEqual(s.end, 5)
        self.assertEqual(s.step, 2)

    def test_create_with_start_string(self):
        s = Sequence.create("5")
        self.assertEqual(s.start, 5)
        self.assertEqual(s.end, 5)
        self.assertEqual(s.step, 1)


class SequenceToStringTest(unittest.TestCase):

    def test_progression_single(self):
        s = Progression(1, 1, 1)
        self.assertEqual(str(s), "1")

    def test_progression_range(self):
        s = Progression(1, 10, 1)
        self.assertEqual(str(s), "1-10")

    def test_progression_range_step(self):
        s = Progression(1, 9, 2)
        self.assertEqual(str(s), "1-9x2")

    def test_progression_range_step_round_down(self):
        s = Sequence.create(0, 10, 3)
        self.assertEqual(str(s), "0-9x3")

    def test_sequence(self):
        s = Sequence.create("1-10, 14, 20-48x4")
        self.assertEqual(str(s), "1-10,14,20-48x4")

    def test_repr_from_progression(self):
        s = Sequence.create(0, 10, 3)
        self.assertEqual(repr(s), "Sequence.create('0-9x3')")

    def test_repr_from_sequence(self):
        s = Sequence.create("1-10, 14, 20-48x4")
        self.assertEqual(repr(s), "Sequence.create('1-10,14,20-48x4')")


class ClumpsTest(unittest.TestCase):

    def test_no_clump_size(self):
        s = Sequence.create("1-100")
        self.assertEqual(s.clump_size, 100)

    def test_clamp_clump_size(self):
        s = Sequence.create("1-100", clump_size=200)
        self.assertEqual(s.clump_size, 100)

    def test_clump_size(self):
        s = Sequence.create("1-100", clump_size=50)
        self.assertEqual(s.clump_size, 50)

    def test_clump_size_setter(self):
        s = Sequence.create("1-100")
        s.clump_size = 50
        self.assertEqual(s.clump_size, 50)

    def test_best_clump_size(self):
        s = Sequence.create("1-100")
        s.clump_size = 76
        self.assertEqual(s.best_clump_size(), 50)
        s.clump_size = 37
        self.assertEqual(s.best_clump_size(), 34)
        s.clump_size = 100
        self.assertEqual(s.best_clump_size(), 100)

    def test_create_clumps_linear(self):
        s = Sequence.create("1-100")
        s.clump_size = 10
        clumps = s.clumps("linear")
        self.assertEqual(list(clumps[0]), list(range(1, 11)))

    def test_create_clumps_cycle(self):
        s = Sequence.create("1-100")
        s.clump_size = 10
        clumps = s.clumps("cycle")
        self.assertEqual(list(clumps[0]), list(range(1, 100, 10)))
        s.clump_size = 7
        clumps = s.clumps("cycle")
        self.assertEqual(list(clumps[0]), list(range(1, 100, 15)))

    def test_clump_count(self):
        s = Sequence.create("1-100")
        s.clump_size = 7
        self.assertEqual(s.clump_count(), 15)
        s.clump_size = 15
        self.assertEqual(s.clump_count(), 7)
        s.clump_size = 10
        self.assertEqual(s.clump_count(), 10)


class IntersectionTest(unittest.TestCase):

    def test_does_intersect(self):
        s = Sequence.create("1-10")
        i = s.intersection(range(5, 15))
        self.assertEqual(list(i), list(range(5, 11)))

    def test_does_not_intersect(self):
        s = Sequence.create("1-10")
        i = s.intersection(range(25, 35))
        self.assertEqual(i, None)


class ProgressionsTest(unittest.TestCase):

    def test_longest_progressions_factory(self):
        s = Sequence.create("1-10, 14, 20-48x4")
        progs = Progression.factory(s)
        self.assertEqual(len(progs), 3)

    def test_limited_length_progressions_factory(self):
        s = Sequence.create("1-10, 14, 20-48x4")
        progs = Progression.factory(s, max_size=4)
        self.assertEqual(len(progs), 6)


class SequenceValidator(unittest.TestCase):

    def test_is_valid_method_true(self):
        self.assertTrue(Sequence.is_valid_spec("12-26x3, 1,7,8,2,4-9"))
        self.assertTrue(Sequence.is_valid_spec("1"))
        self.assertTrue(Sequence.is_valid_spec(",4-9,2,"))

    def test_is_valid_method_false(self):
        self.assertFalse(Sequence.is_valid_spec("12-26x3d, 1,7,8,2,4-9"))
        self.assertFalse(Sequence.is_valid_spec(",4x9,2,"))
        self.assertFalse(Sequence.is_valid_spec(" "))

    def test_is_valid_method_bad_type(self):
        with self.assertRaises(TypeError):
            Sequence.is_valid_spec(1)
        with self.assertRaises(TypeError):
            Sequence.is_valid_spec()


class SequenceIterator(unittest.TestCase):

    def test_iterator_sorted_no_dups(self):
        s = Sequence.create("1-10, 8-20x2, 19, 17")
        expected = [1, 2, 3, 4, 5, 6, 7, 8, 9,
                    10, 12, 14, 16, 17, 18, 19, 20]
        self.assertEqual(list(s), expected)


class ProgressionsTest(unittest.TestCase):

    def test_empty(self):
        result = Progression.factory([])
        self.assertEqual(result, [])

    def test_single(self):
        result = Progression.factory([3])
        self.assertEqual(len(result), 1)
        self.assertEqual(str(result[0]), "3")

    def test_two(self):
        result = Progression.factory([3, 7])
        self.assertEqual(len(result), 1)
        self.assertEqual(str(result[0]), "3-7x4")

    def test_progression_at_start(self):
        result = Progression.factory([3, 5, 7, 10, 15])
        self.assertEqual(len(result), 2)
        self.assertEqual(str(result[0]), "3-7x2")

    def test_progression_at_end(self):
        result = Progression.factory([3, 5, 8, 10, 12])
        self.assertEqual(str(result[1]), "8-12x2")

    def test_order(self):
        numbers = [3, 5, 8, 10, 12]
        numbers.reverse()
        result = Progression.factory(numbers)
        self.assertEqual(str(result[0]), "3-5x2")
        self.assertEqual(str(result[1]), "8-12x2")

    def test_from_range(self):
        result = Progression.factory(xrange(2, 97, 3))
        self.assertEqual(len(result), 1)
        self.assertEqual(len(result[0]), 32)

    def test_max_size_one(self):
        result = Progression.factory([2, 4, 6, 8, 10], max_size=1)
        self.assertEqual(len(result), 5)

    def test_max_2(self):
        result = Progression.factory([2, 4, 6, 8, 10], max_size=2)
        self.assertEqual(len(result), 3)

    def test_max_16(self):
        result = Progression.factory(xrange(2, 197, 3), max_size=16)
        self.assertEqual(len(result[0]), 16)
        self.assertEqual(len(result), 5)


if __name__ == '__main__':
    unittest.main()
