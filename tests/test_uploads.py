import os
import unittest
import sys
import traceback
import urllib2

from urllib2 import HTTPError

# add ../conductor to path
test_dir = os.path.dirname(os.path.realpath(__file__))
os.chdir(test_dir)
base_dir = os.path.dirname(test_dir)
sys.path.append(base_dir)

upload_test_helpers = os.path.join(test_dir,'upload_helpers')

os.environ['FLASK_CONF'] = 'TEST' # disable retries n' stuff
# os.environ['CONDUCTOR_DEVELOPMENT'] = '1' # uncomment this line to get debug messages


# import conductor stuff
from conductor.lib.conductor_submit import Uploader, Submit, make_request


def full_path(relative_path_in_test_helpers_dir):
    return os.path.join(upload_test_helpers,relative_path_in_test_helpers_dir)

class UploaderTest(unittest.TestCase):

    def test_get_children(self):

        single_file = full_path('single_file/foo')
        self.assertEqual(Uploader().get_children(single_file),
                         [single_file])

        dir_with_single_file = full_path('single_file')
        self.assertEqual(Uploader().get_children(dir_with_single_file),[
            single_file])

        dir_with_two_files = full_path('two_files')
        self.assertEqual(Uploader().get_children(dir_with_two_files),[
            full_path('two_files/one'),
            full_path('two_files/two')])

        dir_with_a_subdir = full_path('one_subdir')
        self.assertEqual(Uploader().get_children(dir_with_a_subdir),[
            full_path('one_subdir/one'),
            full_path('one_subdir/a_subdir/three'),
            full_path('one_subdir/a_subdir/two')])

        dir_with_many_subdirs = full_path('many_subdirs')
        self.assertEqual(Uploader().get_children(dir_with_many_subdirs),[
            full_path('many_subdirs/bar'),
            full_path('many_subdirs/one'),
            full_path('many_subdirs/a_subdir/adsf'),
            full_path('many_subdirs/a_subdir/three'),
            full_path('many_subdirs/a_subdir/two'),
            full_path('many_subdirs/a_subdir/another_subdir/oimsdf'),
            full_path('many_subdirs/a_subdir/another_subdir/even_another_subdir/ppp')])

        dir_with_symlink = full_path('one_symlink')
        self.assertEqual(Uploader().get_children(dir_with_symlink),[
            full_path('one_symlink/nnn'),
            full_path('one_symlink/many_subdirs/bar'),
            full_path('one_symlink/many_subdirs/one'),
            full_path('one_symlink/many_subdirs/a_subdir/adsf'),
            full_path('one_symlink/many_subdirs/a_subdir/three'),
            full_path('one_symlink/many_subdirs/a_subdir/two'),
            full_path('one_symlink/many_subdirs/a_subdir/another_subdir/oimsdf'),
            full_path('one_symlink/many_subdirs/a_subdir/another_subdir/even_another_subdir/ppp')])

        with self.assertRaises(ValueError):
            Uploader().get_children('/adsf/asdvawe/asdfvasdv/aotmasdfp')


    def test_get_upload_files(self):
        # create dummy upload file
        # TODO: make this not suck
        upload_file_path = '/tmp/upload_file'
        upload_file = open(upload_file_path, 'w')
        upload_file.write(full_path('single_file'))
        upload_file.close()


        # test most basic case
        args = {'cmd': 'some command',
                'upload_file': upload_file_path,
                'upload_only': True,
                }
        s1 = full_path('single_file/foo')
        self.assertEqual(Submit(args).get_upload_files(),[full_path('single_file/foo') ])


        # test two items in the upload file
        upload_file = open(upload_file_path, 'w')
        upload_file.write('%s,%s' % (full_path('single_file'),full_path('one_symlink')))
        upload_file.close()
        args = {'cmd': 'some command',
                'upload_file': upload_file_path,
                'upload_only': True}
        self.assertEqual(Submit(args).get_upload_files(),[
            full_path('single_file/foo'),
            full_path('one_symlink/nnn'),
            full_path('one_symlink/many_subdirs/bar'),
            full_path('one_symlink/many_subdirs/one'),
            full_path('one_symlink/many_subdirs/a_subdir/adsf'),
            full_path('one_symlink/many_subdirs/a_subdir/three'),
            full_path('one_symlink/many_subdirs/a_subdir/two'),
            full_path('one_symlink/many_subdirs/a_subdir/another_subdir/oimsdf'),
            full_path('one_symlink/many_subdirs/a_subdir/another_subdir/even_another_subdir/ppp')])


        # test upload_paths
        args = {'cmd': 'some command',
                'upload_only': True,
                'upload_paths': [full_path('single_file'),
                                 full_path('one_symlink')]}

        self.assertEqual(Submit(args).get_upload_files(),[
            full_path('single_file/foo'),
            full_path('one_symlink/nnn'),
            full_path('one_symlink/many_subdirs/bar'),
            full_path('one_symlink/many_subdirs/one'),
            full_path('one_symlink/many_subdirs/a_subdir/adsf'),
            full_path('one_symlink/many_subdirs/a_subdir/three'),
            full_path('one_symlink/many_subdirs/a_subdir/two'),
            full_path('one_symlink/many_subdirs/a_subdir/another_subdir/oimsdf'),
            full_path('one_symlink/many_subdirs/a_subdir/another_subdir/even_another_subdir/ppp')])


        # test upload_file and upload_paths together
        upload_file = open(upload_file_path, 'w')
        upload_file.write(full_path('single_file'))
        upload_file.close()
        args = {'cmd': 'some command',
                'upload_only': True,
                'upload_file': upload_file_path,
                'upload_paths': [full_path('one_symlink')]}

        self.assertEqual(Submit(args).get_upload_files(),[
            full_path('single_file/foo'),
            full_path('one_symlink/nnn'),
            full_path('one_symlink/many_subdirs/bar'),
            full_path('one_symlink/many_subdirs/one'),
            full_path('one_symlink/many_subdirs/a_subdir/adsf'),
            full_path('one_symlink/many_subdirs/a_subdir/three'),
            full_path('one_symlink/many_subdirs/a_subdir/two'),
            full_path('one_symlink/many_subdirs/a_subdir/another_subdir/oimsdf'),
            full_path('one_symlink/many_subdirs/a_subdir/another_subdir/even_another_subdir/ppp')])


    def test_make_request(self):
        """This test depends on an object in :
          gs://conductor-test/accounts/testing/files/myObject
        with content:
          'hi'
        """
        base_url = 'http://test.conductor.io:8080'

        try:
            uri_path = '/api/files/ping'
            job = make_request(uri_path)
        except Exception:
            message = str(traceback.print_exc())
            message += "could not connect to app. are you running a dev env?"
            self.fail(message)


        # this should produce a 400
        uri_path = '/api/files/stat'
        with self.assertRaises(HTTPError):
        # with self.assertRaises(HttpError):
            job = make_request(uri_path=uri_path)


        uri_path = '/api/files/stat'
        params = {'filename':'myObject'}
        job = make_request(uri_path=uri_path,params=params)


    def test_get_upload_url(self):
        args = {'url': 'http://test.conductor.io:8080' }

        uploader = Uploader(args)
        self.assertEqual(uploader.__class__.__name__,'Uploader')

        file_name = full_path('upload_file1')
        md5= uploader.get_md5(file_name)
        self.assertEqual(md5,'n\x03G=\xb6\xc1\xae\x89<\xf1?H\xcb\xd9<\xf1')

        b64 = uploader.get_base64_md5(file_name)
        self.assertEqual(b64,'bgNHPbbBrok88T9Iy9k88Q==')

        upload_url = uploader.get_upload_url(file_name + 'asdfasdf')
        self.assertNotEqual(upload_url,'')




if __name__ == '__main__':
        unittest.main()
