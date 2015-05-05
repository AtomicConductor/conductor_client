import os
from PySide import QtGui, QtCore
import nuke
from conductor import submitter

# A dict of nuke node types, and their knob names to query for dependency filepaths

NODE_DEP_ATTRS = {  'Read':['file'],
                    'DeepRead':['file'],
                    'ReadGeo2':['file'],
                    'Vectorfield':['vfield_file'],
                    'ScannedGrain':['fullGrain'],
                    'Group':['vfield_file', 'cdl_path'],
                    'Precomp':['file'],
                    'AudioRead':['file']}



'''
TODO:
1. Get nuke dependencies
4. what is the "output_path" arg for nuke render's? (in maya its the root images dir from project settings)
2. What write nodes should be selected when launching the UI? - only those which are selected by the user in nuke
3. implement pyside inheritance for Nuke's window interface
'''

class NukeWidget(QtGui.QWidget):

    # The .ui designer filepath
    _ui_filepath = os.path.join(submitter.RESOURCES_DIRPATH, 'nuke.ui')

    def __init__(self, parent=None):
        super(NukeWidget, self).__init__(parent=parent)
        submitter.UiLoader.loadUi(self._ui_filepath, self)
        self.refreshUi()

    def refreshUi(self):
        write_nodes = get_all_write_nodes()
        self.populateWriteNodes(write_nodes)


    def populateWriteNodes(self, write_nodes):
        '''
        Populate each Write and Deep Write node into the UI QTreeWidget.
        Any write nodes that are currently selected in nuke by the user will be
        also be selected in UI. Note that only write nodes that are selected in 
        the UI will be rendered when submitting to Conductor.
        '''
        self.ui_write_nodes_trwgt.clear()
        assert isinstance(write_nodes, dict), "write_nodes argument must be a dict. Got: %s" % type(write_nodes)
        for write_node, selected in write_nodes.iteritems():
            tree_item = QtGui.QTreeWidgetItem([write_node])
            self.ui_write_nodes_trwgt.addTopLevelItem(tree_item)

            # If the node is selected in Nuke, then select it in the UI
            if selected:
                self.ui_write_nodes_trwgt.setItemSelected(tree_item, True)


    def getSelectedWriteNodes(self):
        '''
        Return the names of the write nodes that are selected in the UI
        '''
        return [item.text(0)for item in self.ui_write_nodes_trwgt.selectedItems()]

    def getUploadOnlyBool(self):
        '''
        Return whether the "Upload Only" checkbox is checked on or off.
        '''
        return self.ui_upload_only.isChecked()


    @QtCore.Slot(bool, name="on_ui_upload_only_toggled")
    def on_ui_upload_only_toggled(self, toggled):
        '''
        when the "Upload Only" checkbox is checked on, disable the Write 
        Nodes widget. when the "Upload Only" checkbox is checked off, enable
        the Write Nodes widget.
        '''
        self.ui_write_nodes_trwgt.setDisabled(toggled)




class NukeConductorSubmitter(submitter.ConductorSubmitter):
    '''
    The class is PySide front-end for submitting Nuke renders to Conductor.
    To launch the UI, simply call self.runUI method.
     
    '''

    _window_title = "Conductor - Nuke"

    @classmethod
    def runUi(cls):
        '''
        This
        '''
        ui = cls()
        ui.show()

    def __init__(self, parent=None):
        super(NukeConductorSubmitter, self).__init__(parent=parent)
        self.refreshUi()

    def initializeUi(self):
        super(NukeConductorSubmitter, self).initializeUi()


    def refreshUi(self):
        start, end = get_frame_range()
        self.setFrameRange(start, end)
        self.extended_widget.refreshUi()


    def getExtendedWidget(self):
        return NukeWidget()


    @QtCore.Slot(name="on_ui_submit_pbtn_clicked")
    def on_ui_submit_pbtn_clicked(self):
        print "Frame range: %s" % self.getFrameRangeString()
        print "Write Nodes:"
        for write_node in self.extended_widget.getSelectedWriteNodes():
            print "\t%s" % write_node



    def generateConductorCmd(self):
        '''
        Return the command string that Conductor will execute
        
        example:
            "nuke-render -X AFWrite.write_exr -F %f /Volumes/af/show/walk/shots/114/114_100/sandbox/mjtang/tractor/nuke_render_job_122/walk_114_100_main_comp_v136.nk"

        '''
        base_cmd = "nuke-render -F %%f %s %s"

        write_nodes = self.extended_widget.getSelectedWriteNodes()
        write_nodes_args = ["-X %s" % write_node for write_node in write_nodes]
        nuke_scriptpath = get_nuke_script_path()
        cmd = base_cmd % (" ".join(write_nodes_args), nuke_scriptpath)
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



