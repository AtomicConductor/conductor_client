import os
import unittest
import sys
import traceback
import urllib2

# TODO: make urllib3
from urllib2 import HTTPError

# add ../conductor to path
test_dir = os.path.dirname(os.path.realpath(__file__))
os.chdir(test_dir)
base_dir = os.path.dirname(test_dir)
sys.path.append(base_dir)

upload_test_helpers = os.path.join(test_dir,'upload_helpers')
os.environ['FLASK_CONF'] = 'TEST'
# os.environ['CONDUCTOR_DEVELOPMENT'] = '1'
TEST = True

from conductor.lib.conductor_submit import Uploader, Submit, make_request


class UploaderTest(unittest.TestCase):

    def test_get_children(self):
        single_file_test_dir = os.path.join(upload_test_helpers,'single_file')

        single_file = '%s/single_file/foo' % upload_test_helpers
        self.assertEqual(Uploader().get_children(single_file),
                         [single_file])

        dir_with_single_file = '%s/single_file' % upload_test_helpers
        self.assertEqual(Uploader().get_children(dir_with_single_file),
                         [single_file])

        dir_with_two_files = '%s/two_files' % upload_test_helpers
        self.assertEqual(Uploader().get_children(dir_with_two_files),
                         ['%s/two_files/one' % upload_test_helpers,
                          '%s/two_files/two' % upload_test_helpers])

        dir_with_a_subdir = '%s/one_subdir' % upload_test_helpers
        self.assertEqual(Uploader().get_children(dir_with_a_subdir),
                         ['%s/one_subdir/one' % upload_test_helpers,
                          '%s/one_subdir/a_subdir/three' % upload_test_helpers,
                          '%s/one_subdir/a_subdir/two' % upload_test_helpers])

        dir_with_many_subdirs = '%s/many_subdirs' % upload_test_helpers
        self.assertEqual(Uploader().get_children(dir_with_many_subdirs),
                         ['%s/many_subdirs/bar' % upload_test_helpers,
                          '%s/many_subdirs/one' % upload_test_helpers,
                          '%s/many_subdirs/a_subdir/adsf' % upload_test_helpers,
                          '%s/many_subdirs/a_subdir/three' % upload_test_helpers,
                          '%s/many_subdirs/a_subdir/two' % upload_test_helpers,
                          '%s/many_subdirs/a_subdir/another_subdir/oimsdf' % upload_test_helpers,
                          '%s/many_subdirs/a_subdir/another_subdir/even_another_subdir/ppp' % upload_test_helpers])

        dir_with_symlink = '%s/one_symlink' % upload_test_helpers
        self.assertEqual(Uploader().get_children(dir_with_symlink),
                         ['%s/one_symlink/nnn' % upload_test_helpers,
                          '%s/one_symlink/many_subdirs/bar' % upload_test_helpers,
                          '%s/one_symlink/many_subdirs/one' % upload_test_helpers,
                          '%s/one_symlink/many_subdirs/a_subdir/adsf' % upload_test_helpers,
                          '%s/one_symlink/many_subdirs/a_subdir/three' % upload_test_helpers,
                          '%s/one_symlink/many_subdirs/a_subdir/two' % upload_test_helpers,
                          '%s/one_symlink/many_subdirs/a_subdir/another_subdir/oimsdf' % upload_test_helpers,
                          '%s/one_symlink/many_subdirs/a_subdir/another_subdir/even_another_subdir/ppp' % upload_test_helpers])

        with self.assertRaises(ValueError):
            Uploader().get_children('/adsf/asdvawe/asdfvasdv/aotmasdfp')


    def test_get_upload_files(self):
        # create dummy upload file
        # TODO: make this not suck
        upload_file_path = '/tmp/upload_file'
        upload_file = open(upload_file_path, 'w')
        upload_file.write('%s/single_file' % upload_test_helpers)
        upload_file.close()


        # test most basic case
        args = {'cmd': 'some command',
                'upload_file': upload_file_path,
                'upload_only': True,
                }
        print "args is %s" % args
        s1 = '%s/single_file/foo' % upload_test_helpers
        print "s1 is %s" % s1

        self.assertEqual(Submit(args).get_upload_files(),['%s/single_file/foo' % upload_test_helpers ])
        # self.assertEqual(Submit(args).get_upload_files(),['upload_helpers/single_file/foo'])


        # test two items in the upload file
        upload_file = open(upload_file_path, 'w')
        upload_file.write('%s/single_file,%s/one_symlink' % (upload_test_helpers,upload_test_helpers))
        upload_file.close()
        args = {'cmd': 'some command',
                'upload_file': upload_file_path,
                'upload_only': True}
        self.assertEqual(Submit(args).get_upload_files(),[
            '%s/single_file/foo' % upload_test_helpers,
            '%s/one_symlink/nnn' % upload_test_helpers,
            '%s/one_symlink/many_subdirs/bar' % upload_test_helpers,
            '%s/one_symlink/many_subdirs/one' % upload_test_helpers,
            '%s/one_symlink/many_subdirs/a_subdir/adsf' % upload_test_helpers,
            '%s/one_symlink/many_subdirs/a_subdir/three' % upload_test_helpers,
            '%s/one_symlink/many_subdirs/a_subdir/two' % upload_test_helpers,
            '%s/one_symlink/many_subdirs/a_subdir/another_subdir/oimsdf' % upload_test_helpers,
            '%s/one_symlink/many_subdirs/a_subdir/another_subdir/even_another_subdir/ppp' % upload_test_helpers])


        # test upload_paths
        args = {'cmd': 'some command',
                'upload_only': True,
                'upload_paths': ['%s/single_file' % upload_test_helpers,
                                 '%s/one_symlink' % upload_test_helpers]}

        self.assertEqual(Submit(args).get_upload_files(),[
            '%s/single_file/foo' % upload_test_helpers,
            '%s/one_symlink/nnn' % upload_test_helpers,
            '%s/one_symlink/many_subdirs/bar' % upload_test_helpers,
            '%s/one_symlink/many_subdirs/one' % upload_test_helpers,
            '%s/one_symlink/many_subdirs/a_subdir/adsf' % upload_test_helpers,
            '%s/one_symlink/many_subdirs/a_subdir/three' % upload_test_helpers,
            '%s/one_symlink/many_subdirs/a_subdir/two' % upload_test_helpers,
            '%s/one_symlink/many_subdirs/a_subdir/another_subdir/oimsdf' % upload_test_helpers,
            '%s/one_symlink/many_subdirs/a_subdir/another_subdir/even_another_subdir/ppp' % upload_test_helpers])


        # test upload_file and upload_paths together
        upload_file = open(upload_file_path, 'w')
        upload_file.write('%s/single_file' % upload_test_helpers)
        upload_file.close()
        args = {'cmd': 'some command',
                'upload_only': True,
                'upload_file': upload_file_path,
                'upload_paths': ['%s/one_symlink' % upload_test_helpers]}

        self.assertEqual(Submit(args).get_upload_files(),[
            '%s/single_file/foo' % upload_test_helpers,
            '%s/one_symlink/nnn' % upload_test_helpers,
            '%s/one_symlink/many_subdirs/bar' % upload_test_helpers,
            '%s/one_symlink/many_subdirs/one' % upload_test_helpers,
            '%s/one_symlink/many_subdirs/a_subdir/adsf' % upload_test_helpers,
            '%s/one_symlink/many_subdirs/a_subdir/three' % upload_test_helpers,
            '%s/one_symlink/many_subdirs/a_subdir/two' % upload_test_helpers,
            '%s/one_symlink/many_subdirs/a_subdir/another_subdir/oimsdf' % upload_test_helpers,
            '%s/one_symlink/many_subdirs/a_subdir/another_subdir/even_another_subdir/ppp' % upload_test_helpers])





    def test_make_request(self):
        """This test depends on an object in :
        gs://conductor-test/accounts/testing/files/myObject with
        content: 'hi'

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
        # with self.assertRaises(ValueError):
        #     uploader = Uploader()

        args = {'url': 'http://test.conductor.io:8080' }

        uploader = Uploader(args)
        self.assertEqual(uploader.__class__.__name__,'Uploader')

        file_name = '%s/upload_file1' % upload_test_helpers
        md5= uploader.get_md5(file_name)
        self.assertEqual(md5,'n\x03G=\xb6\xc1\xae\x89<\xf1?H\xcb\xd9<\xf1')

        b64 = uploader.get_base64_md5(file_name)
        self.assertEqual(b64,'bgNHPbbBrok88T9Iy9k88Q==')

        # file_name = '%s/u' % upload_test_helpers
        # upload_url = uploader.get_upload_url(file_name)
        # print 'file_name is ' + file_name
        # print 'upload_url is ' + upload_url
        # self.assertEqual(upload_url,'')

        upload_url = uploader.get_upload_url(file_name + 'asdfasdf')
        self.assertNotEqual(upload_url,'')




if __name__ == '__main__':
        unittest.main()
