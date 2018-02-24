import unittest
import sys
import os

HDA_MODULE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if HDA_MODULE not in sys.path:
    sys.path.insert(0, HDA_MODULE)

from hda.clumps import RegularClump, IrregularClump, ClumpCollection, to_xrange


class RegularClumpNumericInitTest(unittest.TestCase):

    def test_start_end_step_properties(self):
        r = RegularClump(3, 10, 2)
        self.assertEqual(r.start, 3)
        self.assertEqual(r.end, 10)
        self.assertEqual(r.step, 2)

    def test_first_last_properties(self):
        r = RegularClump(3, 10, 2)
        self.assertEqual(r.first, 3)
        self.assertEqual(r.last, 9)

    def test_start_end_properties_reversed(self):
        r = RegularClump(10, 3, 2)
        self.assertEqual(r.start, 3)
        self.assertEqual(r.end, 10)

    def test_bad_step_raise(self):
        with self.assertRaises(ValueError):
            RegularClump(3, 10, 0)

    def test_length(self):
        r = RegularClump(3, 5, 1)
        self.assertEqual(len(r), 3)
        r = RegularClump(0, 10, 4)
        self.assertEqual(len(r), 3)

    def test_single_frame(self):
        r = RegularClump(2, 2)
        self.assertEqual(len(r), 1)

    def test_str(self):
        r = RegularClump(3, 5, 2)
        self.assertEqual(str(r), "RegularClump(3-5x2)")

    def test_iterable(self):
        self.assertEqual([x for x in RegularClump(3, 6, 1)], [3, 4, 5, 6])

    def test_too_many_args_raise(self):
        with self.assertRaises(TypeError):
            RegularClump(3, 10, 0, 7, 8)

    def test_not_enough_args_raise(self):
        with self.assertRaises(TypeError):
            RegularClump()

    def test_format(self):
        r = RegularClump(1, 10, 3)
        template = "root/%02d/name.%04d.ext"
        result = r.format(template)
        self.assertEqual(result[1], "root/04/name.0004.ext")
        self.assertEqual(len(result), 4)

    def test_is_regular(self):
        r = RegularClump(1, 10, 3)
        self.assertEqual(r.is_regular, True)
        self.assertEqual(r.is_irregular, False)


class RegularClumpSpecInitTest(unittest.TestCase):

    def test_start_end_step_properties(self):
        r = RegularClump("3-10x2")
        self.assertEqual(r.start, 3)
        self.assertEqual(r.end, 10)
        self.assertEqual(r.step, 2)

    def test_first_last_properties(self):
        r = RegularClump("3-10x2")
        self.assertEqual(r.first, 3)
        self.assertEqual(r.last, 9)

    def test_start_end_properties_reversed(self):
        r = RegularClump("10-3x2")
        self.assertEqual(r.start, 3)
        self.assertEqual(r.end, 10)

    def test_invalid_spec(self):
        with self.assertRaises(TypeError):
            RegularClump("10-3x2f")
        with self.assertRaises(TypeError):
            RegularClump("10")


class IrregularClumpTest(unittest.TestCase):

    def test_iterable(self):
        self.assertEqual([x for x in IrregularClump([1, 3, 2])], [1, 2, 3])

    def test_length(self):
        r = IrregularClump([1, 7, 12])
        self.assertEqual(len(r), 3)

    def test_first_last_properties(self):
        r = IrregularClump([1, 2, 3])
        self.assertEqual(r.first, 1)
        self.assertEqual(r.last, 3)

    def test_sort_if_unordered_input(self):
        r = IrregularClump([4, 1, 2, 37, 3, 25, 28])
        self.assertEqual(r.first, 1)
        self.assertEqual(r.last, 37)

    def test_str(self):
        r = IrregularClump([1, 2, 3])
        self.assertEqual(str(r), "IrregularClump(1~3)")

    def test_iterable2(self):
        self.assertEqual(
            [x for x in IrregularClump([1, 3, 4, 2])], [1, 2, 3, 4])


class CreateXRangeTest(unittest.TestCase):

    def test_create_from_start_end_ints(self):
        r = to_xrange((1, 5))
        self.assertEqual(str(r), 'xrange(1, 6)')

    def test_create_from_start_end_strings(self):
        r = to_xrange(("1", "5"))
        self.assertEqual(str(r), 'xrange(1, 6)')

    def test_create_from_start_end_strings_backwards(self):
        r = to_xrange(("5", "1"))
        self.assertEqual(str(r), 'xrange(1, 6)')

    def test_create_with_step_ints(self):
        r = to_xrange((1, 5, 2))
        self.assertEqual(str(r), 'xrange(1, 6, 2)')

    def test_create_with_step_strings(self):
        r = to_xrange(("1", "5", "2"))
        self.assertEqual(str(r), 'xrange(1, 6, 2)')

    # def test_num_frames(self):
    #     self.assertEqual(self.c.total_length, 10)

    # def test_regular(self):
    #     self.assertTrue(self.c.clumps[0].regular)
    #     self.assertTrue(self.c.clumps[3].regular)


