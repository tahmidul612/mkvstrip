# Unittest related imports
from unittest import mock
import subprocess
import unittest
import json
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

        input_file = '/movies/test.mkv'
        real_path = os.path.realpath(input_file)
        self.mock_sub.assert_called_once_with(['/usr/bin/mkvmerge', '-i', '-F', 'json', real_path],
                                              stdout=subprocess.PIPE)

    def test_clean_tracks(self):
        self.mock_sub.return_value.communicate.return_value = (read("clean_tracks.json"), None)

        input_file = '/movies/test.mkv'
        real_path = os.path.realpath(input_file)
        mkvstrip.main(["-b", "/usr/bin/mkvmerge", "-l", "eng", input_file])
        self.mock_isfile.assert_called_with(real_path)
        self.mock_sub.assert_called_with(['/usr/bin/mkvmerge', '-i', '-F', 'json', real_path],
                                         stdout=subprocess.PIPE)

    @mock.patch.multiple(os, utime=mock.DEFAULT, unlink=mock.DEFAULT, rename=mock.DEFAULT, stat=mock.DEFAULT)
    def test_remove_tracks(self, **multi):
        side_effect = [io.StringIO("data\nProgress 50%"), io.StringIO("data\nProgress 100%")]
        type(self.mock_sub.return_value).stdout = mock.PropertyMock(side_effect=side_effect)
        multi["stat"].return_value.configure_mock(st_atime=1512084181.0, st_mtime=1512084181.0)
        self.mock_sub.return_value.configure_mock(**{"communicate.return_value": (read("remove_tracks.json"), None),
                                                     "poll.side_effect": [None, None, 0]})

        input_file = '/movies/test.mkv'
        real_path = os.path.realpath(input_file)
        mkvstrip.main(["-b", "/usr/bin/mkvmerge", "-l", "eng", input_file])
        self.mock_isfile.assert_called_with(real_path)
        multi["stat"].assert_called_with(real_path)
        multi["unlink"].assert_called_with(real_path)
        multi["rename"].assert_called_with(real_path + ".tmp", real_path)
        multi["utime"].assert_called_with(real_path + ".tmp", (1512084181.0, 1512084181.0))
        self.assertTrue(self.mock_sub.called)

    def test_remove_tracks_dry_run(self):
        self.mock_sub.return_value.communicate.return_value = (read("remove_tracks.json"), None)

        input_file = '/movies/test.mkv'
        real_path = os.path.realpath(input_file)
        mkvstrip.main(["--dry-run", "-b", "/usr/bin/mkvmerge", "-l", "eng", input_file])
        self.mock_sub.assert_called_with(['/usr/bin/mkvmerge', '-i', '-F', 'json', real_path],
                                         stdout=subprocess.PIPE)

    def test_remove_audio_only_dry_run(self):
        self.mock_sub.return_value.communicate.return_value = (read("remove_audio_track.json"), None)

        input_file = '/movies/test.mkv'
        real_path = os.path.realpath(input_file)
        mkvstrip.main(["--dry-run", "-b", "/usr/bin/mkvmerge", "-l", "eng", input_file])
        self.mock_sub.assert_called_with(['/usr/bin/mkvmerge', '-i', '-F', 'json', real_path],
                                         stdout=subprocess.PIPE)

    def test_remove_sub_only_dry_run(self):
        self.mock_sub.return_value.communicate.return_value = (read("remove_sub_track.json"), None)

        input_file = '/movies/test.mkv'
        real_path = os.path.realpath(input_file)
        mkvstrip.main(["--dry-run", "-b", "/usr/bin/mkvmerge", "-l", "eng", input_file])
        self.mock_sub.assert_called_with(['/usr/bin/mkvmerge', '-i', '-F', 'json', real_path],
                                         stdout=subprocess.PIPE)


