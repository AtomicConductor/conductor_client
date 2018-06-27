#!/usr/bin/env python
'''

sudo -HE env PATH=$PATH PYTHONPATH=$PYTHONPATH HOME=$HOME ./profile.py dirs /mnt/WD-Passport-WDBYFT0040BBL-1/test_data/random_data/07 --read=False --xxhash=True  --md5=False --warm_cache=True --benchmark_device=True
'''
import argparse
import collections
import csv
import functools
import hashlib
import io
import inspect
import json
import logging
from multiprocessing.pool import ThreadPool
import os
import re
import socket
import subprocess
import time

from conductor.lib import api_client, loggeria

try:
    import xxhash
    XXHASH = True
except ImportError as e:
    print "warning: Could not import xxhash.  xxhash functionality disabled"
    XXHASH = False

IS_ROOT = os.geteuid() is 0

DEFAULT_READ_SIZE = 65536

DESCRIPTION = "DESCRIPTION"
TIME_STAT = "STAT TIME"
TIME_READ = "READ TIME"
TIME_MD5 = "MD5 TIME"
TIME_XXHASH = "XXHASH TIME"
FILEPATH = "FILEPATH"
SIZE = "SIZE"
NAME = "NAME"
VALUE = "VALUE"
FILE_COUNT = "FILE COUNT"

# HEADERS for different csv/table sections
ARGS_HEADERS = [NAME, VALUE]
DEVICE_HEADERS = [DESCRIPTION, VALUE]
DATA_HEADERS = (DESCRIPTION, FILEPATH, SIZE, TIME_STAT, TIME_READ, TIME_MD5, TIME_XXHASH)
SUMMARY_HEADERS = (DESCRIPTION, FILE_COUNT, SIZE, TIME_STAT, TIME_READ, TIME_MD5, TIME_XXHASH)

logger = logging.getLogger("conductor")


