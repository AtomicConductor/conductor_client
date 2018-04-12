
import os
import sys
from mock import Mock

HDA_MODULE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if HDA_MODULE not in sys.path:
    sys.path.insert(0, HDA_MODULE)



sys.modules['hou'] = Mock()

from hda import frame_spec_ui
