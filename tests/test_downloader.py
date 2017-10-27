'''
The aim of this module is to test the downloader to ensure that it's functioning
properly

Requirments:

1. Need a volume of data to download
    - multiple jobs with multiple tasks
    - large files and small files

    


setup

Generate 5 Job
    
    Job 1
        3 Tasks
        3 Downloads
            location
        
    Job 2
        20 Tasks
        20 Downloads
        
    Job 3
        100 Tasks
        100 Downloads
        
    Job 4
        2 Tasks
        2 Downloads
        
    Job 5
        700 Tasks
        700 Downloads
        
    
     


'''
import os
import subprocess
import logging
#
#
# from application import models
# from cdr import remote
import test_uploader

# use this for filename construction
RANDOM_WORDS = ['heartland',
                'cental',
                'foolproof',
                'limestone',
                'corer',
                'bootless',
                'curtin',
                'mopoke',
                'handcuffs',
                'shemaal',
                'wendish',
                'cullen',
                'perdix',
                'estocs',
                'toxoid',
                'pantsuit',
                'yester',
                'cadelle',
                'untorn',
                'snowdrift']




def setup(project, account, job_id):
    pass



def gcloud_login(project):
    cmd = "gcloud auth login %s --brief" % project
    logging.debug(cmd)
    subprocess.call(cmd, shell=True)



def copy_file_to_gcs(filepath, gcs_filepath):
    '''
    copy the given filepath to the given GCS filepath
    '''
    copy_cmd = 'gsutil cp gs://%s %s' % (filepath, gcs_filepath)
    print copy_cmd
    logging.info(copy_cmd)
    subprocess.call(copy_cmd, shell=True)


def generate_local_task_files(task_id, file_count, file_size, dirpath, render_pass_dir=True):
    '''
    Generate files for a task
    
    example:
        task_id=37,  file_count=5, dirpath=/usr/tmp/randomfiles/
        
        /usr/tmp/randomfiles/heartland.037.exr
        /usr/tmp/randomfiles/cental.037.exr
        /usr/tmp/randomfiles/foolproof.037.exr
        /usr/tmp/randomfiles/limestone.037.exr
        /usr/tmp/randomfiles/corer.037.exr

    
    '''
    task_files = []
    for render_pass in RANDOM_WORDS[:file_count]:
        task_id_str = str(task_id).zfill(3)
        file_name = "%s.%s.exr" % (render_pass, task_id_str)
        if render_pass_dir:
            filepath = os.path.join(dirpath, render_pass, file_name)
        else:
            filepath = os.path.join(dirpath, file_name)

        test_uploader.generate_file(filepath, file_size)
    task_files.append(filepath)
    return task_files



def setup_job(project, account, task_count, task_files_count, file_size, output_path, location, job_id=None):
    '''
    Create a Job entity, and
    Create n Tasks entities(task_count), and
    Create n Download entities (task_count), which
    record  x files (task_files_count) in gcs, which
    Are each of x bytes large (file_size)
    '''
    # Generate files and upload them to gcs




    # Create the job
    job = create_job(account, output_path, task_count, location, job_id=job_id)




def setup_job_files(job_id, task_count, task_file_count, file_size, dirpath):
    job_files = create_job_files(job_id, task_count, task_file_count, file_size, dirpath)



def copy_job_files_to_gcs(project, account, job_id, job_files, render_pass_dir=True):
    gcs_job_dir = "%s/accounts/%s/output_render/%s/" % (project, account, job_id)

    for task_id, task_filepaths in job_files.iteritems():
        for filepath in task_filepaths:
            if render_pass_dir:
                root_dir = os.path.dirname(os.path.dirname(filepath))
            else:
                root_dir = os.path.dirname(filepath)

            relpath = os.path.relpath(filepath, root_dir)
            gcs_filepath = os.path.join(gcs_job_dir, task_id, relpath)
            copy_file_to_gcs(filepath, gcs_filepath)


def create_job_files(job_id, task_count, task_file_count, file_size, dirpath):
    job_files = {}

    for task_int in range(task_count):
        task_id_str = str(task_int).zfill(3)
        task_dirpath = os.path.join(dirpath, job_id, task_id_str)
        task_files = generate_local_task_files(task_int, task_file_count, file_size, task_dirpath)
        job_files[task_id_str] = task_files

    return job_files


# gsutil cp /usr/local/lschlosser/code/conductor_ae/utils/render_scripts/maya2015Render gs://render_scripts/render_scripts_0.3.2/maya2015Render



def create_job(account, output_path, task_count, location, job_id=None):
    if not job_id:
        job_id = str(models.get_next_job_id(account)).zfill(5)
    assert isinstance(job_id, str), job_id


    job = models.Job(account=account,
                      job_id=job_id,
                      frame_range="1-1x1" ,
                      owner="test",
                      status="success",  # Set to success so that no job will launch (or be misleading
                      instance_type="",
                      output_path="bogus",
                      command="test command",
                      environment={},
                      resource="testResource",
                      tasks=str(task_count),
                      pending="0",  # Don't set any tasking to pending
                      priority="100",
                      machine_flavor="fakeMachineFlavor",
                      cores="2",
                      title="fake job for dowloader",
                      location=location,
                      notify={})



    return job.put()


# Download
# destination /Volumes/af/show/wash/shots/MJ/MJ_1150/publish/main/light/v007/render/plants
# source fiery-celerity-88718/accounts/atomicfiction/output_render/08553/*1030.*
def create_download(account, source, destination, task, job_id, task_id, status):
    download = models.Download(account=account, source=source, destination=destination, jid=job_id, tid=task_id)
    return download.put()
