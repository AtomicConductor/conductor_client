import Queue
import thread
import traceback
from threading import Thread


import conductor, conductor.setup

from conductor.setup import CONFIG, logger
from conductor.lib import api_client, common


'''
This is used to signal to workers if work should continue or not
'''
WORKING=True


'''
Abstract worker class.

The class defines the basic function and data structures that all workers need.

TODO: move this into it's own lib
'''
class ThreadWorker():
    def __init__(self, in_queue, out_queue=None, error_queue=None):
        # the in_queue provides work for us to do
        self.in_queue = in_queue

        # results of work are put into the out_queue
        self.out_queue = out_queue

        # exceptions will be put here if provided
        self.error_queue = error_queue

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
                try:
                    output = self.do_work(job)
                except Exception, e:
                    if self.error_queue:

                        error_message = traceback.format_exc()
                        self.mark_done()
                        self.error_queue.put(error_message)
                        continue
                    else:
                        raise e

                # put result in out_queue
                self.put_job(output)

                # signal that we are done with this task (needed for the
                # Queue.join() operation to work.
                self.mark_done()

            except Exception:
                logger.error('+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=')
                logger.error('+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=')
                logger.error('+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=')
                logger.error('+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=')
                logger.error('+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=')
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


    def mark_done(self):
        try:
            self.in_queue.task_done()
        except ValueError:
            # this will happen if we are draining queues
            if WORKING:
                # this should not happen if we are still working
                raise
        return



    def put_job(self,job):
        # don't to anything if we were not provided an out_queue
        if not self.out_queue:
            return
        # dont create jobs with None or empty things
        if not job:
            return
        # if were not supposed to be working, don't create new jobs
        if not WORKING:
            return

        # add item to job
        self.out_queue.put(job)
        return True
