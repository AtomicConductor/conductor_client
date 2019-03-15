"""Script to be added to Clarisse's list of startup scripts.

It registers the conductor_job class in Clarisse.
"""

# from ix.api import  ModuleScriptedClass
import ix
from ix.api import OfAttr, OfObjectFactory


from conductor.clarisse.scripted_class.conductor_job import ConductorJob

ix.api.ModuleScriptedClass.register_scripted_class(
    ix.application, "ConductorJob", ConductorJob())
  
# c_class = ix.application.get_factory().get_classes().get("ConductorJob")
# c_attr = c_class.get_attribute("task_template") 
# # c_class.get_attribute("preemptible").set_bool(False)
# # c_class.get_attribute("preemptible").set_bool(True)

# expr = ""cnode "+get_string("render_package[0]")+" -image "+$CT_SOURCE+" -image_frames_list "+$CT_CHUNK"
# c_attr.set_expression(expr)

# expr = "$CTEMP"
# attr.set_string(expr)
# attr.set_expression(expr)




