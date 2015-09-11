import Queue
import thread
import traceback
import threading
# from threading import Thread


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
    def __init__(self, in_queue, out_queue=None, error_queue=None, metric_store=None):
        # the in_queue provides work for us to do
        self.in_queue = in_queue

        # results of work are put into the out_queue
        self.out_queue = out_queue

        # exceptions will be put here if provided
        self.error_queue = error_queue

        self.threads = []

        # an optional metric store to share counters between threads
        self.metric_store = metric_store

    '''
    This ineeds to be implmented for each worker type. The work task from
    the in_queue is passed as the job argument.

    Returns the result to be passed to the out_queue
    '''
    def do_work(self,job):
        raise NotImplementedError

    def PosionPill(self):
        return 'PosionPill'

    def check_for_posion_pill(self,job):
        if job == self.PosionPill():
            self.mark_done()
            exit()

    def kill(self,block=False):
        logger.debug('killing workers %s', self.__class__.__name__)
        for _ in self.threads:
            self.in_queue.put(self.PosionPill())

        if block:
            for index, thd in enumerate(self.threads):
                logger.debug('waiting for thread %s', index)
                thd.join()

        # TODO
        # self.threads = []

        return True

    def join(self):
        self.in_queue.join()
        self.kill(True)

    # Basic thread target loop.
    def target(self):
        # logger.debug('on target')
        while not common.SIGINT_EXIT:
            try:
                # this will block until work is found
                job = self.in_queue.get(True)

                # exit if we were passed 'PosionPill'
                self.check_for_posion_pill(job)

                # start working on job
                try:
                    output = None
                    output = self.do_work(job)
                except Exception, e:
                    if self.error_queue:
                        self.mark_done()
                        error_message = traceback.format_exc()
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
        if self.threads:
            return self.threads

        for i in range(number_of_threads):
            # thread will begin execution on self.target()
            thd = threading.Thread(target = self.target)

            # make sure threads don't stop the program from exiting
            thd.daemon = True

            # start thread
            thd.start()
            self.threads.append(thd)

        return self.threads

    def mark_done(self):
        try:
            self.in_queue.task_done()
        except ValueError:
            # this will happen if we are draining queues
            logger.debug('WORKING: %s', WORKING)
            if WORKING:
                logger.error('error hit when marking task_done')
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


class MetricStore():
    '''
    This provides a thread-safe integer store that can be used by workers to
    share atomic counters.

    Note: writes are eventually consistent
    '''

    def __init__(self):
        self.metrics = {}
        self.update_queue = Queue.Queue()
        self.started = False

    def start(self):

        '''
        needs to be single-threaded for atomic updates
        '''
        if self.started:
            logger.debug('metric_store already started')
            return None
        logger.debug('starting metric_store')
        thd = threading.Thread(target=self.target)
        thd.daemon = True
        thd.start()
        self.started = True
        return thd

    def set(self, variable, value):
        self.metrics[variable] = value

    def get(self, variable):
        return self.metrics.get(variable,0)

    def increment(self, variable, step_size = 1):
        self.update_queue.put((variable, step_size))

    def target(self):
        logger.debug('created metric_store target thread')
        while True:
            # block until update given
            variable, step_size = self.update_queue.get(True)

            # initialize variable to 0 if not set
            if not self.metrics.has_key(variable):
                self.metrics[variable] = 0

            # increment variable by step_size
            self.metrics[variable] += step_size

            # mark task done
            self.update_queue.task_done()


class JobManager():
    '''

    '''

    def __init__(self, job_description):
        self.error = None
        self.workers = []
        self.error_queue = Queue.Queue()
        self.metric_store = MetricStore()
        self.work_queues = [Queue.Queue()]
        self.job_description = job_description

    def drain_queues(self):
        logger.error('draining queues')
        # http://stackoverflow.com/questions/6517953/clear-all-items-from-the-queue
        for queue in self.work_queues:
            queue.mutex.acquire()
            queue.queue.clear()
            queue.mutex.release()
        return True

    def mark_all_tasks_complete(self):
        logger.error('clearing out all tasks')
        # http://stackoverflow.com/questions/6517953/clear-all-items-from-the-queue
        for queue in self.work_queues:
            queue.mutex.acquire()
            queue.all_tasks_done.notify_all()
            queue.unfinished_tasks = 0
            queue.mutex.release()
        return True

    def kill_workers(self):
        # WORKING = False
        for worker in self.workers:
            worker.kill(block=False)

    def stop_work(self):
        global WORKING
        WORKING = False                # stop any new jobs from being created
        self.drain_queues()            # clear out any jobs in queue
        self.kill_workers()            # kill all threads
        self.mark_all_tasks_complete() # reset task counts

    def error_handler_target(self):
        while True:
            error = self.error_queue.get(True)
            if self.error:
                self.error += '#' * 80 + '\n'
            else:
                self.error = ''
            self.error += error
            self.stop_work()
            try:
                self.error_queue.task_done()
            except ValueError:
                pass

    def start_error_handler(self):
        logger.debug('creating error handler thread')
        thd = threading.Thread(target = self.error_handler_target)
        thd.daemon = True
        thd.start()
        return None

    def add_task(self,task):
        self.work_queues[0].put(task)
        return True

    def start(self):
        global WORKING
        WORKING = True

        # start shared metric store
        self.metric_store.start()

        # create error handler
        self.start_error_handler()

        # create worker pools based on job_description
        last_queue = self.work_queues[0]
        last_worker = next(reversed(self.job_description))
        for worker_class, thread_count in self.job_description.items():
            if last_worker == worker_class:
                # the last worker does not need an output queue
                next_queue = None
            else:
                next_queue = Queue.Queue()
                self.work_queues.append(next_queue)

            worker = worker_class(last_queue,
                                  next_queue,
                                  self.error_queue,
                                  self.metric_store)
            logger.debug('starting worker %s', worker_class.__name__)
            worker_threads = worker.start(thread_count)
            self.workers.append(worker)
            last_queue = next_queue

        return True

    def join(self):
        ''' Block untill all work is complete '''
        # for index, queue in enumerate(self.work_queues):
        #     worker_class_name = self.workers[index].__class__.__name__
        #     logger.debug('waiting for %s workers to finish', worker_class_name)
        #     queue.join()
        for index, worker in enumerate(self.workers):
            worker_class_name = worker.__class__.__name__
            logger.debug('waiting for %s workers to finish', worker_class_name)
            worker.join()
        logger.debug('all workers finished')
        if self.error:
            return self.error
        self.kill_workers()
        return True

    def metric_store(self):
        return self.metric_store

    def worker_queue_status_text(self):
        msg = '\n' + '#' * 80 + '\n'
        for index, worker_class in enumerate(self.job_description):
            q_size = self.work_queues[index].qsize()
            worker_threads = self.workers[index].threads
            num_active_threads = len([thd for thd in worker_threads if thd.isAlive()])
            msg += '%s \titems in queue: %s' % (q_size, worker_class.__name__)
            msg += '\t\t%s threads' % num_active_threads
            msg += '\n'
        return msg
