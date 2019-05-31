'''
Example usage from within Modo's script editor

from conductor.lib import api_client, conductor_submit, modo_utils
reload(conductor_submit)
reload(modo_utils)
from conductor import submitter

packages = api_client.request_software_packages()
modo_package = [package for package in packages if package["product"] == "modo"][0]

PROJECT_DIR="/home/lschlosser/modo/checkpointvfx"
RENDER_SCRIPT_FILEPATH="/home/lschlosser/git/conductor_client/samples/resources/modo/render.py"
OUTPUT_PATH="/tmp/render"

job_args = {
    "autoretry_policy": { "preempted": { "max_retries": 5}},
    "cores": 2,
#    "job_title": "whatever you want your job title to be",
    "local_upload": False,
    "machine_type": "standard",
    "output_path": OUTPUT_PATH,
    "project": "default",
    "preemptible": True,
    "scout_frames": "1,12,24",
    "software_package_ids": [modo_package["package_id"]],
    "upload_paths": [
        PROJECT_DIR,
        RENDER_SCRIPT_FILEPATH,
    ]
}

task_args = {

    # ----- Required ------

    # The path to the render.py file. This gets executed on conductor.
    render_script_filepath": RENDER_SCRIPT_FILEPATH,

    # ---- optional -------
    # "chunk_size": 1,
    "frames": "1-24", # can take other formats as well, e.g. "1-5x2,12,14",
    # "modo_filepath": r"S:\conductor\modo.xlo",
    # "res_x": 1920,
    # "res_y": 1080,
    "file_format": "openexr_32",
    "project_dir": PROJECT_DIR,
    "output_pattern": "[_<pass>.][<output>.][<LR>.]<FFFF>",
    # "render_pass_group": "render pass group name",
}


submission = modo_utils.ModoSubmit(job_args, **task_args)
response, response_code = submission.main()

print response_code
print response
'''

import logging
import os
import pipes

import lx
import modo

from conductor.lib.lsseq import seqLister
from conductor import submitter
from conductor.lib import api_client, conductor_submit, file_utils, package_utils

# Reassign for brevity. unfortunately we can't import from the symbol module bc it's a builtin
C = lx.symbol

logger = logging.getLogger(__name__)