# class LinearClumpCollectionFromRangeTest(unittest.TestCase):

#     def setUp(self):
#         # expands to (1,3,5),(7,9,11),(13,15,17),(19)
#         self.c = ClumpCollection.from_range(1, 20, step=2, clump_size=3)

#     def test_num_clumps(self):
#         self.assertEqual(len(self.c), 4)

    # def test_num_frames(self):
    #     self.assertEqual(self.c.total_length, 10)

    # def test_regular(self):
    #     self.assertTrue(self.c.clumps[0].regular)
    #     self.assertTrue(self.c.clumps[3].regular)


# class ClumpCollectionFromStringTest(unittest.TestCase):

#     def setUp(self):
#         # expands to (1,3,2),(7,4,5),(6,8,9),(12,15)
#         self.c = ClumpCollection(
#             frameList="1,3,2,7,2,4-9,12-16x3", clumpSize=3)

#     def test_num_clumps(self):
#         self.assertEqual(len(self.c), 4)

#     def test_num_frames(self):
#         self.assertEqual(self.c.total_length, 11)

#     def test_order_maintained(self):
#         self.assertEqual(self.c.clumps[0].frames, [1, 3, 2])

#     def test_irregular(self):
#         self.assertTrue(self.c.clumps[0].irregular)
#         self.assertFalse(self.c.clumps[0].regular)

#     def test_regular(self):
#         self.assertTrue(self.c.clumps[3].regular)
#         self.assertFalse(self.c.clumps[3].irregular)

#     def test_iterable(self):
#         it = [x for x in self.c]
#         self.assertEqual(len(it), 4)
#         self.assertIsInstance(it[0], Clump)


# class LinearClumpCollectionFromRangeTest(unittest.TestCase):

#     def setUp(self):
#         # expands to (1,3,5),(7,9,11),(13,15,17),(19)
#         self.c = ClumpCollection(start=1, end=20, step=2, clumpSize=3)

#     def test_num_clumps(self):
#         self.assertEqual(len(self.c), 4)

#     def test_num_frames(self):
#         self.assertEqual(self.c.total_length, 10)

#     def test_regular(self):
#         self.assertTrue(self.c.clumps[0].regular)
#         self.assertTrue(self.c.clumps[3].regular)


# class CycleClumpCollectionFromRangeTest(unittest.TestCase):

#     def test_ones_sequence(self):
#         c = ClumpCollection(start=1, end=10, step=1, clumpSize=1, cycle=True)
#         self.assertEqual(len(c), 10)
#         self.assertEqual(c.total_length, 10)
#         s = "1-1x1\n2-2x1\n3-3x1\n4-4x1\n5-5x1\n6-6x1\n7-7x1\n8-8x1\n9-9x1\n10-10x1"
#         self.assertEqual(str(c), s)

#     def test_twos_sequence(self):
#         # expands to (1,7,13),(3,9,15),(5,11,17),(19)
#         c = ClumpCollection(start=1, end=20, step=2, clumpSize=3, cycle=True)
#         self.assertEqual(len(c), 4)
#         self.assertEqual(c.total_length, 10)
#         self.assertTrue(c.clumps[0].regular)
#         self.assertTrue(c.clumps[3].regular)
#         s = "1-17x8\n3-19x8\n5-13x8\n7-15x8"
#         self.assertEqual(str(c), s)

#     def test_larger_sequence(self):
#         c = ClumpCollection(start=17, end=353, step=1,
#                             clumpSize=10, cycle=True)
#         self.assertEqual(len(c), 34)
#         self.assertEqual(c.total_length, 337)


# class ClumpCollectionWithFloatArgs(unittest.TestCase):

#     def test_linear(self):
#         c = ClumpCollection(start=1.0, end=20.0, step=2.0,
#                             clumpSize=3, cycle=False)
#         self.assertEqual(len(c), 4)
#         self.assertEqual(c.total_length, 10)

#     def test_cycle(self):
#         c = ClumpCollection(start=1.0, end=20.0, step=2.0,
#                             clumpSize=3, cycle=True)
#         self.assertEqual(len(c), 4)
#         self.assertEqual(c.total_length, 10)

#     def test_framelist(self):
#         c = ClumpCollection(frameList="1,3,2,7,2,4-9,12-16x3", clumpSize=3)
#         self.assertEqual(len(c), 4)
#         self.assertEqual(c.total_length, 11)


if __name__ == '__main__':
    unittest.main()
