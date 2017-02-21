#
# Copyright (C) 2009 - 2015 Isotropix SAS. All rights reserved.
#
# The information in this file is provided for the exclusive use of
# the software licensees of Isotropix. Contents of this file may not
# be distributed, copied or duplicated in any form, in whole or in
# part, without the prior written permission of Isotropix SAS.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
# A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
# OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
# LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
# DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
# THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#

## @package export_render_package
# This file archives the current project and its all dependencies in a zip
# file
#
# LIMITATIONS
# The current script assumes all file are reachable
# It doesn't support UDIM/Image Sequence
# It must be extended to support error handling (file not found etc...)


import os.path, tempfile, shutil, zipfile, ix, platform


def get_clarisse_version():
    return ix.application.get_version()


def get_clarisse_images():
    render_images = ix.api.OfObjectArray()
    ix.application.get_factory().get_all_objects("Image", render_images)
    return render_images


def get_clarisse_layers():
    render_images = ix.api.OfObjectArray()
    ix.application.get_factory().get_all_objects("Image", render_images)
    layers = []
    for image in render_images:
        ll = image.attrs.layers
        for i in range(len(ll)):
            layers.append(ll[i].__str__())
    return layers


def get_clarisse_output_path():
    layers = get_clarisse_layers()
    output_paths = [str(get_clarisse_layer_output_path(layer)) for layer in layers]
    return os.path.commonprefix(output_paths)


def get_clarisse_output_paths():
    layers = get_clarisse_layers()
    output_paths = [str(get_clarisse_layer_output_path(layer)) for layer in layers]
    return output_paths


def get_clarisse_image_layers(image_name):
    image_obj = ix.application.get_factory().get_object(image_name)
    return image_obj.attrs.layers


def get_clarisse_layer_output_path(layer_name):
    layer_obj = ix.application.get_factory().get_object(layer_name)
    return layer_obj.attrs.save_as[0]


def get_frame_range():
    return ix.application.get_current_frame_range()


# create folders according to a path
def create_path(path):
    if not os.path.exists(path):
        l=[]
        p = "/"
        l = path.split("/")
        i = 1
        while i < len(l):
            p = p + l[i] + "/"
            i = i + 1
            if not os.path.exists(p):
                os.mkdir(p, 0755)


# localize all contexts so they are remote anymore
def make_all_context_local():
    # getting all contexts
    all_ctx = ix.api.OfContextSet()
    ix.application.get_factory().get_root().resolve_all_contexts(all_ctx)
    ref_ctxs = []

    for i in range(all_ctx.get_count()):
        ctx = all_ctx[i]
        # check if the context is a reference
        if ctx.is_reference():
            ref_ctxs.append(ctx)

    if len(ref_ctxs) > 0:
        for ctx in ref_ctxs:
            ix.cmds.MakeLocalContext(ctx)


def do_export():
    # extensions = 'All Known Files...\t*.{zip}\nZip Archive (*.zip)\t*.{zip}\n'
    extensions = 'All Known Files...\t*'
    dest_dir = '/var/tmp'
    if platform.system() == "Windows":
        dest_dir = ix.api.GuiWidget.save_file(ix.application, '', 'Select temp folder',extensions)

    # generating temp folder in Clarisse temp directory
    gen_tempdir = tempfile.mkdtemp('', '', dest_dir)
    # if dest_file[-4:] == ".zip": dest_file = dest_file[:-4]

    # dest_dir = os.path.dirname(dest_file)
    # if dest_file == '' or not os.path.isdir(dest_dir):
    #     if dest_file == '':
    #         pass # cancel
    #     else:
    #         ix.log_error("The specified directory is invalid")
    #     return
    # else:
    ix.enable_command_history()
    ix.begin_command_batch("ExportRenderPackage()")
    # first we flatten all contexts
    make_all_context_local()

    # then we gather all external file resources
    unique_files = {}
    attrs = ix.api.OfAttr.get_path_attrs()
    new_file_list = []
    attr_list = []
    scene_info = {"output_path": ""}
    for i in range(attrs.get_count()):
        # deduplicating
        file = attrs[i].get_string()
        print file
        if not os.path.isfile(file):
            #  Find the output path...
            if attrs[i].get_name() == "save_as":
                scene_info['output_path'] = os.path.dirname(file)

            print("Skipping file %s" % file)
            continue
        attr_list.append(attrs[i].get_full_name())
        if not file in unique_files:
            # de-windoify path
            print "abs path: %s" % os.path.abspath(file)
            new_filename = os.path.abspath(file)
            # new_filename = os.path.abspath(file).replace("\\", '/').replace(':', '').replace('\\\\', '/')
            # new_filename = gen_tempdir + new_filename
            # getting the absolute path of the file
            # if (not platform.system == "Windows" and not new_filename.startswith("/")) and \
            #         not new_filename.startswith("$PDIR") and \
            #         not new_filename.startswith("$CDIR"):
            # new_filename = "$PDIR/" + new_filename
            unique_files[file] = new_filename
            new_file_list.append(new_filename)
            print "became %s" % new_filename
        else:
            new_file_list.append(unique_files[file])

    # updating attribute path with new filename
    ix.enable_command_history()

    ix.log_info("saving project file...")
    ix.application.check_for_events()
    name = ix.application.get_current_project_filename()
    name = os.path.basename(name)
    if name == '':
        name = "Untitled.project"

    if name.endswith(".project"):
        name = name[:-8] + ".render"
    else:
        name += ".render"

    # ix.application.export_context_as_project(gen_tempdir + '/' + name, ix.application.get_factory().get_root())
    # restoring file attributes with original paths

    # copying files in new directory
    # return_files = [gen_tempdir + '/' + name]
    scene_info["scene_file"] = os.path.join(gen_tempdir, name)
    scene_info["dependencies"] = [scene_info["scene_file"]]
    for file in unique_files:
        target = unique_files[file]
        if target.startswith("$PDIR") or target.startswith("$CDIR"):
            target = unique_files[file][5:]
        # target_dir = gen_tempdir + os.path.dirname(target)
        target_dir = os.path.dirname(target)
        if not os.path.isdir(target_dir):
            os.makedirs(target_dir)
        ix.log_info("copying file '" + file + "' to " + target + "..." )
        ix.application.check_for_events()
        # new_path = gen_tempdir + target
        scene_info["dependencies"].append(target)
        # if platform.system() == "Windows":
        #     shutil.copyfile(file, target)
        # else:
        #     os.symlink(file, target)

    ix.cmds.SetValues(attr_list, new_file_list)
    ix.application.export_context_as_project(scene_info["scene_file"], ix.application.get_factory().get_root())
    ix.application.export_render_archive(scene_info["scene_file"])

    #  The stuff that is commented out packages the dependencies into an archive
    #  this is something we do not support at the moment, but I'm leaving around 
    #  for future reference...

    # ix.log_info("building archive...")
    ix.application.check_for_events()
    # shutil.make_archive(dest_file, 'zip', gen_tempdir)
    # ix.log_info("cleaning temporary files...")
    # ix.application.check_for_events()
    # shutil.rmtree(gen_tempdir)
    # ix.log_info("Package successfully exported in '" + dest_file + ".zip'.")
    ix.end_command_batch()
    # # restore original state
    ix.application.get_command_manager().undo()
    ix.disable_command_history()

    print("Dependencies: ")
    for filename in scene_info["dependencies"]:
        print("\t%s" % filename)

    return scene_info