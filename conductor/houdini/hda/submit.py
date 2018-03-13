"""Entry point for job submission."""

from conductor.houdini.hda import submission


def dry_run(node, **_):
    """TODO in CT-59 generate request and open a panel.

    Should be instant and not mutate anything. Therefore, do
    not save a file or actually submit anything.

    """
    sub = submission.Submission(node)
    sub.dry_run()


def local(node, **_):
    print "LOCAL TEST"
    pass


def doit(node, **_):

    pass
