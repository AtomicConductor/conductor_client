import ix
from conductor.native.lib.sequence import Sequence

def handle_use_custom_frames(obj, attr):
    obj.get_attribute("custom_frames").set_hidden( not attr.get_bool())
    _validate_frame_range_atts(obj)
 
def handle_use_scout_frames(obj, attr):
    obj.get_attribute("scout_frames").set_hidden( not attr.get_bool())
    _validate_frame_range_atts(obj)
  
def handle_frames_atts(obj, _):
    _validate_frame_range_atts(obj)

def _validate_spec(attr):
    spec = attr.get_string()
    if spec and Sequence.is_valid_spec(spec):
        return
    msg = "{} Invalid frame spec.\nFormat should be \"2\" or \"1-5x2\" or \"2,5,6, 9-11, 20-30x2\"".format(attr.get_name())
    ix.log_warning(msg)

def _validate_frame_range_atts(obj):
    for field in ["custom", "scout"]:
        use_att = obj.get_attribute("use_{}_frames".format(field)) 
        if use_att.get_bool():
            _validate_spec(obj.get_attribute("{}_frames".format(field)))
 