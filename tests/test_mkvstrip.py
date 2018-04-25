# Unittest related imports
from unittest import mock
import subprocess
import unittest
import os
import io

# Module to be tested
import mkvstrip


def read(filename):
    """Open data file and return contents."""
    with open(os.path.join(os.path.dirname(__file__), "mockdata", filename), "r") as stream:
        return stream.read()


class IntegratedTests(unittest.TestCase):
    def setUp(self):
        patch_isfile = mock.patch.object(os.path, "isfile", return_value=True)
        patch_sub = mock.patch.object(subprocess, "Popen", spec=True, returncode=0)
        self.mock_isfile = patch_isfile.start()
        self.mock_sub = patch_sub.start()
        self.addCleanup(mock.patch.stopall)

    def test_no_tracks(self):
        self.mock_sub.return_value.communicate.return_value = (read("no_tracks.json"), None)
        mkvstrip.main(["-b", "/usr/bin/mkvmerge", "-l", "eng", "/movies/test.mkv"])

        self.mock_isfile.assert_called_once_with('/movies/test.mkv')
        self.mock_sub.assert_called_once_with(['/usr/bin/mkvmerge', '-i', '-F', 'json', '/movies/test.mkv'],
                                              stdout=subprocess.PIPE)

    def test_clean_tracks(self):
        self.mock_sub.return_value.communicate.return_value = (read("clean_tracks.json"), None)

        mkvstrip.main(["-b", "/usr/bin/mkvmerge", "-l", "eng", "/movies/test.mkv"])
        self.mock_isfile.assert_called_with('/movies/test.mkv')
        self.mock_sub.assert_called_with(['/usr/bin/mkvmerge', '-i', '-F', 'json', '/movies/test.mkv'],
                                         stdout=subprocess.PIPE)

    @mock.patch.multiple(os, utime=mock.DEFAULT, remove=mock.DEFAULT, rename=mock.DEFAULT, stat=mock.DEFAULT)
    def test_remove_tracks(self, **multi):
        side_effect = [io.StringIO("data\nProgress 50%"), io.StringIO("data\nProgress 100%")]
        type(self.mock_sub.return_value).stdout = mock.PropertyMock(side_effect=side_effect)
        multi["stat"].return_value.configure_mock(st_atime=1512084181, st_mtime=1512084181)
        self.mock_sub.return_value.configure_mock(**{"communicate.return_value": (read("remove_tracks.json"), None),
                                                     "poll.side_effect": [None, None, 0]})

        mkvstrip.main(["-b", "/usr/bin/mkvmerge", "-l", "eng", "/movies/test.mkv"])
        self.mock_isfile.assert_called_with("/movies/test.mkv")
        multi["stat"].assert_called_with("/movies/test.mkv")
        multi["remove"].assert_called_with("/movies/test.mkv")
        multi["rename"].assert_called_with("/movies/test.mkv.tmp", "/movies/test.mkv")
        multi["utime"].assert_called_with("/movies/test.mkv.tmp", (1512084181, 1512084181))
        self.assertTrue(self.mock_sub.called)

    def test_remove_tracks_dry_run(self):
        self.mock_sub.return_value.communicate.return_value = (read("remove_tracks.json"), None)

        mkvstrip.main(["--dry-run", "-b", "/usr/bin/mkvmerge", "-l", "eng", "/movies/test.mkv"])
        self.mock_sub.assert_called_with(['/usr/bin/mkvmerge', '-i', '-F', 'json', '/movies/test.mkv'],
                                         stdout=subprocess.PIPE)

    def test_remove_audio_only_dry_run(self):
        self.mock_sub.return_value.communicate.return_value = (read("remove_autio_track.json"), None)

        mkvstrip.main(["--dry-run", "-b", "/usr/bin/mkvmerge", "-l", "eng", "/movies/test.mkv"])
        self.mock_sub.assert_called_with(['/usr/bin/mkvmerge', '-i', '-F', 'json', '/movies/test.mkv'],
                                         stdout=subprocess.PIPE)

    def test_remove_sub_only_dry_run(self):
        self.mock_sub.return_value.communicate.return_value = (read("remove_sub_track.json"), None)

        mkvstrip.main(["--dry-run", "-b", "/usr/bin/mkvmerge", "-l", "eng", "/movies/test.mkv"])
        self.mock_sub.assert_called_with(['/usr/bin/mkvmerge', '-i', '-F', 'json', '/movies/test.mkv'],
                                         stdout=subprocess.PIPE)

    @mock.patch.object(os.path, "isdir", return_value=True)
    @mock.patch.object(os, "walk", return_value=[("/movies/", [], ["movie_one.mkv", "desktop.ini"])])
    def test_directory(self, mock_walk, *_):
        self.mock_isfile.return_value = False
        self.mock_sub.return_value.communicate.return_value = (read("no_tracks.json"), None)

        mkvstrip.main(["-b", "/usr/bin/mkvmerge", "-l", "eng", "/movies/"])
        mock_walk.assert_called_with("/movies")


class UnitTests(unittest.TestCase):
    pass
