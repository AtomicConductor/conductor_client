import sys
import os
import unittest
from unittest import TestCase
from mock import Mock
import logging

module = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if module not in sys.path:
    sys.path.insert(0, module)

sys.modules['hou'] = Mock()

from hda import frame_spec, stats

logging.basicConfig()


class BestClumpSizeTest(TestCase):

    # This not unittest.TestCase#setUp, it is manual set_up to support args
    def set_up(self, clump_size=1, frame_iterable=[1, 2, 3]):
        node = Mock(["parm"])
        parm = Mock(["eval", "set"])
        parm.eval = Mock(return_value=clump_size)
        parm.set = Mock()
        node.parm = Mock(return_value=parm)
        frame_spec.frame_set = Mock(return_value=set(frame_iterable))
        stats.update_frames_stats = Mock()
        return (node, parm)

    def test_clump_size_should_remain_1(self):
        node, parm = self.set_up(clump_size=1, frame_iterable=xrange(1, 9, 1))
        frame_spec.best_clump_size(node)
        parm.set.assert_called_with(1)

    def test_adjust_clump_size_when_possible(self):
        node, parm = self.set_up(clump_size=7, frame_iterable=xrange(1, 9, 1))
        frame_spec.best_clump_size(node)
        parm.set.assert_called_with(4)

    def test_adjust_clump_size_when_greater_than_frames(self):
        node, parm = self.set_up(clump_size=20, frame_iterable=xrange(1, 9, 1))
        frame_spec.best_clump_size(node)
        parm.set.assert_called_with(8)

    def test_adjust_clump_size_when_zero(self):
        node, parm = self.set_up(clump_size=0, frame_iterable=xrange(1, 9, 1))
        frame_spec.best_clump_size(node)
        parm.set.assert_called_with(1)

    def test_bail_out_when_no_frames(self):
        node, parm = self.set_up(clump_size=0, frame_iterable=[])
        frame_spec.best_clump_size(node)
        parm.set.assert_not_called()


class SetTypeTest(TestCase):
    pass


if __name__ == '__main__':
    unittest.main()
