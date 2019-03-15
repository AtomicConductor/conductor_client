import ix


def handle_optimize_scan(obj, attr):
    """Not really used yet."""
    hide = not attr.get_bool()
    obj.get_attribute("optimization_samples").set_hidden(hide)
