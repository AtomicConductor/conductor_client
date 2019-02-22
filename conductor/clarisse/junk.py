import ix
kls =  ix.application.get_factory().get_classes().get("ConductorJob")
print kls.get_name()

project_att = kls.get_attribute("project")

num = project_att.get_preset_count()
print num
# project_att.add_preset("fooz", "6")

#project_att.set_long(1)




project_att.apply_preset("2")

project_att.remove_preset("foo")

print  project_att.get_preset_value("foo")

#for i in range(1,num, -1):
#        project_att.remove_preset(i)


#######################


import ix
kls =  ix.application.get_factory().get_classes().get("Locator")
print kls

#print type(ob)
#print ob.get_count()

objects = ix.api.OfObjectArray()
ix.application.get_factory().get_objects("ConductorJob", objects)
print objects.get_item(0).get_name()
print objects.get_count()
project_att = objects.get_item(0).get_attribute("project")
print project_att
#project_att.add_preset("blobby", "100")
project_att.apply_preset("blobby")


ob1 = ob.acquire()
print type(ob1)
ob.next()
ob1 = ob.aacquire()
print ob1.get_name()

kls.add_attribute(
    "asset_id",
    ix.api.OfAttr.TYPE_STRING,
    ix.api.OfAttr.CONTAINER_SINGLE,
    ix.api.OfAttr.VISUAL_HINT_DEFAULT,
     "Custom Attributes")


project_att = kls.get_attribute("project")

num = project_att.get_preset_count()
print num

project_att.remove_preset("foo")

print  project_att.get_preset_value("foo")





            # kls =  ix.application.get_factory().get_classes().get("ConductorJob")
            # print(object)
            # print dir(self.__class__.get_class_info())
            # print "-" * 20
            # print dir("get_class_info_id" , self.__class__.get_class_info_id())
            # print "-" * 20
            # print dir("get_class_info_name" , self.__class__.get_class_info_name())
            # print "-" * 20
            # print dir("get_class_interface" , self.__class__.get_class_interface())
            # print "-" * 20
            
 # 'get_class_info',
 # 'get_class_info_id',
 # 'get_class_info_name',
 # 'get_class_interface',

#for i in range(1,num, -1):
#        project_att.remove_preset(i)


 # project_att.apply_preset("Ellipsoid") 
    # print "SEL2:", project_att.get_applied_preset_index()
 
    # num = project_`att.get_preset_count()
    # print curr_label
    # print num
    # print project_att.get_long()
    # print project_att.get_preset_value(selected)

    # project_att.remove_all_presets()

 
    # if selected not in (project["id"] for project in projects):
    #     node.parm('project').set(projects[0]["id"])
    # res = [k for i in projects for k in (i["id"], i["name"])]
    # return res


 
    # entries = ["-- Select Project --", "foo", "bar", "baz", "hod" ] 


    # for i, entry in enumerate(entries):
    #      project_att.add_preset(entry, str(i+1))

    # project_att.apply_preset("foo")



# void    add_preset (const CoreString &preset_label, const CoreString &preset_value, const GuiIcon *icon=0)
#     Add a preset value to this attribute. 
 
# void    remove_preset (const CoreString &label)
#     Removes the preset, specified by its label, from this attribute. 
 
# void    remove_preset (const unsigned int &index)
#     Removes the preset, specified by its index, from this attribute. 
 
# void    remove_all_presets ()
#     Removes all presets from this attribute. 
 
# bool    has_preset () const
#     Returns true if this attribute has presets. 
 
# const unsigned int &    get_preset_count () const
#     Returns the number of preset values for this attribute. 
 
# CoreString  get_preset_label (const unsigned int &preset_index) const
#     Returns the label of the preset for the given index or an empty string if out of range. 
 
# CoreString  get_preset_value (const unsigned int &preset_index) const
#     Returns the value of the preset for the given index or an empty string if out of range. 
 
# const GuiIcon *     get_preset_icon (const unsigned int &preset_index) const
#     Returns the icon of the preset for the given index or a null pointer if out of range. 
 
# CoreString  get_preset_value (const CoreString &preset_label) const
#     Returns the value of the preset for the given label or an empty string if not found. 
 
# int     get_preset_index (const CoreString &preset_label) const
#     Returns the index of the preset for the given label or -1 if not found (quietly). 
 
# void    set_preset_label (const unsigned int &preset_index, const CoreString &preset_label)
 
