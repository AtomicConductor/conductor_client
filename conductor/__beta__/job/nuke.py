import logging

from . import job

LOG = logging.getLogger(__name__)

class NukeRenderJob(job.Job):
    
        def __init__(self, scene_path=None, *args , **kwargs):
            
            super(NukeRenderJob, self).__init__(*args, **kwargs)
            
            self.cmd = "nuke-render"
            self.scene_path = scene_path            
            self.upload_paths.append(scene_path)
            self.additional_cmd_args = ""
            self.pre_task_cmd = ""
            self.post_task_cmd = ""
            self.post_job_cmd = None
            self.chunk_size = None
            self.argv = ""

        def _get_task_data(self):

            task_data = []
            
            frames = range(self.start_frame, self.end_frame+1)
            
            if self.chunk_size is None:
                self.chunk_size =  len(frames)

            LOG.debug("Using a chunk size of {}".format(self.chunk_size))
            LOG.debug("Frames: {}".format(frames))

            for start in range(0, len(frames), self.chunk_size):
                chunk_frames = frames[start:start+self.chunk_size]
                start_frame = chunk_frames[0]
                end_frame = chunk_frames[-1]
                
                command_args = {'cmd': self.cmd,
                                'start_frame': start_frame,
                                'end_frame': end_frame,
                                'frame_step': self.frame_step,
                                'scene_path': self.scene_path,
                                'extra_args': self.additional_cmd_args,
                                'argv': self.argv,
                                'pre_task_cmd': self.pre_task_cmd,
                                'post_cmd': self.post_task_cmd}
                
                task_data.append({"frames": "{}-{}".format(start_frame, end_frame),
                                  "command": "{pre_task_cmd}; {cmd} -x -F {start_frame}-{end_frame}x{frame_step} {extra_args} {scene_path} {argv} && {post_cmd}".format(**command_args)})
                
            if self.post_job_cmd is not None:
                task_data.append({"frames": "999999", 
                                  "command": self.post_job_cmd})
                
                self.scout_frames = ",".join([str(f) for f in frames])
                
            return task_data