class ModoSubmit(conductor_submit.Submit):

    def __init__(self, job_args, **task_args):
        self._scene = modo.Scene()

        assert "output_path" in job_args, 'Missing "output_path" arg'
        job_args["output_path"] = massage_path(job_args["output_path"], nodrive=False, quote=False)

        if 'tasks_data' not in job_args:
            task_args['output_path'] = massage_path(job_args["output_path"], nodrive=True, quote=True)

            if 'frames' not in task_args:
                task_args['frames'] = self.get_frames_str()

            if 'modo_filepath' not in task_args:
                task_args['modo_filepath'] = self.get_modo_filepath()

            lx.out("task_args: %s" % task_args)
            job_args['tasks_data'] = self.generate_tasks_data(**task_args)

        if 'job_title' not in job_args:
            job_args["job_title"] = "MODO %s" % os.path.basename(task_args['modo_filepath'])

        if 'environment' not in job_args:
            all_packages = api_client.request_software_packages()
            package_ids = job_args["software_package_ids"]
            job_packages = [package for package in all_packages if package["package_id"] in package_ids]
            # merge the packages' environments with the custom environment
            job_args["environment"] = package_utils.merge_package_environments(job_packages, base_env={})

        super(ModoSubmit, self).__init__(job_args)

    def get_modo_filepath(self):
        return self._scene.filename

    def get_frames_str(self):

        render_item = self._scene.renderItem
        frames = []
        range_iter = lx.object.IntRange(render_item.channel(C.sICHAN_POLYRENDER_FRMRANGE).get())
        while True:
            try:
                frames.append(range_iter.Next())
            except RuntimeError:
                break

        if frames:
            return ", ".join(seqLister.condenseSeq(frames))

        return '{start_frame}-{end_frame}x{step}'.format(
            start_frame=render_item.channel(C.sICHAN_POLYRENDER_FIRST).get(),
            end_frame=render_item.channel(C.sICHAN_POLYRENDER_LAST).get(),
            step=render_item.channel(C.sICHAN_POLYRENDER_STEP).get(),
        )

    def generate_tasks_data(self, modo_filepath, output_path, render_script_filepath, frames, chunk_size=1, project_dir=None, res_x=None, res_y=None, file_format=None, output_pattern=None, render_pass_group=None):
        '''
        Ultimately we want to generate command that each task will execute, e.g.

        modo_cl -dboff:crashreport -cmd:@/tmp/render.py" --modo-filepath /tmp/Scenes/modo_scene.lxo --output-path /tmp/output --frame-start 1 --frame-end 1 --frame-step 1 --project-dir /tmp --file-format openexr_32 --output-pattern '.[<pass>.][<output>.][<LR>.]<FFFF>'"
        '''
        logger.debug("modo_filepath: %s", modo_filepath)
        logger.debug("output_path: %s", output_path)
        logger.debug("render_script_filepath: %s", render_script_filepath)
        logger.debug("frames: %s", frames)
        logger.debug("chunk_size: %s", chunk_size)
        logger.debug("project_dir: %s", project_dir)
        logger.debug("res_x: %s", res_x)
        logger.debug("res_y: %s", res_y)
        logger.debug("file_format: %s", file_format)
        logger.debug("output_pattern: %s", output_pattern)
        logger.debug("render_pass_group: %s", render_pass_group)

        frames_list = seqLister.expandSeq(frames.split(","), None)

        cmd_template = (
            'modo_cl -dboff:crashreport -cmd:@{render_script_filepath}'
            '"'
            ' --modo-filepath {modo_filepath}'
            ' --output-path {output_path}'
            ' --frame-start {frame_start}'
            ' --frame-end {frame_end}'
            ' --frame-step {frame_step}'
            '{project_dir}'
            '{res_x}'
            '{res_y}'
            '{file_format}'
            '{output_pattern}'
            '{render_pass_group}'
            '"'
        )

        # Use the task frames generator to dispense the appropriate amount of
        # frames per task, generating a command for each task to execute
        tasks_data = []
        frames_generator = submitter.TaskFramesGenerator(frames_list, chunk_size=chunk_size, uniform_chunk_step=True)
        for start_frame, end_frame, step, task_frames in frames_generator:
            task_cmd = cmd_template.format(
                render_script_filepath=massage_path(render_script_filepath),
                modo_filepath=massage_path(modo_filepath),
                output_path=massage_path(output_path),  # windows pathing hack
                frame_start=start_frame,
                frame_end=end_frame,
                frame_step=step,
                project_dir=(' --project-dir %s' % massage_path(project_dir)) if project_dir is not None else "",
                res_x=(' --res-x %s' % res_x) if res_x is not None else "",
                res_y=(' --res-y %s' % res_y) if res_y is not None else "",
                file_format=(' --file-format %s' % file_format) if file_format is not None else "",
                output_pattern=(' --output-pattern %s' % massage_path(output_pattern)) if output_pattern is not None else "",
                render_pass_group=(' --render-pass-group %s' % render_pass_group) if render_pass_group is not None else "",
            )

            # Generate tasks data
            # convert the list of frame ints into a single string expression
            # TODO:(lws) this is silly. We should keep this as a native int list.
            task_frames_str = ", ".join(seqLister.condenseSeq(task_frames))
            tasks_data.append({"command": task_cmd,
                               "frames": task_frames_str})
        return tasks_data


def massage_path(path, quote=True, nodrive=True):
    if nodrive:
        path = file_utils.strip_drive_letter(path)
    path = os.path.expandvars(path)
    path = os.path.normpath(path).replace('\\', "/")
    if quote:
        path = pipes.quote(path)
    return path
