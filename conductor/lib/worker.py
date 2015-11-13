import collections
import Queue
import thread
import traceback
import threading

import conductor, conductor.setup

from conductor.setup import CONFIG, logger
from conductor.lib import api_client, common


'''
This is used to signal to workers if work should continue or not
'''
WORKING = True


class Reporter():
    def __init__(self, metric_store=None):
        self.metric_store = metric_store
        self.api_helper = api_client.ApiClient()
        self.thread = None
        self.terminate = False

    def kill(self, block=False):
        self.terminate = True
        if block:
            logger.debug('joining reporter thread...')
            self.thread.join()
            logger.debug('reporter_thread exited')

    def working(self):
        return WORKING

    def target(self):
        raise 'not implmented'

    def start(self):
        if self.thread:
            logger.error('threads already started. will not start more')
            return self.thread

        logger.debug('starting reporter thread')
        thd = threading.Thread(target=self.target)
        thd.daemon = True
        thd.start()
        self.thread = thd
        return self.thread



'''
Abstract worker class.

The class defines the basic function and data structures that all workers need.

TODO: move this into it's own lib
'''
class ThreadWorker():
    def __init__(self,**kwargs):

        # the in_queue provides work for us to do
        self.in_queue = kwargs['in_queue']

        # results of work are put into the out_queue
        self.out_queue = kwargs['out_queue']

        # exceptions will be put here if provided
        self.error_queue = kwargs['error_queue']

        # set the thread count (default: 1)
        self.thread_count = int(kwargs.get('thread_count',1))

        # an optional metric store to share counters between threads
        self.metric_store = kwargs['metric_store']

        # create a list to hold the threads that we create
        self.threads = []

    '''
    This ineeds to be implmented for each worker type. The work task from
    the in_queue is passed as the job argument.

    Returns the result to be passed to the out_queue
    '''
    def do_work(self, job):
        raise NotImplementedError

    def PosionPill(self):
        return 'PosionPill'

    def check_for_posion_pill(self, job):
        if job == self.PosionPill():
            self.mark_done()
            exit()

    def kill(self, block=False):
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
                        logger.error('hit error: \n')
                        self.error_queue.put(error_message)
                        break
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
    def start(self):
        if self.threads:
            logger.error('threads already started. will not start more')
            return self.threads

        for i in range(self.thread_count):
            logger.debug('starting thread %s', i)
            # thread will begin execution on self.target()
            thd = threading.Thread(target=self.target)

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

    def put_job(self, job):
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
        self.metric_store = {}
        self.update_queue = Queue.Queue()
        self.started = False

    def join(self):
        self.update_queue.join()
        return True

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

    def set(self, key, value):
        self.metric_store[key] = value

    def get(self, variable):
        return self.metric_store.get(variable, 0)

    def increment(self, variable, step_size=1, filename=""):
        self.update_queue.put(('increment', variable, step_size, filename))

    def do_increment(self, *args):
        variable, step_size, filename = args

        # initialize variable to 0 if not set
        if not self.metric_store.has_key(variable):
            self.metric_store[variable] = 0

        # increment variable by step_size
        self.metric_store[variable] += step_size

        if filename:
            if 'files' not in self.metric_store:
                self.metric_store['files'] = {}
            if filename not in self.metric_store['files']:
                self.metric_store['files'][filename] = 0
            self.metric_store['files'][filename] += step_size

    def set_dict(self, dict_name, key, value):
        self.update_queue.put(('set_dict', dict_name, key, value))

    def do_set_dict(self, *args):
        dict_name, key, value = args

        if not self.metric_store.has_key(dict_name):
            self.metric_store[dict_name] = {}

        self.metric_store[dict_name][key] = value

    def get_dict(self, dict_name, key=None):
        # if dict_name does not exist, return an empty dict
        if not self.metric_store.has_key(dict_name):
            return {}

        # if key was not provided, return full dict
        if not key:
            return self.metric_store[dict_name]

        # return value of key
        return self.metric_store[dict_name].get(key)

    def append(self, list_name, value):
        self.update_queue.put(('append', list_name, value))

    def do_append(self, *args):
        list_name, value = args

        # initialize to empty list if not yet created
        if not self.metric_store.has_key(list_name):
            self.metric_store[list_name] = []

        # append value to list
        self.metric_store[list_name] = value

    def get_list(self, list_name):
        return self.metric_store.get(list_name, [])

    def target(self):
        logger.debug('created metric_store target thread')
        while True:
            # block until update given
            update_tuple = self.update_queue.get(True)

            method = update_tuple[0]
            method_args = update_tuple[1:]
            # check to see what action is to be carried out
            if method == 'increment':
                self.do_increment(*method_args)
            elif method == 'append':
                self.do_append(*method_args)
            elif method == 'set_dict':
                self.do_set_dict(*method_args)
            else:
                raise "method '%s' not valid" % method

            # mark task done
            self.update_queue.task_done()


