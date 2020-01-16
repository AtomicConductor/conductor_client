import logging

from . import job

LOG = logging.getLogger(__name__)

class MayaRenderJob(job.Job):
    
        def __init__(self, scene_path=None, project_path=None, *args , **kwargs):
            
            super(MayaRenderJob, self).__init__(*args, **kwargs)
            
            self.cmd = "Render"
            self.render_layer = "defaultRenderLayer"
            self.scene_path = scene_path
            self.project_path = project_path
            
            self.software_packages_ids = ["bcfe5df6e2361d77ca7d7b9da76e351b", "936dac0a489071942be623da35dd71fb"]
            self.upload_paths.append(scene_path)
            
        def _get_environment(self):
            return {"MAYA_PLUG_IN_PATH": "/opt/solidangle/arnold-maya/3/arnold-maya-maya2018-3.2.1-1./plug-ins", "MAYA_LOCATION": "/opt/autodesk/maya-io/2018/maya-io2018.SP6", "MAYA_LICENSE": "unlimited", "PYTHONPATH": "/opt/autodesk/maya-io/2018/maya-io2018.SP6/Conductor:/opt/solidangle/arnold-maya/3/arnold-maya-maya2018-3.2.1-1./scripts", "MAYA_DISABLE_CIP": "1", "MAYA_SCRIPT_PATH": "/opt/solidangle/arnold-maya/3/arnold-maya-maya2018-3.2.1-1./scripts", "solidangle_LICENSE": "4101@docker_host", "MAYA_RENDER_DESC_PATH": "/opt/solidangle/arnold-maya/3/arnold-maya-maya2018-3.2.1-1.", "PATH": "/opt/autodesk/maya-io/2018/maya-io2018.SP6/bin:/opt/solidangle/arnold-maya/3/arnold-maya-maya2018-3.2.1-1./bin", "ARNOLD_PLUGIN_PATH": "/opt/solidangle/arnold-maya/3/arnold-maya-maya2018-3.2.1-1./plug-ins", "LD_LIBRARY_PATH": "/opt/autodesk/maya-io/2018/maya-io2018.SP6/lib:/opt/autodesk/maya-io/2018/maya-io2018.SP6/plug-ins/xgen/lib:/opt/autodesk/maya-io/2018/maya-io2018.SP6/plug-ins/bifrost/lib"}
        
        def _get_task_data(self):
            
            {"frames": "1-2", "command": "Render  -s 1 -e 2 -b 1 -rl defaultRenderLayer -rd /tmp/render_output/ -proj \"C:/Users/jlehrman/Documents/maya/projects/conductor/\" \"/Users/jlehrman/Documents/maya/projects/conductor/simple_shapes.ma\""},

            [u'Render', u'-s', u'5', u'-e', u'5', u'-b', u'1', u'-rl', u'defaultRenderLayer', u'-rd', u'/tmp/render_output/', u'-proj', u'"C:/Users/jlehrman/Documents/maya/projects/conductor/"', u'"C:/Users/jlehrman/Documents/maya/projects/conductor/simple_shapes.ma"']
            
            LOG.debug("Using a chunk size of {}".format(self.chunk_size))
            
            task_data = []
            
            frames = range(self.start_frame, self.end_frame+1)
            
            LOG.debug("Frames: {}".format(frames))

            for start in range(0, len(frames), self.chunk_size):
                chunk_frames = frames[start:start+self.chunk_size]
                start_frame = chunk_frames[0]
                end_frame = chunk_frames[-1]
                
                command_args = {'cmd': self.cmd,
                                'start_frame': start_frame,
                                'end_frame': end_frame,
                                'frame_step': self.frame_step,
                                'render_layer': self.render_layer,
                                'output_path': self.output_path,
                                'project_path': self.project_path,
                                'scene_path': self.scene_path} 
                
                task_data.append({"frames": "{}-{}".format(start_frame, end_frame),
                                  "command": "{cmd} -s {start_frame} -e {end_frame} -b {frame_step} -rl {render_layer} -rd {output_path} -proj {project_path} -r arnold -ai:lve 2 {scene_path}".format(**command_args)})
                
            return task_data