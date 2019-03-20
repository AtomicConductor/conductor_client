# import ix
# from conductor.native.lib.sequence import Sequence


# def attribute_sequence(attr, **kw):
#     """Get the sequence associated with a filename attribute.

#     Many attributes have an associated sequence_mode attribute, which
#     when set to 1 signifies varying frames, and makes availabel start,
#     end, and offset attributes to help in specifying the sequence.

#     If the keyword intersector is given, then work out the intersection 
#     with it. Why? Because during dependency scanning, we can optimize
#     the number of frames to upload if we use only those frames specified
#     in the sequence attribute, and intersect them with the frame range
#     specified in the job node.
#     """
#     intersector = kw.get("intersector")

#     obj = attr.get_parent_object()
#     mode_attr = obj.attribute_exists("sequence_mode")
#     if not (mode_attr and mode_attr.get_long()):
#         # This attribute cannot be expanded to a time sequence
#         return None

#     global_frame_rate = ix.application.get_prefs(
#         ix.api.AppPreferences.MODE_APPLICATION).get_long_value(
#         "animation", "frames_per_second")
#     attr_frame_rate = obj.get_attribute("frame_rate").get_long()
#     if not attr_frame_rate == global_frame_rate:
#         ix.log_error(
#             "Can't get attribute sequence when global \
#             fps is different from fps on the attribute")

#     start = obj.get_attribute("start_frame").get_long()
#     end = obj.get_attribute("end_frame").get_long()

#     if intersect:
#         offset = obj.get_attribute("frame_offset").get_long()
#         return Sequence(start, end, 1).offset(
#             offset).intersect(intersector).offset(-offset)

#     return Sequence(start, end, 1)
