import os, uuid, tempfile

from maya import cmds
from PySide import QtGui, QtCore

from conductor import submitter, submitter_maya_resources  # This is required so that when the .ui file is loaded, any resources that it uses from the qrc resource file will be found

# A dict of maya node types and their attributes to query for dependency filepaths
NODE_DEP_ATTRS = {'file':['fileTextureName'],
                 'AlembicNode':['abc_File'],
                 'VRayMesh':['fileName'],
                 'VRaySettingsNode':['ifile', 'fnm']}


'''
TODO: 
1. When the Upload Only argument is sent to the conductor Submit object as True, does it ignore the filepath and render layer arguments?  Or should those arguments not be given to the Submit object.
2. implement pyside inheritance to Maya's window interface
'''

class MayaWidget(QtGui.QWidget):

    # The .ui designer filepath
    _ui_filepath = os.path.join(submitter.RESOURCES_DIRPATH, 'maya.ui')

    def __init__(self, parent=None):
        super(MayaWidget, self).__init__(parent=parent)
        submitter.UiLoader.loadUi(self._ui_filepath, self)
        self.refreshUi()

    def refreshUi(self):
        render_layers_info = get_render_layers_info()
        self.populateRenderLayers(render_layers_info)


    def populateRenderLayers(self, render_layers_info):
        '''
        Populate each render layer into the UI QTreeWidget.
        If the render layer has been set to renderable in maya, then check its
        qtreewidgetitem's checkbox (on) the the render layer  UI.  Only render 
        layers that are checked on will be rendered
        '''
        self.ui_render_layers_trwgt.clear()
        assert isinstance(render_layers_info, list), "render_layers argument must be a list. Got: %s" % type(render_layers_info)
        for render_layer_info in reversed(render_layers_info):
            tree_item = QtGui.QTreeWidgetItem([render_layer_info["layer_name"],
                                               render_layer_info["camera_shortname"]])

            tree_item.setFlags(tree_item.flags() | QtCore.Qt.ItemIsUserCheckable)
            tree_item._camera_transform = render_layer_info["camera_transform"]
            self.ui_render_layers_trwgt.addTopLevelItem(tree_item)

            # If the render layer is set to renderable, then check the item's checkbox on
            if render_layer_info["renderable"]:
                tree_item.setCheckState(0, QtCore.Qt.Checked)
            else:
                tree_item.setCheckState(0, QtCore.Qt.Unchecked)


    def getSelectedRenderLayers(self):
        '''
        Return the names of the render layers that have their checkboxes checked on
        '''
        selected_layers = []
        for row_idx in range(self.ui_render_layers_trwgt.topLevelItemCount()):
            item = self.ui_render_layers_trwgt.topLevelItem(row_idx)
            if item.checkState(0) == QtCore.Qt.Checked:
                selected_layers.append(item.text(0))
        return selected_layers


    def getUploadOnlyBool(self):
        '''
        Return whether the "Upload Only" checkbox is checked on or off.
        '''
        return self.ui_upload_only.isChecked()


    @QtCore.Slot(bool, name="on_ui_upload_only_toggled")
    def on_ui_upload_only_toggled(self, toggled):
        '''
        when the "Upload Only" checkbox is checked on, disable the Render 
        Layers widget. when the "Upload Only" checkbox is checked off, enable
        the Render Layers widget.
        '''
        self.ui_render_layers_trwgt.setDisabled(toggled)


class MayaConductorSubmitter(submitter.ConductorSubmitter):
    '''
    
    This class inherits from the generic conductor submitter and adds an additional
    widget for maya-specific data.
    
    Note that the addional widget is stored (and accessible) via the 
    self.extended_widget attribute
    
    When the UI loads it will automatically populate various information:
        1. Frame range  
        2. Render layers (with their camera)
    
    '''


    _window_title = "Conductor - Maya"

    @classmethod
    def runUi(cls):
        '''
        Load the UI
        '''
        ui = cls()
        ui.show()

    def __init__(self, parent=None):
        super(MayaConductorSubmitter, self).__init__(parent=parent)
        self.refreshUi()

    def initializeUi(self):
        super(MayaConductorSubmitter, self).initializeUi()


    def refreshUi(self):
        start, end = get_frame_range()[0]
        self.setFrameRange(start, end)
        self.extended_widget.refreshUi()


    def getExtendedWidget(self):
        return MayaWidget()

    def generateConductorCmd(self):
        '''
        Return the command string that Conductor will execute
        
        example:
            "maya2015Render -rd /tmp/render_output/ -s %f -e %f -rl render_layer1_name -rl render_layer2_name maya_maya_filepath.ma"
        '''
        base_cmd = "maya2015Render -rd /tmp/render_output/ -s %%f -e %%f %s %s"

        render_layers = self.extended_widget.getSelectedRenderLayers()
        render_layer_args = ["-fl %s" % render_layer for render_layer in render_layers]
        maya_filepath = get_maya_scene_filepath()
        cmd = base_cmd % (" ".join(render_layer_args), maya_filepath)
        return cmd


    def generateConductorArgs(self):
        '''
        Override this method from the base class to provide conductor arguments that 
        are specific for Maya.  See the base class' docstring for more details.
        
        
            cmd: str
            force: bool
            frames: str
            output_path: str # The directory path that the render images are set to output to  
            postcmd: str?
            priority: int?
            resource: int, core count
            skip_time_check: bool?
            upload_dependent: int? jobid?
            upload_file: str , the filepath to the dependency text file 
            upload_only: bool
            upload_paths: list of str?
            usr: str
        
        '''
        conductor_args = {}
        conductor_args["cmd"] = self.generateConductorCmd()
        conductor_args["force"] = self.getForceUploadBool()
        conductor_args["frames"] = self.getFrameRangeString()
        conductor_args["output_path"] = get_image_dirpath()
        conductor_args["upload_file"] = get_dependencies()
        conductor_args["upload_only"] = self.extended_widget.getUploadOnlyBool()
        conductor_args["resource"] = self.getCoreCount()
        return conductor_args