class TestWalk(unittest.TestCase):
    def setUp(self):
        patch_isfile = mock.patch("os.path.isfile", return_value=False)
        patch_isdir = mock.patch("os.path.isdir", return_value=False)
        self.mock_isfile = patch_isfile.start()
        self.mock_isdir = patch_isdir.start()
        self.addCleanup(mock.patch.stopall)

    def test_file(self):
        self.mock_isfile.return_value = True
        ret = mkvstrip.walk_directory("/movies/test.mkv")
        self.assertListEqual(ret, ["/movies/test.mkv"])
        self.assertTrue(self.mock_isfile.called)
        self.mock_isdir.assert_not_called()

    def test_file_invalid(self):
        self.mock_isfile.return_value = True
        with self.assertRaises(ValueError):
            mkvstrip.walk_directory("/movies/desktop.ini")

        self.assertTrue(self.mock_isfile.called)
        self.mock_isdir.assert_not_called()

    @mock.patch("os.walk", return_value=[("/movies/", [], ["movie_one.mkv", "desktop.ini", "movie_two.mkv"])])
    def test_dir(self, mock_walk):
        self.mock_isdir.return_value = True
        ret = mkvstrip.walk_directory("/movies/")
        self.assertListEqual(ret, ["/movies/movie_one.mkv", "/movies/movie_two.mkv"])
        self.assertTrue(self.mock_isfile.called)
        self.assertTrue(self.mock_isdir.called)
        self.assertTrue(mock_walk.called)

    @mock.patch("os.walk", return_value=[("/movies/", [], ["desktop.ini"])])
    def test_dir_no_mkv(self, mock_walk):
        self.mock_isdir.return_value = True
        ret = mkvstrip.walk_directory("/movies/")
        self.assertFalse(ret)
        self.assertTrue(self.mock_isfile.called)
        self.assertTrue(self.mock_isdir.called)
        self.assertTrue(mock_walk.called)

    def test_not_found(self):
        with self.assertRaises(FileNotFoundError):
            mkvstrip.walk_directory("/movies/")

        self.assertTrue(self.mock_isfile.called)
        self.assertTrue(self.mock_isdir.called)


class TestRemux(unittest.TestCase):
    def setUp(self):
        patch_args = mock.patch.object(mkvstrip, "cli_args", dry_run=False)
        self.mock_args = patch_args.start()
        self.addCleanup(mock.patch.stopall)

    def test_dry_run(self):
        self.mock_args.dry_run = True
        with mock.patch("sys.stdout", new_callable=io.StringIO) as stdout:
            ret = mkvstrip.remux_file(["/usr/bin/mkvmerge"])

        self.assertEqual(stdout.getvalue(), "Dry run 100%\n")
        self.assertFalse(ret)

    @mock.patch.object(subprocess, "Popen", spec=True)
    def test_run(self, mock_sub):
        side_effect = [io.StringIO("data\nProgress 50%"), io.StringIO("data\nProgress 100%")]
        type(mock_sub.return_value).stdout = mock.PropertyMock(side_effect=side_effect)
        mock_sub.return_value.configure_mock(**{"poll.side_effect": [None, None, 0]})
        with mock.patch("sys.stdout", new_callable=io.StringIO) as stdout:
            ret = mkvstrip.remux_file(["/usr/bin/mkvmerge"])

        self.assertEqual(stdout.getvalue(), "Progress 0%\rProgress 50%\rProgress 100%\n")
        self.assertTrue(mock_sub.called)
        self.assertTrue(mock_sub.return_value.poll.called)
        self.assertTrue(ret)

    @mock.patch.object(subprocess, "Popen", spec=True)
    def test_fail(self, mock_sub):
        type(mock_sub.return_value).stdout = mock.PropertyMock(return_value=io.StringIO("fake data"))
        mock_sub.return_value.configure_mock(**{"poll.return_value": -1})
        ret = mkvstrip.remux_file(["/usr/bin/mkvmerge"])
        self.assertTrue(mock_sub.called)
        self.assertTrue(mock_sub.return_value.poll.called)
        self.assertFalse(ret)


