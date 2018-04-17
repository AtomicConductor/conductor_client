import unittest
import sys
import os

import mock

HDA_MODULE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if HDA_MODULE not in sys.path:
    sys.path.insert(0, HDA_MODULE)


# mocked api_client returns json fixtures
sys.modules['conductor.lib.api_client'] = __import__(
    'conductor.houdini.lib.mocks.api_client_mock', fromlist=['dummy'])


from conductor.houdini.lib import data_block as db
from conductor.houdini.lib.mocks.api_client_mock import ApiClient
from conductor.houdini.lib.package_tree import PackageTree


class InstantiationTest(unittest.TestCase):

    def setUp(self):
        db.ConductorDataBlock.clear()
        self.d = db.ConductorDataBlock()

    def test_instantiates(self):
        d = db.ConductorDataBlock()
        self.assertIsInstance(d, db.ConductorDataBlock)

    def test_has_resources(self):
        d = db.ConductorDataBlock()
        self.assertIsInstance(d.projects(), list)
        self.assertIsInstance(d.instance_types(), list)
        self.assertIsInstance(d.package_tree(), PackageTree)

    def test_does_not_make_second_instance(self):
        d = db.ConductorDataBlock()
        inst1 = d.instance
        d = db.ConductorDataBlock()
        inst2 = d.instance
        self.assertIs(inst1, inst2)

    def test_does_make_second_instance_if_forced(self):
        d = db.ConductorDataBlock()
        inst1 = d.instance
        d = db.ConductorDataBlock(force=True)
        inst2 = d.instance
        self.assertIsNot(inst1, inst2)


class FactoryTest(unittest.TestCase):

    def test_houdini_factory_method(self):
        db.ConductorDataBlock.clear()
        d = db.for_houdini()
        self.assertIsInstance(d, db.ConductorDataBlock)

    klass = 'conductor.houdini.lib.data_block.ConductorDataBlock'

    @mock.patch(klass, autospec=True)
    def test_houdini_factory_calls_constructor(
            self, mock_data_block):
        db.for_houdini()
        mock_data_block.assert_called_with(product="houdini", force=False)
        db.for_houdini(force=True)
        mock_data_block.assert_called_with(product="houdini", force=True)


if __name__ == '__main__':
    unittest.main()
