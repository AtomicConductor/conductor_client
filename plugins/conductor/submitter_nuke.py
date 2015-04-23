import os,
from PySide import QtGui
import nuke
from conductor import submitter

'''
1. Where to get start end frame?  Can they be different for each write node
2. What write nodes should be selected when launching the UI?
3. Distinguish between Write and Deep Write un UI?
3. Regex frame ranges for different software plugin, or uniform across all conductor plugins? 
4. Nuke logo vs maya logo?
5. render machine options
6. Extendable vs private:  What's the line?
6. Extendable vs private:  What's the line?
'''

class NukeWidget(QtGui.QWidget):

    # The .ui designer filepath
    _ui_filepath = os.path.join(submitter.RESOURCES_DIRPATH, 'nuke.ui')

    def __init__(self, parent=None):
        super(NukeWidget, self).__init__(parent=parent)
        submitter.UiLoader.loadUi(self._ui_filepath, self)
        self.populateWriteNodes()


    def populateWriteNodes(self, write_nodes=None):
        if write_nodes == None:
            write_nodes = get_all_write_nodes()

        self.ui_write_nodes_trwgt.clear()
        assert isinstance(write_nodes, list), "write_nodes argument must be a list. Got: %s" % type(write_nodes)
        for write_node in reversed(write_nodes):
            tree_item = QtGui.QTreeWidgetItem([write_node])
            self.ui_write_nodes_trwgt.addTopLevelItem(tree_item)

#             # If the render layer is set to renderable, select it in the UI
#             if render_layer_info["renderable"]:
#                 self.ui_render_layers_trwgt.setItemSelected(tree_item, True)


    def getSelectedWrite_nodes(self):
        '''
        Return the names of the render layers that are selected in the UI
        '''
        for item in self.ui_write_nodes_trwgt.selectedItems():
            print item.text(0)





class NukeConductorSubmitter(submitter.ConductorSubmitter):
    '''
    The class is PySide front-end for submitting Nuke renders to Conductor.
    To launch the UI, simply call self.runUI method.
     
    '''

    extended_widget_class = NukeWidget

    def __init__(self, parent=None):
        super(NukeConductorSubmitter, self).__init__(parent=parent)
        self.populateFrameRange(None, None)

    @classmethod
    def runUi(cls):
        '''
        This
        '''
        ui = cls()
        ui.show()


    def populateFrameRange(self, start, end):
        start_, end_ = get_frame_range()
        if start == None:
            start = start_
        if end == None:
            end = end_
        super(NukeConductorSubmitter, self).populateFrameRange(start, end)



def get_frame_range():
    '''
    Return the frame range found in Nuke's Project settings.
    '''
    first_frame = int(nuke.Root()['first_frame'].value() or 0)
    last_frame = int(nuke.Root()['last_frame'].value() or 0)
    return first_frame, last_frame


def get_all_write_nodes():
    return get_write_nodes() + get_deep_write_nodes()

def get_write_nodes():
    return [node.name() for node in nuke.allNodes(filter="Write")]


def get_deep_write_nodes():
    return [node.name() for node in nuke.allNodes(filter="DeepWrite")]
