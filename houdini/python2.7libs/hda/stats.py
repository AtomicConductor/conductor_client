"""Cost estimation and frame stats.

The cost estimate part uses fake values and is currently
hidden.

Frame stats tells the user how many frames there
are, how many scout frames if scout selected, and how many
clumps will be generated with the current clump size.
TODO - put frame stats in frame_spec file or in its own file.

"""

import frame_spec

MACHINE_PRICE_MAP = {
    "standard_2": 1.0,
    "highmem_2": 1.12,
    "standard_4": 1.25,
    "highmem_4": 1.60,
    "highcpu_8": 1.72,
    "standard_8": 2.10,
    "highmem_8": 2.15,
    "highcpu_16": 2.20,
    "standard_16": 2.45,
    "highmem_16": 2.77,
    "highcpu_32": 2.80,
    "standard_32": 2.93,
    "highmem_32": 3.45,
    "highcpu_64": 3.61,
    "standard_64": 3.80,
    "highmem_64": 3.86
}

K_UNIT_OF_WORK = 0.01


def _get_estimate_message(node):
    """Generate estimate info string.

    This formula is a mock. Also estimate UI is currently
    hidden.

    """
    preemp_factor = 0.6 if node.parm("preemptible").eval() else 1.0

    mins_per_frame = node.parm("avg_frame_time").eval()
    if mins_per_frame < 1:
        return "Cant estimate: mins per frame is invalid"

    type_factor = MACHINE_PRICE_MAP.get(node.parm("machine_type").eval())
    if type_factor is None:
        type_factor = 1.0

    num_frames = len(frame_spec.frame_set(node))
    if not num_frames:
        return "Cant estimate: frame count is invalid"

    accumulated_mins = (num_frames * mins_per_frame)
    if not accumulated_mins:
        return "Cant estimate: accumulated mins is invalid"

    job_cost = K_UNIT_OF_WORK * type_factor * accumulated_mins * preemp_factor

    frame_cost = job_cost / num_frames

    return r"%s frames at $%0.2f each.     TOTAL: $%0.2f" % (
        num_frames, frame_cost, job_cost)


def update_estimates(node):
    """Update the estimate string parameter.

    Various params contribute to the estimate. They can this
    function to take care of the whole calculation

    """
    msg = _get_estimate_message(node)
    node.parm("cost_time_estimates").set(msg)


def avg_frame_time_changed(node, **_):
    """Call when average frame time slider changed.

    This will update the estimate

    """
    update_estimates(node)
