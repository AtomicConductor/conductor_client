import datetime
from contextlib import contextmanager
import hou
# from render_job import RenderJob
import hda


@contextmanager
def take_context(take):
    """Put houdini in the context of a take to run some code."""
    remember = hou.takes.currentTake()
    hou.takes.setCurrentTake(take)
    yield
    hou.takes.setCurrentTake(remember)


class Submission(object):

    def __init__(self, node, takes):
        self._submitter_node = node
        self._timestamp = datetime.datetime.now().strftime('%Y_%m_%d_%H_%M_%S')
        self._takes = takes or hda.takes.active_takes(node)
        self._project = node.parm('project').eval()
        self._source_node = hda.render_source.get_render_node(node)
        self._source_type = hda.render_source.get_render_type(node)

        if not self._takes:
            raise

    def view(self):
        submission = {
            "submitter_node": self._submitter_node,
            "timestamp": self.timestamp,
            "takes": self.takes,
            "project": self.project,
            "source_node": self.source_node,
            "source_type": self.source_type
        }
        jobs = []
        for take in self._takes:
            with take_context(take):
                job = hda.job.Job(self._submitter_node)
                print job.data()


 



        # win = 'broodSpoolWindow'
        # if pm.window(win, query=True, exists=True):
        #     pm.deleteUI(win)
        # pm.window(win, title='Brood Spool View Window')
        # tabs = pm.tabLayout()

        # for layer in self._layers:
        #     with take_context(layer):
        #         render_job = self._create()
        #         text = render_job.view()
        #         scroll = pm.scrollField(editable=False,
        #                                 wordWrap=False, text=text)
        #         pm.tabLayout(tabs, edit=True,
        #                      tabLabel=(scroll, utl.layer_name(layer)))

        # pm.showWindow()

    # def _create(self):
    #     """Create a job.

    #     We are in a layer context when this happens.

    #     """
    #     return RenderJob(self._dispatcher_node, self._timestamp)

    # def _get_layers(self):
    #     """Get the render layers.

    #     For now, the choice is current or allActive

    #     """
    #     layers = []
    #     if k.K_CURRENT_LAYER == self._dispatcher_node.renderLayers.get():
    #         layers.append(
    #             pm.editRenderLayerGlobals(q=True, currentRenderLayer=True))
    #     else:
    #         for layer in pm.ls(type='renderLayer'):
    #             if layer.renderable.get() is True:
    #                 if layer.find(":") == -1:
    #                     layers.append(layer)
    #     return layers