class TestReplace(unittest.TestCase):
    def setUp(self):
        self.tmp_file = "/movies/test.mkv.tmp"
        self.org_file = "/movies/test.mkv"

        patch_multi = mock.patch.multiple(os, utime=mock.DEFAULT, unlink=mock.DEFAULT, rename=mock.DEFAULT)
        patch_stat = mock.patch.object(os, "stat", spec=True)

        self.mock_multi = patch_multi.start()
        self.mock_stat = mock_stat = patch_stat.start()
        self.addCleanup(mock.patch.stopall)

        mock_stat.return_value.configure_mock(st_atime=1512084181.0, st_mtime=1512084181.0)

    def test_run(self):
        mkvstrip.replace_file(self.tmp_file, self.org_file)
        self.mock_stat.assert_called_with(self.org_file)
        self.mock_multi["utime"].assert_called_with(self.tmp_file, (1512084181.0, 1512084181.0))
        self.mock_multi["unlink"].assert_called_with(self.org_file)
        self.mock_multi["rename"].assert_called_with(self.tmp_file, self.org_file)

    def test_unlink_fail(self):
        self.mock_multi["unlink"].side_effect = [EnvironmentError, None]
        mkvstrip.replace_file(self.tmp_file, self.org_file)
        self.mock_multi["unlink"].assert_has_calls([mock.call(self.org_file), mock.call(self.tmp_file)])
        self.mock_multi["rename"].assert_not_called()

    def test_rename_fail(self):
        self.mock_multi["rename"].side_effect = EnvironmentError
        mkvstrip.replace_file(self.tmp_file, self.org_file)
        self.mock_multi["rename"].assert_called_with(self.tmp_file, self.org_file)
        self.mock_multi["unlink"].assert_has_calls([mock.call(self.org_file), mock.call(self.tmp_file)])


class TestTrack(unittest.TestCase):
    def test_video_track(self):
        data = json.loads(read("clean_tracks.json"))["tracks"][0]
        track = mkvstrip.Track(data)
        self.assertEqual(str(track), "Track #0: und - MPEG-4p10/AVC/h.264")

    def test_audio_track(self):
        data = json.loads(read("clean_tracks.json"))["tracks"][1]
        track = mkvstrip.Track(data)
        self.assertEqual(str(track), "Track #2: eng - AC-3")

    def test_subtitle_track(self):
        data = json.loads(read("clean_tracks.json"))["tracks"][2]
        track = mkvstrip.Track(data)
        self.assertEqual(str(track), "Track #5: eng - SubRip/SRT")


