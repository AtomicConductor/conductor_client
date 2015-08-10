import Queue
import thread
from threading import Thread


import conductor, conductor.setup

from conductor.lib import api_client, common

'''
Abstract worker class.

The class defines the basic function and data structures that all workers need.

TODO: move this into it's own lib
'''
class ThreadWorker():
    def __init__(self, in_queue, out_queue=None):
        # the in_queue provides work for us to do
        self.in_queue = in_queue

        # results of work are put into the out_queue
        self.out_queue = out_queue

        self.api_client = api_client.ApiClient()

    '''
    This ineeds to be implmented for each worker type. The work task from
    the in_queue is passed as the job argument.

    Returns the result to be passed to the out_queue
    '''
    def do_work(self,job):
        raise NotImplementedError

    # Basic thread target loop.
    def target(self):
        # logger.debug('on target')
        while not common.SIGINT_EXIT:
            try:
                # this will block until work is found
                job = self.in_queue.get(True)

                # start working on job
                output = self.do_work(job)

                # put result in out_queue
                if output and self.out_queue:
                    self.out_queue.put(output)

                # signal that we are done with this task (needed for the
                # Queue.join() operation to work.
                self.in_queue.task_done()

            except Exception:
                logger.error(traceback.print_exc())
                logger.error(traceback.format_exc())

    '''
    Start number_of_threads threads.
    '''
    def start(self,number_of_threads=1):
        for i in range(number_of_threads):
            # thread will begin execution on self.target()
            thd = Thread(target = self.target)

            # make sure threads don't stop the program from exiting
            thd.daemon = True

        # start thread
            thd.start()
