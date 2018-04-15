
from conductor.lib import common


def on_create(node):
    node.parm('local_upload').set(
        int(common.Config().get_user_config().get('local_upload', True)))
