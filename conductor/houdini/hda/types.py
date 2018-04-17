"""Differentiate between a job node and a submitter node."""


def is_job_node(node):
    return node.type().name().startswith("conductor::job")


def is_submitter_node(node):
    return node.type().name().startswith("conductor::submitter")
