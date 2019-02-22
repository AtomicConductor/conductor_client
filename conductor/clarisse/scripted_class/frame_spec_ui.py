def handle_use_custom_range(obj, attr):
    obj.get_attribute("frame_range").set_hidden( not attr.get_bool())
 
def handle_use_scout_range(obj, attr):
    obj.get_attribute("scout_range").set_hidden( not attr.get_bool())
 
