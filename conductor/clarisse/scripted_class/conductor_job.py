import ix
from conductor.native.lib.data_block import ConductorDataBlock
from conductor.clarisse.scripted_class import cid
from conductor.clarisse.scripted_class import projects_ui
from conductor.clarisse.scripted_class import instances_ui
from conductor.clarisse.scripted_class import frame_spec_ui
from conductor.clarisse.scripted_class import variables
  
class ConductorJob(ix.api.ModuleScriptedClassEngine):

    def __init__(self):
        ix.api.ModuleScriptedClassEngine.__init__(self)
        print "RUN ConductorJob INIT"

    def on_action(self, action, obj, data):
        if action.get_name() == "submit":
            window = ix.api.GuiWindow(ix.application, 0, 0, 640, 480)
            lv = ix.api.GuiListView(window, 0, 0, 640, 480)
            lv.add_item("Foo")
            lv.add_item("Bar")
            lv.add_item("Baz")
            lv.add_item("Maya 24")
            window.show()
            while window.is_shown(): 
                ix.application.check_for_events()
    
        elif action.get_name() == "preview":
            print "I'm showing you the script"
        elif action.get_name() == "refresh":
            on_refresh_clicked(obj, data)
        else:
            print "Unknown action"

    def on_attribute_change(self, obj, attr, dirtiness, dirtiness_flags):
        attr_name = attr.get_name()

        if attr_name == "project":
            projects_ui.handle_project(obj, attr)
        elif attr_name == "use_custom_frames":
            frame_spec_ui.handle_use_custom_frames(obj, attr)
        elif attr_name == "use_scout_frames":
            frame_spec_ui.handle_use_scout_frames(obj, attr)
        elif attr_name == "custom_frames":
            frame_spec_ui.handle_frames_atts(obj, attr)
        elif attr_name == "scout_frames":
            frame_spec_ui.handle_frames_atts(obj, attr)

            
        elif attr_name == "source":
            print "source is:"
            print attr.get_object(0)

    def declare_attributes(self, cls):
        self.add_action(cls, "refresh", "status")
        self.add_action(cls, "preview", "actions")
        self.add_action(cls, "submit", "actions")

def on_refresh_clicked(obj, _):
    data_block = ConductorDataBlock(product="clarisse", force=True)
    projects_ui.refresh(obj, data_block)
    instances_ui.refresh(obj, data_block)
    variables.refresh()
 
# Register our class to Clarisse with the supplied implementation

ix.api.ModuleScriptedClass.register_scripted_class(
    ix.application, "ConductorJob", ConductorJob(), cid.JOB)

kls =  ix.application.get_factory().get_classes().get("ConductorJob")
# kls.get_attribute("frame_range").set_locked(True)
   