def parse_args():

    # ------------------------------------------------
    # common parser
    # ------------------------------------------------
    common_parser = argparse.ArgumentParser(add_help=False)

    common_parser.add_argument(
        "--stat",
        choices=[False, True],
        type=cast_to_bool,
        default=True,
        help='Perform a stat on each file'
    )

    common_parser.add_argument(
        "--read",
        choices=[False, True],
        type=cast_to_bool,
        default=True,
        help='Read the entire contents of each file'
    )

    common_parser.add_argument(
        "--md5",
        choices=[False, True],
        type=cast_to_bool,
        default=True,
        help='Generate an md5 hash for each file'
    )

    if XXHASH:
        common_parser.add_argument(
            "--xxhash",
            choices=[False, True],
            type=cast_to_bool,
            default=True,
            help='Generate an xxhash hash for each file'
        )

    common_parser.add_argument(
        "--warm_cache",
        choices=[False, True],
        type=cast_to_bool,
        default=False if IS_ROOT else True,
        help=("If True, will \"warm up\"(i.e.read) each file before performing any further operation on it. "
              "If False (which requires running as root)will clear OS cache before performing read operations (recommended)")
    )

    common_parser.add_argument(
        "--threads",
        type=int,
        default=1,
        help=("The number of threads to use so that parallel reads can be tested. "
              "Note that parallelizing reads my result in a faster overall test, but may also lead "
              "to slower per-file reads on average")
    )

    common_parser.add_argument(
        "--csv_path",
        help="A csv filepath to write the the results to. Results contain metrics per each file",
    )

    common_parser.add_argument(
        "--limit",
        type=int,
        help="Limit the number of files tested to the given value",
    )

    common_parser.add_argument(
        "--log_level",
        choices=loggeria.LEVELS,
        default=loggeria.LEVEL_INFO,
        help="The logging level to display")

    common_parser.add_argument(
        "--read_size",
        type=int,
        default=65536,
        help="The number of bytes to read at a time (when reading a file)",
    )

    common_parser.add_argument(
        "--skip_failures",
        choices=[False, True],
        type=cast_to_bool,
        default=False,
        help=("If True, will skip any failures upon file reads. Otherwise an exception will halt "
              "testing.")
    )

    common_parser.add_argument(
        "--benchmark_device",
        choices=[False, True],
        type=cast_to_bool,
        default=True if IS_ROOT else False,
        help=("If True, will test read-throughput of disk before performing file profiling."
              "Requires root privileges")
    )

    common_parser.add_argument(
        "--suite_file",
        action=ValidatePath,
        help=("The path to the suite of test configurations to be run"),
    )

    common_parser.add_argument(
        "--output_dir",
        help=("The directory to write verbose results to"),
    )

    # ------------------------------------------------
    # Main parser
    # ------------------------------------------------
    parser = argparse.ArgumentParser(
        description=("Profile the performance of your file system by processing a set of files. "
                     "A set of files is dictated by either providing a conductor job id, or a "
                     "list of directories. Use the appropriate sub command to use either methodology.")
    )
    subparsers = parser.add_subparsers(title="Target files from")

    # ------------------------------------------------
    # Job/jid parser
    # ------------------------------------------------
    job_parser = subparsers.add_parser(
        "job",
        parents=[common_parser],
        help="Target files from an existing Conductor job for profiling",
        description=("Profile the performance of your file system by processing files from the provided "
                     "Conductor Job ID (jid)"),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    job_parser.add_argument(
        "jid",
        help="The jid (job id) for a job whose files to target",
    )

    job_parser.set_defaults(func=run_job_profiler)

    # ------------------------------------------------
    # Directory parser
    # ------------------------------------------------
    dir_parser = subparsers.add_parser(
        "dirs",
        parents=[common_parser],
        help="Target files from a provided directory for profiling",
        description=("Profile the performance of your file system by processing files found in the "
                     "given directories"),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )

    dir_parser.add_argument(
        "dirs",
        nargs="+",
        help="One or more directories to read files from (recursively)",
    )

    dir_parser.set_defaults(func=run_dir_profiler)

    return parser.parse_args()


def cast_to_bool(string):
    '''
    Ensure that the argument provided is either "True" or "False (or "true" or
    "false") and convert that argument to an actual bool value (True or False).
    '''
    string_lower = string.lower()
    if string_lower == "true":
        return True
    elif string_lower == "false":
        return False
    raise argparse.ArgumentTypeError('Argument must be True or False')


class ValidatePath(argparse.Action):
    '''
    Validate that the give path exists
    '''

    def __call__(self, parser, namespace, values, option_string):
        if not os.path.exists(values):
            raise argparse.ArgumentError(self, "Path does not exist: %s" % values)
        setattr(namespace, self.dest, values)


def run_job_profiler(args):
    '''
    Profile the files found from the provided Job id (jid)
    '''

    # ------------------------------------------------
    # Fetch Job
    # ------------------------------------------------
    logger.info("Fetching Job %s", args.jid)
    client = api_client.ApiClient()
    r_body, _ = client.make_request('api/v1/jobs',
                                    params="filter=jid_eq_%s" % args.jid,
                                    use_api_key=True
                                    )

    jobs = json.loads(r_body).get("data")
    if not jobs:
        raise Exception("No Job %s found" % args.jid)
    assert len(jobs) < 2, "Found more than 1 Job with jid %s" % args.jid
    job = jobs[0]
    upload_id = job["upload"]

    # ------------------------------------------------
    # Fetch Job's Upload
    # ------------------------------------------------
    logger.info("Fetching Upload %s", upload_id)
    r_body, _ = client.make_request('api/v1/uploads/%s' % upload_id,
                                    use_api_key=True
                                    )
    upload = json.loads(r_body).get("data")
    filepaths = upload["upload_files"].keys()

    return run_profiler(filepaths, args)


def run_dir_profiler(args):
    '''
    Profile the files found from the provided directories
    '''
    logger.info("Testing files in the following directories:\n\t%s", "\n\t".join(args.dirs))
    # Validate that provided directories exist
    for dirpath in args.dirs:
        if not os.path.isdir(dirpath):
            raise Exception("Directory does not exist: %s" % dirpath)

    filepaths = []
    for dirpath in args.dirs:
        filepaths.extend(get_files(dirpath, recurse=True))

    return run_profiler(filepaths, args)


def run_profiler(filepaths, args):

    if not args.suite_file:
        return _run_profiler(filepaths, args)

    with open(args.suite_file) as f:
        suite_file = json.load(f)
        for test_args in suite_file:
            new_args = vars(args)
            new_args.update(test_args)
            _run_profiler(filepaths, argparse.Namespace(**new_args))


def _run_profiler(filepaths, args):
    if args.output_dir:
        filename = "%s_threads=%s_stat=%s_read=%s_md5=%s_xxhash=%s_warm_cache=%s.csv"
        args.csv_path = os.path.join(args.output_dir, filename % (
            socket.gethostname(),
            args.threads,
            bool(args.stat),
            bool(args.read),
            bool(args.md5),
            bool(args.xxhash),
            bool(args.warm_cache),

        ))

    if args.limit:
        filepaths = filepaths[:args.limit]

    return profile(
        filepaths,
        stat=args.stat,
        read=args.read,
        hash_md5=args.md5,
        hash_xx=args.xxhash if XXHASH else None,
        warm_cache=args.warm_cache,
        read_size=args.read_size,
        thread_count=args.threads,
        csv_filepath=args.csv_path,
        skip_failures=args.skip_failures,
        benchmark_device=args.benchmark_device,
    )


def profile(filepaths, stat=True, read=True, hash_md5=True, hash_xx=True, warm_cache=False, benchmark_device=True,
            read_size=DEFAULT_READ_SIZE, thread_count=1, skip_failures=False, csv_filepath=None):
    '''
    Profile the given list of files. see "profile_file" function for
    additional argument details.  If a output_dir is provided, verbose profiling data
    will be written to that destination.  Otherwise, only summary data will be logged to stdout, e.g

        ---------- SUMMARY -----------
        DESCRIPTION    FILE COUNT             SIZE       STAT TIME            WARMUP TIME          READ TIME            MD5 TIME             XXHASH TIME
        Averaged Time  970 files (0 skipped)  206185     000.000005209814642  000.000095234703772  000.000074392495696  000.000403518037698  000.000095770776886
        Summed Time    970 files (0 skipped)  200000000  000.005053520202637  000.092377662658691  000.072160720825195  000.391412496566772  000.092897653579712
        Test Time      0.661609172821
        ------------------------------
    '''

    # Capture/record the arguments that were provided to the function. We'll log/write them out as
    # part of the report.
    args_record = inspect.getargvalues(inspect.currentframe())[3]
    # Instead of recording each filepaths arg (as there may be millions), simply record the file count
    args_record["filepaths"] = len(args_record["filepaths"])

    # Log out the arguments
    for arg_name, arg_value in sorted(args_record.iteritems()):
        logger.info("%s: %s", arg_name, arg_value)

    bench_results = []
    if benchmark_device:
        logger.info("Using device used by file: %s" % filepaths[0])
        device = get_device(filepaths[0])
        logger.info("Benchmarking device: %s", device)
        bench_results.append({DESCRIPTION: "Device", VALUE: device})

        for bench_type, result in run_hdparm(device, runs=3).iteritems():
            bench_results.append({DESCRIPTION: bench_type, VALUE: "%s bytes/sec" % result})

        # Generate a summary string that can be logged out
        disk_bench_str = SummaryTableStr(bench_results,
                                         DEVICE_HEADERS,
                                         title=" DEVICE BENCHMARK ".center(30, "-"),
                                         footer="-" * 30).make_table_str()
        print disk_bench_str

    # Record the start time for the entire test
    test_time_start = time.time()
    logger.info("Profiling %s files using %s threads...", len(filepaths), thread_count)

    # Run the profile
    results = profile_files(filepaths, stat=stat, read=read, hash_md5=hash_md5, hash_xx=hash_xx, warm_cache=warm_cache,
                            read_size=read_size, thread_count=thread_count, skip_failures=skip_failures)

    # Record the duration of the entire test.
    test_time_duration = time.time() - test_time_start
    logger.info('Profile runtime: %.2f seconds', test_time_duration)

    # Generate summary information
    summary = generate_summary(results)
    # inject the duration of the entire test into the summary.  Pretty hacky, could be better!
    summary.append({DESCRIPTION: "Test Time", FILE_COUNT: test_time_duration})

    # Generate a summary string that can be logged out
    summary_str = SummaryTableStr(summary,
                                  SUMMARY_HEADERS,
                                  title=" SUMMARY ".center(30, "-"),
                                  footer="-" * 30).make_table_str()
    # print out summary
    print summary_str

    # If a csv filepath is provided (for output), generate a more verbose output
    if csv_filepath:

        # Generate a summary of the arguments that were used to run this test
        args_summary = generate_args_summary(args_record)
        logger.debug("Writing to: %s", csv_filepath)
        if not os.path.isdir(os.path.dirname(csv_filepath)):
            safe_mkdirs(os.path.dirname(csv_filepath))

        # There are three different sections in the csv (each have different headers):
        # - arguments used to run the test
        # - the summary of the test
        # - the per-file results of the test
        with open(csv_filepath, 'w') as f:
            for title, headers, data in (
                (" ARGUMENTS ".center(30, "-"), ARGS_HEADERS, args_summary),
                (" DEVICE BENCHMARK ".center(30, "-"), DEVICE_HEADERS, bench_results),
                (" SUMMARY ".center(30, "-"), SUMMARY_HEADERS, summary),
                (" FILE RESULTS ".center(30, "-"), DATA_HEADERS, results),
            ):
                write_csv_section(f, title, headers, data)

        logger.info("Summary written to: %s", csv_filepath)


def profile_files(filepaths, stat=True, read=True, hash_md5=True, hash_xx=True, warm_cache=False,
                  read_size=DEFAULT_READ_SIZE, thread_count=1, skip_failures=False):
    '''
    Profile the given list of files within a threading pool.  see "profile_file" function for
    additional argument details.
    '''

    # Run Profile using the number of threads specified
    pool = ThreadPool(processes=thread_count)
    return pool.map(functools.partial(profile_file,
                                      stat=stat,
                                      read=read,
                                      hash_md5=hash_md5,
                                      hash_xx=hash_xx,
                                      warm_cache=warm_cache,
                                      read_size=read_size,
                                      skip_failures=skip_failures,
                                      ),
                    filepaths)


def profile_file(filepath, stat=True, read=True, hash_md5=True, hash_xx=True, warm_cache=False,
                 read_size=DEFAULT_READ_SIZE, skip_failures=False):
    '''
    Perform the indicated actions on the given file.  Record and return the time that it takes for
    each action.

    args:
        stat: bool.  If True, stat the file.
        read: bool.  If True, read the entire file.
        hash_md5: bool.  If True, generate an md5 hash from the file.
        hash_xx: bool.  If True, generate an xx hash from the file.
        warmup: bool.  If True, read the entire file first (i.e. "warm it up") before performing any
             operations on it.  This essentially loads the file into any OS/disk cache so that
             subsequent reads to that file will yield consistent performance between tests.
        read_size: int. The number of bytes to read when
        skip_failures: bool. If True, skip/suppress any failures (rather than raising an exception).
        return: dict of metrics data
    '''
    # Create the boilerplate data structure for profile data
    profile_data = {
        DESCRIPTION: "file",
        FILEPATH: filepath,
        SIZE: None,
        TIME_STAT: None,
        TIME_READ: None,
        TIME_MD5: None,
        TIME_XXHASH: None,
    }
    profiler = Profile(use_cache=warm_cache, read_size=read_size)
    try:

        if stat:
            result, duration = profiler(stat_file)(filepath)
            profile_data[TIME_STAT] = duration
            profile_data[SIZE] = result.st_size

        if read:
            _, duration = profiler(read_file)(filepath, read_size=read_size)
            profile_data[TIME_READ] = duration

        if hash_xx and XXHASH:
            _, duration = profiler(generate_xxhash)(filepath, read_size=read_size)
            profile_data[TIME_XXHASH] = duration

        if hash_md5:
            _, duration = profiler(generate_md5)(filepath, read_size=read_size)
            profile_data[TIME_MD5] = duration

    except Exception as e:
        if not skip_failures:
            raise
        logger.warning(e)
        profile_data[DESCRIPTION] = "skipped file due to error: %s" % e

    return profile_data


def stat_file(filepath):
    return os.stat(filepath)


def read_file(filepath, read_size):
    with io.open(filepath, 'rb') as f:
        file_buffer = f.read(read_size)
        while len(file_buffer) > 0:
            file_buffer = f.read(read_size)


def generate_md5(filepath, read_size=DEFAULT_READ_SIZE):
    hasher = hashlib.md5()
    return generate_hash(filepath, hasher, read_size=read_size).hexdigest()


def generate_xxhash(filepath, read_size=DEFAULT_READ_SIZE):
    hasher = xxhash.xxh32()
    return generate_hash(filepath, hasher, read_size=read_size).hexdigest()


def generate_hash(filepath, hasher, read_size=DEFAULT_READ_SIZE):
    '''
    Hash the given filepath using the given hasher object.

    filepath: str. The file path of the file to hash.

    hasher: hashing object.
    '''
    file_obj = io.open(filepath, 'rb')
    buffer_count = 1
    file_buffer = file_obj.read(read_size)
    while len(file_buffer) > 0:
        hasher.update(file_buffer)
        file_buffer = file_obj.read(read_size)
        buffer_count += 1
    return hasher


def write_csv_section(file_obj, title, headers, data):
    '''
    Write a section of csv data to an open file object

    '''
    writer = csv.DictWriter(file_obj, fieldnames=headers)
    writer.writer.writerow([title])
    writer.writeheader()
    for row in data:
        writer.writerow(row)
    writer.writerow({})
    writer.writerow({})


def generate_args_summary(args):

    args_summary = []
    for arg_name, arg_value in args.iteritems():
        args_summary.append(
            {
                NAME: arg_name,
                VALUE: arg_value,
            }

        )
    return args_summary


def drop_caches(value=3, sync=True):
    '''
    Flush Operating System caches (Linux only!)

    Uses /proc/sys/vm/drop_caches

    sync: bool. If True will flush dirty objects to disk. Otherwise dirty objects will continue to
        be in use until written out to disk and are not freeable.

    value: int
        1: free pagecache
        2: free dentries and inodes
        3: free pagecache, dentries and inodes
    '''
    cmd = "echo %s > /proc/sys/vm/drop_caches" % value
    if sync:
        cmd = "sync;" + cmd
    subprocess.check_call(cmd, shell=True)


def generate_summary(data):
    '''
    Generate the summary data from the profiling results. Summary data consists for two rows:
        - summed totals of all columns
        - averages of all columns

    Filter out any rows/files that were
    skipped/failed.

    args:
        data: a list of dicts, where each dict represents a row of file information
        return: a list of dicts, where each dict represents a row of summary data.
    '''
    logger.info("Creating summary rows...")

    # Filter our skipped files
    filtered_rows = []
    skipped_rows = []
    for row in data:
        if "skipped" in row[DESCRIPTION]:
            skipped_rows.append(row)
        else:
            filtered_rows.append(row)

    sum_summary = {
        DESCRIPTION: "Sum",
        FILE_COUNT: "%s files (%s skipped)" % (len(filtered_rows), len(skipped_rows)),
    }
    avg_summary = {
        DESCRIPTION: "Average",
        FILE_COUNT: "%s files (%s skipped)" % (len(filtered_rows), len(skipped_rows)),
    }

    for header in (SIZE, TIME_STAT, TIME_READ, TIME_MD5, TIME_XXHASH):
        logger.debug('Summarizing "%s" data...', header)
        column_entries = [row[header] for row in filtered_rows if row[header] is not None]
        sum_summary[header] = sum(column_entries) if column_entries else ""
        avg_summary[header] = (sum_summary[header] / float(len(column_entries))) if column_entries else ""

    return [avg_summary, sum_summary]


def get_files(dirpath, recurse=True):
    '''
    Return all files found in the given directory.

    Optionally recurse the directory to also include files that are located
    in subdirectories as well
    '''
    files = []

    if not os.path.isdir(dirpath):
        raise Exception("Directory does not exist: '%s'" % dirpath)

    # If operating recursively, use os.walk to grab sub files
    if recurse:
        for sub_dirpath, _, filenames in os.walk(dirpath):
            for filename in filenames:
                filepath = os.path.join(sub_dirpath, filename)
                if os.path.isfile(filepath):
                    files.append(filepath)
    else:
        for filename in os.listdir(dirpath):
            if os.path.isfile(os.path.join(dirpath, filename)):
                files.append(os.path.join(dirpath, filename))

    return files


def safe_mkdirs(dirpath):
    '''
    Create the given directory.  If it already exists, suppress the exception.
    This function is useful when handling concurrency issues where it's not
    possible to reliably check whether a directory exists before creating it.
    '''

    # Attempt to create the directory path
    try:
        os.makedirs(dirpath)

    # only catch OSERrror exceptions
    except OSError:
        # This exception might happen for various reasons. So to be sure that
        # it's due to the path already existing, check the path existence.
        # If the path doesn't exist, then raise the original exception.
        # Otherwise ignore the exception bc the path exists.
        if not os.path.isdir(dirpath):
            raise


def precision_formatter(value, float_precision=15, zfill=4, omit_empty=True):
    '''
    args:
        float_precision: int. The number of decimal places to limit the value to
        zfill: the number of decimal places to fill/pad (with zeros) *to the left* of the
            decimal place (if necesary).
    '''
    if value is "" and omit_empty:
        return ""

    # Pads/prefixes the float with 3 decimal places of zeros
    return ('%.*f' % (float_precision, value)).zfill(float_precision + zfill)


def get_device(path):
    '''
    Derive the device from the given filepath
    '''
    dev = os.stat(path).st_dev
    major, minor = os.major(dev), os.minor(dev)
    res = {}
    for line in file("/proc/partitions"):
        fields = line.split()
        try:
            tmaj = int(fields[0])
            tmin = int(fields[1])
            name = fields[3]
            res[(tmaj, tmin)] = name
        except Exception:
            # just ignore parse errors in header/separator lines
            pass

    return "/dev/%s" % res[(major, minor)]


def run_hdparm(device, runs=3):
    run_results = collections.defaultdict(list)
    for _ in range(runs):
        print "Executing %s/%s runs:" % (_ + 1, runs),
        for bench_type, result in _run_hdparm(device).iteritems():
            run_results[bench_type].append(result)

    result_avg = {}

    for bench_type, results in run_results.iteritems():
        result_avg[bench_type] = int(sum(results) / float(len(results)))

    return result_avg


def _run_hdparm(device):
    '''

    regex samples:
        Timing cached reads:   18784 MB in  2.00 seconds = 9400.60 MB/sec
        Timing buffered disk reads: 3220 MB in  3.00 seconds = 1072.86 MB/sec
        Timing buffered disk reads:  80 MB in  3.01 seconds =  26.60 MB/sec

    '''
    rx = r"Timing ((?:\w|\s)+)+:\s+\d+\s+\w+\s+in\s+\d+\.\d+\s+seconds\s+=\s+(\d+\.\d+)\s+(\w+)/sec"
    cmd = "hdparm -Tt %s" % device
    print cmd
    results = {}
    for line in subprocess.check_output(cmd, shell=True).split("\n"):
        if not line.strip() or line.startswith("/dev/"):
            continue
        match = re.search(rx, line.strip())
        if not match:
            raise Exception('Failed to parse benchmarking output: "%s"' % line.strip())

        bench_type, data_value, data_unit = match.groups()
        # convert to bytes
        if data_unit == "GB":
            bytes_ = float(data_value) * 1000000000
        elif data_unit == "MB":
            bytes_ = float(data_value) * 1000000
        elif data_unit == "KB":
            bytes_ = float(data_value) * 1000
        elif data_unit == "B":
            bytes_ = float(data_value)
        else:
            raise Exception("Got unexpected unit of measurement: %s" % data_unit)
        results[bench_type] = int(bytes_)

    return results


class SummaryTableStr(loggeria.TableStr):
    '''
    Subclass TableStr to provide custom formatters for our data

    ---------- SUMMARY -----------
    DESCRIPTION    FILE COUNT             SIZE       STAT TIME            WARMUP TIME          READ TIME            MD5 TIME             XXHASH TIME
    Averaged Time  970 files (0 skipped)  206185     000.000005209814642  000.000095234703772  000.000074392495696  000.000403518037698  000.000095770776886
    Summed Time    970 files (0 skipped)  200000000  000.005053520202637  000.092377662658691  000.072160720825195  000.391412496566772  000.092897653579712
    Test Time      0.661609172821
    ------------------------------
    '''

    cell_modifiers = {
        TIME_STAT: precision_formatter,
        TIME_READ: precision_formatter,
        TIME_MD5: precision_formatter,
        TIME_XXHASH: precision_formatter,
        SIZE: lambda x: int(x) if x is not "" else x,
    }


class Profile(object):
    '''
    Wrapped function's signuature must use a filepath as the first argument
    '''

    def __init__(self, use_cache=False, read_size=DEFAULT_READ_SIZE):
        '''
        args
            use_cache: bool.  If True, will read file first before calling wrapped function
        '''
        self.use_cache = use_cache
        self.read_size = read_size

    def __call__(self, function):

        @functools.wraps(function)
        def _decorator(*args, **kwargs):
            filepath = args[0]
            if self.use_cache:
                logger.debug("warming file..")
                read_file(filepath, read_size=self.read_size)
            else:
                logger.debug("flushing os caches")
                drop_caches(value=3, sync=True)
            start_time = time.time()
            result = function(*args, **kwargs)
            duration = time.time() - start_time
            return result, duration
        return _decorator


if __name__ == '__main__':
    args = parse_args()
    loggeria.setup_conductor_logging(logger_level=loggeria.LEVEL_MAP.get(args.log_level))
    args.func(args)