# void    set_preset_value (const unsigned int &preset_index, const CoreString &preset_value)
 
# void    set_preset_value (const CoreString &preset_label, const CoreString &preset_value)
 
# void    apply_preset (const CoreString &preset_label)
#     Sets the value of this attribute by applying the preset matching the given label. 
 
# void    apply_preset (const unsigned int &preset_index)
#     Sets the value of this attribute by applying the preset at the given index. 
 
# unsigned int    get_applied_preset_index () const
#     Returns the index of the applied preset or -1 if the current value if not matching any preset. 
 
# CoreString  get_applied_preset_label () const
#     Returns the label of the applied preset or an empty string if the current value if not matching any preset. 
 
# void    get_preset_hints (CoreArray< bool > &hints) const
#     Gather an array of hints used by the UI to tag the presets. 

# elif action.get_name() == "addattr":
        #     print "I'm adding an attribute"
        # Do something when an attribute value is changing. To check 
        # which attribute is changing use the attribute name.
        # print "flags:"
        # print dirtiness_flags
        # print "dirtiness: ", dirtiness


            # print "-" * 20
            # # print self.this

            # print kls
            # print "-" * 20
            # print type(kls)
            # att = kls.get_attribute("project") 
            # att

            # print type(att)
            # print att.get_type()
            # print att.is_single()
            # print att.is_array()
            # print att.is_list()


            # kls.add_attribute("asset_id", ix.api.OfAttr.TYPE_STRING, ix.api.OfAttr.CONTAINER_SINGLE, ix.api.OfAttr.VISUAL_HINT_DEFAULT, "Custom Attributes")





# def on_refresh_obj(obj, data):
#     project_att = obj.get_attribute("project")
#     selected_index = project_att.get_applied_preset_index()
#     # print "selected", selected
#     on_refresh_project(obj)

#     if project_att.get_preset_value(selected):
#         print "found selected"
#         project_att.apply_preset(selected)
#     else:
#         print "set to 0"
#         project_att.apply_preset(0)



# kls = ix.application.get_factory().get_classes().get(self.__class__.__name__)

# setting the base attribute smooting angle of the polyfile class to 0.0
# kls.get_attribute("override_range").set_bool(True)

# on_refresh_class()

# on_initiate_class()


# class "my_class_name" "optional_base_class_name" {
#     //class properties

#     attribute_type "attribute_name1" {
#         //attribute properties
#     }
#     attribute_type "attribute_name2" {
#             //attribute properties
#     }
#     ...
#     attribute_group "attribute_group_name1" {
#         attribute_type "attribute_name3" {
#             //attribute properties
#         }
#         attribute_type "attribute_name4" {
#             //attribute properties
#         }
#         ...
#     }
#     attribute_group "attribute_group_name2"{
#         ...
#     }
#     ...
# }

# # getting the polyfile class
#    2 polymesh_class = ix.application.get_factory().get_classes().get("GeometryPolyfile")
#    3 # adding a custom attribute to the polymesh class
#    4 polymesh_class.add_attribute("asset_id", ix.api.OfAttr.TYPE_STRING, ix.api.OfAttr.CONTAINER_SINGLE, ix.api.OfAttr.VISUAL_HINT_DEFAULT, "Custom Attributes")
# 5 # now each time a polyfile is created it will have an extra attribute
# asset_id that will be saved in the project.


# add_action (OfClass &cls, const CoreString &action, const CoreString &category="General")
#     Binds a new action.

# virtual
# ModuleScriptedClassEngineData *     create_instance_data (OfObject &object)
# Return a dedicated instance data for this specific process. You must
# call ModuleProcessScriptEngineData::initialize_data before returning it!

# virtual void    declare_attributes (OfClass &cls)
# Allow to declare attributes of the class. Can be used as declare_cid
# alternative.

# virtual void    on_action (const OfAction &action, OfObject &object, void *data)
# Allow to declare attributes of the class. Can be used as declare_cid
# alternative.

# virtual void    on_attribute_change (OfObject &object, const OfAttr &attr, int &dirtiness, const int &dirtiness_flags)
#     Call when attributes of an instance are modified.

# bool    is_shared () const
# Return true is the engine is currently shared (has been registered).
# When an engine is shared, its deletion will be handled by the
# ModuleProcessScript.

# void    share ()
#     Used internally to track destruction.

#


