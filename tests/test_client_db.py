#!/usr/bin/env python

import json
import logging
import Queue
import os
import threading

from conductor.lib import common, client_db, uploader, loggeria, profiling_utils, test_utils


logger = logging.getLogger(__name__)


def get_file_entry(filepath, db_connection):

    # Otherwise attempt to use the md5 cache
    file_info = uploader.get_file_info(filepath)
#     return client_db.FilesDB.get_cached_file(file_info, connection=db_connection)
    return client_db.FilesDB.get_cached_file(file_info, db_filepath=db_connection, thread_safe=True)


class Worker(threading.Thread):

    def __init__(self, work_queue, results_queue):
        self.work_queue = work_queue
        self.results_queue = results_queue
        super(Worker, self).__init__()

    def run(self, *args, **kwargs):
        try:
            while True:
                try:
                    work = self.work_queue.get_nowait()
                except Queue.Empty:
                    logger.debug("Queue is empty.  Exiting thread..")
                    return
                else:
                    result = self.execute(work)
                    self.results_queue.put_nowait(result)
                    self.work_queue.task_done()
        except:
            logger.exception("Thread encountered exception")
            raise

    def execute(self, work):
        pass


class DbWorker(Worker):

    def __init__(self, work_queue, results_queue, db_filepath):
        self.db_filepath = db_filepath
        super(DbWorker, self).__init__(work_queue, results_queue)

    def run(self, *args, **kwargs):
        self.connection = client_db.TableDB.connnect_to_db(self.db_filepath, timeout=5.0, db_perms=0666)
        return super(DbWorker, self).run(*args, **kwargs)

    def execute(self, work):
        filepath = work
        return get_file_entry(filepath, self.db_filepath)
#         return get_file_entry(filepath, self.connection)


@common.dec_timer_exit(log_level=logging.INFO)
@profiling_utils.YappiProfile()
def test(filepaths, db_filepath, thread_count):

    work_queue = Queue.Queue()
    [work_queue.put_nowait(filepath) for filepath in filepaths]

    results_queue = Queue.Queue()

    threads = []
    for thread_int in range(thread_count):
        thread = DbWorker(work_queue, results_queue, db_filepath)
        thread.daemon = True
        thread.start()
        threads.append(thread)

    for thread in threads:
        thread.join()
    return results_queue


def run_db_test(filepaths, db_filepath=None, thread_count=4):

    logger.info("Filepath count: %s", len(filepaths))
    logger.info("thread_count: %s", thread_count)
    results_queue = test(filepaths, db_filepath, int(thread_count))
    results = list(results_queue.queue)
    logger.info("results count: %s", len(results))
    misses = filter(lambda x: not x, results)
    logger.info("db misses: %s", len(misses))