class JobManager():
    '''

    '''

    def __init__(self, job_description, reporter_description=None):
        self.error = []
        self.workers = []
        self.reporters = []
        self.error_queue = Queue.Queue()
        self.metric_store = MetricStore()
        self.work_queues = [Queue.Queue()]
        self.job_description = job_description
        self.reporter_description = reporter_description

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
        global WORKING
        WORKING = False
        for worker in self.workers:
            worker.kill(block=False)

    def kill_reporters(self):
        for reporter in self.reporters:
            logger.debug('killing reporter %s', reporter)
            reporter.kill()

    def stop_work(self):
        global WORKING
        WORKING = False  # stop any new jobs from being created
        self.drain_queues()  # clear out any jobs in queue
        self.kill_workers()  # kill all threads
        self.kill_reporters()
        self.mark_all_tasks_complete()  # reset task counts

    def error_handler_target(self):

        while True:
            error = self.error_queue.get(True)
            logger.error('got something from the error queue')
            self.error.append(error)
            self.stop_work()
            try:
                self.error_queue.task_done()
            except ValueError:
                pass

    def start_error_handler(self):
        logger.debug('creating error handler thread')
        thd = threading.Thread(target=self.error_handler_target)
        thd.daemon = True
        thd.start()
        return None

    def add_task(self, task):
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
        next_queue = None
        last_queue = self.work_queues[0]
        last_worker = next(reversed(self.job_description))

        for worker_description in self.job_description:
            worker_class = worker_description[0]
            thread_count = worker_description[1]
            args = []
            kwargs = {}

            if len(worker_description) > 1:
                args = worker_description[1]

            if len(worker_description) > 2:
                kwargs = worker_description[2]

            kwargs['in_queue'] = last_queue

            if last_worker == worker_class:
                # the last worker does not need an output queue
                kwargs['out_queue'] = None
            else:
                next_queue = Queue.Queue()
                self.work_queues.append(next_queue)
                kwargs['out_queue'] = next_queue

            kwargs['error_queue'] = self.error_queue
            kwargs['metric_store'] = self.metric_store

            worker = worker_class(*args, **kwargs)
            logger.debug('starting worker %s', worker_class.__name__)
            worker_threads = worker.start()
            self.workers.append(worker)
            last_queue = next_queue

        # start reporters
        if self.reporter_description:
            for reporter_class, download_id in self.reporter_description:
                reporter = reporter_class(self.metric_store)
                logger.debug('starting reporter %s', reporter_class.__name__)
                reporter.start(download_id)
                self.reporters.append(reporter)

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
        self.metric_store.join()
        logger.debug('metric store in sync')
        if self.error:
            return self.error
        self.kill_workers()
        self.kill_reporters()
        return None

    def metric_store(self):
        return self.metric_store

    def worker_queue_status_text(self):
        msg = '\n' + '#' * 80 + '\n'
        for index, worker_info in enumerate(self.job_description):
            worker_class = worker_info[0]
            q_size = self.work_queues[index].qsize()
            worker_threads = self.workers[index].threads
            num_active_threads = len([thd for thd in worker_threads if thd.isAlive()])
            msg += '%s \titems in queue: %s' % (q_size, worker_class.__name__)
            msg += '\t\t%s threads' % num_active_threads
            msg += '\n'
        return msg