class TestMKVFile(unittest.TestCase):
    def setUp(self):
        patch_sub = mock.patch.object(subprocess, "Popen", spec=True, returncode=0)
        patch_args = mock.patch.object(mkvstrip, "cli_args",
                                       mkvmerge_bin="/usr/bin/mkvmerge",
                                       language=["und", "eng"],
                                       subs_language=None)
        self.mock_sub = patch_sub.start()
        self.mock_args = patch_args.start()
        self.addCleanup(mock.patch.stopall)

    def test_init(self):
        self.mock_sub.return_value.communicate.return_value = (read("clean_tracks.json"), None)
        mkv = mkvstrip.MKVFile("/movies/test.mkv")
        self.assertFalse(mkv.remux_required)
        self.mock_sub.assert_called_with(["/usr/bin/mkvmerge", "-i", "-F", "json", "/movies/test.mkv"],
                                         stdout=subprocess.PIPE)

        self.assertTrue(self.mock_sub.return_value.communicate.called)
        self.assertTrue(len(mkv.video_tracks) == 1)
        self.assertTrue(len(mkv.audio_tracks) == 1)
        self.assertTrue(len(mkv.subtitle_tracks) == 1)

    def test_init_fail(self):
        self.mock_sub.return_value.configure_mock(returncode=1)
        self.mock_sub.return_value.communicate.return_value = (read("clean_tracks.json"), None)
        with self.assertRaises(RuntimeError):
            mkvstrip.MKVFile("/movies/test.mkv")

        self.assertTrue(self.mock_sub.return_value.communicate.called)
        self.mock_sub.assert_called_with(["/usr/bin/mkvmerge", "-i", "-F", "json", "/movies/test.mkv"],
                                         stdout=subprocess.PIPE)

    def test_remux_required_one(self):
        self.mock_sub.return_value.communicate.return_value = (read("no_tracks.json"), None)
        mkv = mkvstrip.MKVFile("/movies/test.mkv")
        self.assertFalse(mkv.remux_required)

    def test_remux_required_two(self):
        self.mock_sub.return_value.communicate.return_value = (read("clean_tracks.json"), None)
        mkv = mkvstrip.MKVFile("/movies/test.mkv")
        self.assertFalse(mkv.remux_required)

    def test_remux_required_three(self):
        self.mock_sub.return_value.communicate.return_value = (read("remove_tracks.json"), None)
        mkv = mkvstrip.MKVFile("/movies/test.mkv")
        self.assertTrue(mkv.remux_required)

    def test_remux_required_four(self):
        self.mock_sub.return_value.communicate.return_value = (read("remove_audio_track.json"), None)
        mkv = mkvstrip.MKVFile("/movies/test.mkv")
        self.assertTrue(mkv.remux_required)

    def test_remux_required_five(self):
        self.mock_sub.return_value.communicate.return_value = (read("remove_sub_track.json"), None)
        mkv = mkvstrip.MKVFile("/movies/test.mkv")
        self.assertTrue(mkv.remux_required)

    def test_remux_required_six(self):
        self.mock_sub.return_value.communicate.return_value = (read("remove_sub_track.json"), None)
        mkvstrip.cli_args.language = ['fre']

        mkv = mkvstrip.MKVFile("/movies/test.mkv")
        self.assertFalse(mkv.remux_required)

    @mock.patch.object(mkvstrip, "replace_file")
    @mock.patch.object(mkvstrip, "remux_file", return_value=True)
    def test_remove_tracks_audio(self, mock_remux, mock_replace):
        self.mock_sub.return_value.communicate.return_value = (read("remove_audio_track.json"), None)
        with mock.patch("sys.stdout", new_callable=io.StringIO):
            mkvstrip.MKVFile("/movies/test.mkv").remove_tracks()

        self.assertTrue(mock_remux.called)
        mock_replace.assert_called_with("/movies/test.mkv.tmp", "/movies/test.mkv")

    @mock.patch.object(mkvstrip, "replace_file")
    @mock.patch.object(mkvstrip, "remux_file", return_value=True)
    def test_remove_tracks_sub(self, mock_remux, mock_replace):
        self.mock_sub.return_value.communicate.return_value = (read("remove_sub_track.json"), None)
        with mock.patch("sys.stdout", new_callable=io.StringIO):
            mkvstrip.MKVFile("/movies/test.mkv").remove_tracks()

        self.assertTrue(mock_remux.called)
        mock_replace.assert_called_with("/movies/test.mkv.tmp", "/movies/test.mkv")

    @mock.patch.object(mkvstrip, "replace_file")
    @mock.patch.object(mkvstrip, "remux_file", return_value=True)
    def test_remove_tracks_all(self, mock_remux, mock_replace):
        self.mock_sub.return_value.communicate.return_value = (read("remove_tracks.json"), None)
        with mock.patch("sys.stdout", new_callable=io.StringIO):
            mkvstrip.MKVFile("/movies/test.mkv").remove_tracks()

        self.assertTrue(mock_remux.called)
        mock_replace.assert_called_with("/movies/test.mkv.tmp", "/movies/test.mkv")

    @mock.patch.object(os, "remove")
    @mock.patch.object(os.path, "exists", return_value=False)
    @mock.patch.object(mkvstrip, "remux_file", return_value=False)
    def test_remove_fail_one(self, mock_remux, mock_exists, mock_remove):
        self.mock_sub.return_value.communicate.return_value = (read("remove_tracks.json"), None)
        with mock.patch("sys.stdout", new_callable=io.StringIO):
            mkvstrip.MKVFile("/movies/test.mkv").remove_tracks()

        self.assertTrue(mock_remux.called)
        mock_exists.assert_called_with("/movies/test.mkv.tmp")
        mock_remove.assert_not_called()

    @mock.patch.object(os, "remove")
    @mock.patch.object(os.path, "exists", return_value=True)
    @mock.patch.object(mkvstrip, "remux_file", return_value=False)
    def test_remove_fail_one(self, mock_remux, mock_exists, mock_remove):
        self.mock_sub.return_value.communicate.return_value = (read("remove_tracks.json"), None)
        with mock.patch("sys.stdout", new_callable=io.StringIO):
            mkvstrip.MKVFile("/movies/test.mkv").remove_tracks()

        self.assertTrue(mock_remux.called)
        mock_exists.assert_called_with("/movies/test.mkv.tmp")
        mock_remove.assert_called_with("/movies/test.mkv.tmp")
