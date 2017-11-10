import os
import random

# import upload_node

BYTE = 1
KILOBYTE = BYTE * 1024
MEGABYTE = KILOBYTE ** 2
GIGABYTE = KILOBYTE ** 3


def generate_random_files(file_count, dest_dirpath, min_size=BYTE, max_size=MEGABYTE):
    '''
    Generate n files, which are sized between the given min and max_size.

    file_count: int. the number of files to generate
    dest_dirpath: str. The directory to save the files to
    min_size: int. The minumum size that a file can be (bytes)
    max_size: int. The maximum size that a file can be (bytes)
    '''
    if not os.path.isdir(dest_dirpath):
        os.makedirs(dest_dirpath)

    for n in range(file_count):
        filename = "randomfile_%s" % n
        filepath = os.path.join(dest_dirpath, filename)

        random_bytes = random.randrange(min_size, max_size + 1)
        generate_file(filepath, random_bytes)



def generate_file(filepath, size):
    '''
    Generate a file at the given filepath of the given size
    '''


    dirpath = os.path.dirname(filepath)
    if not os.path.isdir(dirpath):
        os.makedirs(dirpath)

    print "Generating %s byte file: %s" % (size, filepath)
    with open(filepath, 'wb') as file_:
        file_.write(os.urandom(size))



def generate_small_text_files():
    '''
    3000 text files

    0.5KB-200KB
    
    TOTAL SIZE: 294.43359 MB
    '''
    file_count = 3000
    dest_dirpath = '/Volumes/af/tools/sandbox/lschlosser/test_data/conductor/upload_files/big_test/3000_small_text_files'
    min_size = KILOBYTE * .5
    max_size = KILOBYTE * 200
    generate_random_files(file_count, dest_dirpath, min_size=min_size, max_size=max_size)



def generate_medium_media_files():
    '''
    Generate 3000 media files
    
    2MB-50MB
    
    TOTAL SIZE: 76.17188 GB
    '''
    file_count = 3000
    dest_dirpath = '/Volumes/af/tools/sandbox/lschlosser/test_data/conductor/upload_files/big_test/3000_medium_media_files'
    min_size = MEGABYTE * 2
    max_size = MEGABYTE * 50
    generate_random_files(file_count, dest_dirpath, min_size=min_size, max_size=max_size)


def generate_large_media_files():
    '''
    Generate 100 media files
    
    200MB-5GB
    
    TOTAL SIZE: 259.76563 GB
    '''
    file_count = 5
    dest_dirpath = '/Volumes/af/tools/sandbox/lschlosser/test_data/conductor/upload_files/big_test/100_large_media_files'
    min_size = MEGABYTE * 200
    max_size = GIGABYTE * 5
    generate_random_files(file_count, dest_dirpath, min_size=min_size, max_size=max_size)


def generate_mega_media_files():
    '''
    Generate 1 large media file
    
    TOTAL SIZE: 65 GB
    '''
    file_count = 1
    dest_dirpath = '/Volumes/af/tools/sandbox/lschlosser/test_data/conductor/upload_files/big_test/1_mega_media_file'
    min_size = GIGABYTE * 65
    max_size = GIGABYTE * 65
    generate_random_files(file_count, dest_dirpath, min_size=min_size, max_size=max_size)

# def download_upload_paths(job_id):
#     filepaths = get_job_filepaths(job_id)
#     for filepath, hash in filepaths.iteritems():
#
