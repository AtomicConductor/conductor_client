import os, sys

from maya import cmds
from maya.app.general import mayaMixin

from PySide import QtGui, QtCore, QtUiTools


from conductor import submitter

'''
1. Validate against frame range  (are doubles ok?) - limit this to ints  (dev note about full frames only)
2. validate against custom frame range - see fram_range.py
3. CameraShapes or Transforms?
     - populate via transform names; pass transforms to command.  Check that namespaces are preserved
4. How does the users current selection (in maya) effect how the UI is populated?
    - select the renderlayers in the ui by which renderlayers are set to render in maya
4. Display render resolution?
5. modal Dialog or window?
6. refresh menu
7. about menu?
'''

class MayaWidget(QtGui.QWidget):

    # The .ui designer filepath
    _ui_filepath = os.path.join(submitter.RESOURCES_DIRPATH, 'maya.ui')

    def __init__(self, parent=None):
        super(MayaWidget, self).__init__(parent=parent)
        submitter.loadUi(self._ui_filepath, self)
        self.populateRenderLayers()


    def populateRenderLayers(self, render_layers_info=None):
        if render_layers_info == None:
            render_layers_info = get_render_layers_info()

        self.ui_render_layers_trwgt.clear()
        assert isinstance(render_layers_info, list), "render_layers argument must be a list. Got: %s" % type(render_layers_info)
        for render_layer_info in reversed(render_layers_info):
            tree_item = QtGui.QTreeWidgetItem([render_layer_info["layer_name"],
                                               render_layer_info["camera_shortname"]])
            tree_item._camera_transform = render_layer_info["camera_transform"]
            self.ui_render_layers_trwgt.addTopLevelItem(tree_item)

            # If the render layer is set to renderable, select it in the UI
            if render_layer_info["renderable"]:
                self.ui_render_layers_trwgt.setItemSelected(tree_item, True)


    def get_selected_renderlayers(self):
        '''
        Return the names of the render layers that are selected in the UI
        '''
        for item in self.ui_render_layers_trwgt.selectedItems():
            print item.text(0)


class MayaConductorSubmitter(submitter.ConductorSubmitter):
    '''
    TODO: inherit from maya's interface
    
    This class inherits from the generic conductor submitter and adds additional
    widgets for maya-specific data.
    
    When the UI loads it will automatically populate various information:
    
    1. Frame range
    
    2. Camera
    
    3. Render layers
    
    
    '''
    extended_widget_class = MayaWidget

    def __init__(self, parent=None):
        super(MayaConductorSubmitter, self).__init__(parent=parent)
        self.populateFrameRange(None, None)


    @classmethod
    def runUi(cls):
        '''
        Load the UI
        '''
        ui = cls()
        ui.show()


    def addMayaWidget(self):
        self.maya_wgt = MayaWidget()
        self.layout = QtGui.QVBoxLayout()
        self.ui_extendable_wgt.setLayout(self.layout)
        self.layout.addWidget(self.maya_wgt)


    def populateFrameRange(self, start, end):
        start_, end_ = get_frame_range()[0]
        if start == None:
            start = start_
        if end == None:
            end = end_
        super(MayaConductorSubmitter, self).populateFrameRange(start, end)

    @QtCore.Slot(name="on_ui_submit_pbtn_clicked")
    def on_ui_submit_pbtn_clicked(self):
        print "Frame range: %s" % self.get_frame_ranges()
        print "render layers:"
        self.extended_widget.get_selected_renderlayers()





def get_frame_range():
    '''
    Return the current frame range for the current maya scene.  This consists
    of both the "playback" start/end frames, as well as the "range" start/end frames.
    
    Note that only integers are currently support for frames
    
    return: list of two tuples, where the first tuple is the "playback" start/end 
            frames and the second is the "range" start/end frames,
            e.g. [(1.0, 24.0), (5.0, 10.0)]
    '''
    # Get the full start/end frame range
    playback_start = cmds.playbackOptions(q=True, animationStartTime=True)
    playback_end = cmds.playbackOptions(q=True, animationEndTime=True)

    # Get the selected range start/end
    range_start = cmds.playbackOptions(q=True, minTime=True)
    range_end = cmds.playbackOptions(q=True, maxTime=True)
    return [(int(playback_start), int(playback_end)), (int(range_start), int(range_end))]



def get_render_layers_info():
    '''
    Return a list of dictionaries where each dictionary represents data for 
    a a render layer.  Each dictionar provides the following information:
        - render layer name
        - whether the render layer is set to renderable 
        - the camera that the render layer uses
    
    Note that only one camera is allowed per render layer.  This is somewhat
    of an arbitraty limitation, but implemented to reduce complexity.  This 
    restriction may need to be removed.
    
    '''
    render_layers = []
    cameras = cmds.ls(type="camera", long=True)
    for render_layer in cmds.ls(type="renderLayer"):
        layer_info = {"layer_name": render_layer}
        cmds.editRenderLayerGlobals(currentRenderLayer=render_layer)
        renderable_cameras = [get_transform(camera) for camera in cameras if cmds.getAttr("%s.renderable" % camera)]
        assert renderable_cameras, 'No Renderable camera found for render layer "%s"' % render_layer
        assert len(renderable_cameras) == 1, 'More than one renderable camera found for render layer "%s". Cameras: %s' % (render_layer, renderable_cameras)

        layer_info["camera_transform"] = renderable_cameras[0]
        layer_info["camera_shortname"] = get_short_name(layer_info["camera_transform"])
        layer_info["renderable"] = cmds.getAttr("%s.renderable" % render_layer)
        render_layers.append(layer_info)

    return render_layers



def get_transform(shape_node):
    relatives = cmds.listRelatives(shape_node, parent=True, type="transform", fullPath=True) or []
    assert relatives, "Could not find parent for shape node: %s" % shape_node
    assert len(relatives) == 1, "More than one parent found for shape node: %s" % shape_node
    return relatives[0]


def get_short_name(node):
    short_name = cmds.ls(node)
    assert short_name, "Node does not exist: %s" % node
    assert len(short_name) == 1, "More than one object matches node name: %s" % node
    return short_name[0]


def get_render_resolution():
    '''
    #TODO: should the render resolution be displayed?
    '''