def collect_dependencies(node_knobs, skip_unused=True):
    '''
    '''

    deps = {}

    unused = []
    if skip_unused:
        unused = get_unused_read_nodes()

    for node_type, dep_knobs in node_knobs.iteritems():

        for node in find_all_nodes(classfilter=(node_type)):

            if skip_unused and node in unused:
                continue

            for knob_name in dep_knobs:
                
                if knob_name in node.knobs():
                    
                    filename = node[knob_name].getValue()
                    
                    if filename:
                       
                        if '%' in filename or '#' in filename:
                            
#                             fileobj = afpipe.utils.FileSequence(filename)
                        else:
                            fileobj = afpipe.utils.File(filename)
        
                        fileid = fileobj.getId(resolveSymlink=True, conform_root=True)
        
                        if fileid not in deps:
                            deps[fileid] = Dependency(fileobj, item_class)
        
                        if node[knob_name] not in deps[fileid].knobs:
                            deps[fileid].knobs.append(node[knob_name])
        
                        if find_aovs and type(fileobj) == afpipe.utils.FileSequence:
                            aovs = fileobj.getAOVs()
                            for aov in aovs:
                                if aovs[aov].getId() not in deps:
                                   deps[aovs[aov].getId(resolveSymlink=True, conform_root=True)] = Dependency(aovs[aov], item_class)

    return deps



def get_files_from_seq_string(seq_str):
    '''
    From a given string that describes an image sequence, return a list of files
    that it encompasses. Only include files which exist on disk.
    Supports two different types of 
    
    seq_str: str
        /batman/beauty_v012.%04d.jpg
        /batman/beauty_v012.####.jpg
        
        /batman/beauty_v012.%04d.jpg
        /batman/beauty_v012.####.jpg
        
    
    '''
    delimiters = [".", "#"]
    
    percent_reg1 = r"%[\d]+d"
    percent_reg = r"%s(?P<filebase>[^%s\.]+)(?P<ext>\.[a-zA-Z]{1:2})" % (os.sep,os.sep)
    

def find_all_nodes(node=None, classfilter=None):
    results = []
    if node == None:
        node = nuke.Root()
    else:
        if classfilter is None or node.Class() in classfilter:
            results.append(node)
    try:
        for subnode in node.nodes():
            results += find_all_nodes(subnode, classfilter)
    except:
        pass
    return results


def get_node_dependencies(node, results=[]):

    for dep in node.dependencies():
        if dep not in results:
            results.append(dep)
            get_node_dependencies(dep, results)
    return results

def get_unused_read_nodes():

    results = []

    write_depends = []

    all_nodes = [n for n in nuke.root().nodes() if n]

    for write in [n for n in all_nodes if n.Class() in ['Write', 'DeepWrite']]:
        write_depends += get_node_dependencies(write)

    for read in [n for n in all_nodes if n.Class() in ['Read', 'DeepRead']]:
        if read not in write_depends:
            results.append(read)

    return results



def get_nuke_script_path():
    filepath = nuke.root().name()
    if not filepath or not os.path.isfile(filepath):
        raise Exception("Nuke script has not been saved to a file location.  Please save file before submitting to Conductor.")
    return filepath

def get_frame_range():
    '''
    Return the frame range found in Nuke's Project settings.
    '''
    first_frame = int(nuke.Root()['first_frame'].value() or 0)
    last_frame = int(nuke.Root()['last_frame'].value() or 0)
    return first_frame, last_frame


def get_all_write_nodes():
    '''
    Return a dictionary of all Write and Deep Write nodes that exist in the current
    Nuke script.  The dictionary key is the node name, and the value (bool) indicates
    whether the node is currently selected or not.
    '''
    write_nodes = nuke.allNodes(filter="Write")
    write_nodes.extend(nuke.allNodes(filter="DeepWrite"))
    selected_nodes = nuke.selectedNodes()
    node_names = dict([(node.name(), bool(node in selected_nodes)) for node in write_nodes])
    return node_names