def get_dependencies():
    '''
    Generate a list of filepaths that the current maya scene is dependent on.
    This list will be written to a text file which conductor will use to upload
    the necessary files when executing a render.
    If no depenencies exist, return None
    '''
    dependencies = collect_dependencies(NODE_DEP_ATTRS)
    if dependencies:
        depenency_filepath = submitter.generate_temporary_filepath()
        return submitter.write_dependency_file(dependencies, depenency_filepath)




def get_maya_scene_filepath():
    filepath = cmds.file(q=True, sceneName=True)
    if not filepath or not os.path.isfile(filepath):
        raise Exception("Maya scene has not been saved to a file location.  Please save file before submitting to Conductor.")
    return str(filepath)



def get_image_dirpath():
    workspace_root = cmds.workspace(q=True, rootDirectory=True)
    image_dirname = cmds.workspace(fileRuleEntry="images")
    return os.path.join(workspace_root, image_dirname)


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
    TODO: Does the default render layer name need to be augmented when passed to maya's rendering command?
    TODO: Should the default render layer be included at all?  And should it be unselected by default?
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


def collect_dependencies(node_attrs):
    '''
    Return a list of filepaths that the current maya scene has dependencies on.
    This is achieved by inspecting maya's nodes.  Use the node_attrs argument
    to pass in a dictionary 

        node_attrs = {'file':['fileTextureName'],
                 'af_alembicDeform':['fileName'],
                 'AlembicNode':['abc_File'],
                 'VRayMesh':['fileName'],
                 'VRaySettingsNode':['ifile', 'fnm'],
                 'CrowdProxyVRay':['cacheFileDir', 'camFilePath'],
                 'CrowdManagerNode':['escod', 'efbxod', 'eabcod', 'eribod', 'emrod', 'evrod', 'eassod', 'cam']
                 }

    
    '''
    assert isinstance(node_attrs, dict), "node_attrs arg must be a dict. Got %s" % type(node_attrs)

    # Scene name, refs and textures
    dependencies = cmds.file(query=True, list=True) or []

    # explicit deps
    if node_attrs is None:
        node_attrs = {'file':['fileTextureName'],
                     'af_alembicDeform':['fileName'],
                     'AlembicNode':['abc_File'],
                     'VRayMesh':['fileName'],
                     'VRaySettingsNode':['ifile', 'fnm'],
                     'CrowdProxyVRay':['cacheFileDir', 'camFilePath'],
                     'CrowdManagerNode':['escod', 'efbxod', 'eabcod', 'eribod', 'emrod', 'evrod', 'eassod', 'cam']
                     }

    all_node_types = cmds.allNodeTypes()

    for node_type, node_attrs in node_attrs.iteritems():

        if node_type not in all_node_types:
            print "Warning: skipping unknown node type: %s" % node_type
            continue

        for node in cmds.ls(type=node_type):
            for node_attr in node_attrs:
                plug_name = '%s.%s' % (node, node_attr)
                if cmds.objExists(plug_name):
                    plug_value = cmds.getAttr(plug_name)
                    path = cmds.file(plug_value, exn=True, query=True)
                    dependencies.append(path)

    return sorted(set([os.path.normpath(path) for path in dependencies]))




def get_transform(shape_node):
    '''
    Return the transform node of a given shape node
    '''
    relatives = cmds.listRelatives(shape_node, parent=True, type="transform", fullPath=True) or []
    assert relatives, "Could not find parent for shape node: %s" % shape_node
    assert len(relatives) == 1, "More than one parent found for shape node: %s" % shape_node
    return relatives[0]


def get_short_name(node):
    '''
    Return the short name of a given maya node
    '''
    short_name = cmds.ls(node)
    assert short_name, "Node does not exist: %s" % node
    assert len(short_name) == 1, "More than one object matches node name: %s" % node
    return short_name[0]

