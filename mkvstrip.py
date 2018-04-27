#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright: (c) 2013 William Forde (willforde@gmail.com)
# License: GPLv3, see LICENSE for more details
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.

"""
Welcome to mkvstrip.py. This script can go through a folder looking for extraneous
audio and subtitle tracks, and removes them by remuxing the mkv files.

This python script has the following requirements:
1.  Mkvtoolnix
2.  Python3

Note:
A remux should only occur if a change needs to be made to the file.
If no change is required then the file isn't remuxed.

For help with the command line parameters use the -h parameter.

Github: https://github.com/willforde/mkvstrip
Codacy: https://app.codacy.com/app/willforde/mkvstrip/dashboard
"""

__version__ = "1.0.1"

from functools import lru_cache
from operator import itemgetter
import subprocess
import argparse
import time
import json
import sys
import os

# Global parser namespace
cli_args = None


def catch_interrupt(func):
    """Decorator to catch Keyboard Interrupts and silently exit."""
    def wrapper(*args, **kwargs):
        try:
            func(*args, **kwargs)
        except KeyboardInterrupt:
            pass

    # The function been catched
    return wrapper


def walk_directory(path):
    """
    Walk through the given directory to find all mkv files and process them.

    :param str path: Path to Directory containing mkv files.

    :return: List of processed mkv files.
    :rtype: list[str]
    """
    movie_list = []
    if os.path.isfile(path):
        if path.lower().endswith(".mkv"):
            movie_list.append(path)
        else:
            raise ValueError("Given file is not a valid mkv file: '%s'" % path)

    elif os.path.isdir(path):
        dirs = []
        # Walk through the directory
        for dirpath, _, filenames in os.walk(path):
            files = []
            for filename in filenames:
                if filename.lower().endswith(".mkv"):
                    files.append(filename)

            # Sort list of files and add to directory list
            dirs.append((dirpath, sorted(files)))

        # Sort the list of directorys & files and process them
        for dirpath, filenames in sorted(dirs, key=itemgetter(0)):
            for filename in filenames:
                fullpath = os.path.join(dirpath, filename)
                movie_list.append(fullpath)
    else:
        raise FileNotFoundError("[Errno 2] No such file or directory: '%s'" % path)

    return movie_list


def remux_file(command):
    """
    Remux a mkv file with the given parameters.

    :param list command: The list of command parameters to pass to mkvmerge.

    :return: Boolean indicating if remux was successful.
    :rtype: bool
    """
    # Skip remuxing if in dry run mode
    if cli_args.dry_run:
        print("Dry run 100%")
        return False

    sys.stdout.write("Progress 0%")
    sys.stdout.flush()

    try:
        # Call subprocess command to remux file
        process = subprocess.Popen(command, stdout=subprocess.PIPE, universal_newlines=True)

        # Display Percentage until subprocess has finished
        retcode = process.poll()
        while retcode is None:
            # Sleep for a quarter second and then dislay progress
            time.sleep(.25)
            for line in iter(process.stdout.readline, ""):
                if "progress" in line.lower():
                    sys.stdout.write("\r%s" % line.strip())
                    sys.stdout.flush()

            # Check return code of subprocess
            retcode = process.poll()

        # Check if return code indicates an error
        sys.stdout.write("\n")
        if retcode:
            raise subprocess.CalledProcessError(retcode, command, output=process.stdout)

    except subprocess.CalledProcessError as e:
        print("Remux failed!")
        print(e)
        return False
    else:
        return True


def replace_file(tmp_file, org_file):
    """
    Replaces the original mkv file with the newly remuxed temp file.

    :param str tmp_file: The temporary mkv file
    :param str org_file: The original mkv file to replace.
    """
    # Preserve timestamp
    stat = os.stat(org_file)
    os.utime(tmp_file, (stat.st_atime, stat.st_mtime))

    # Overwrite original file
    try:
        os.unlink(org_file)
        os.rename(tmp_file, org_file)
    except EnvironmentError as e:
        os.unlink(tmp_file)
        print("Renaming failed: %s => %s" % (tmp_file, org_file))
        print(e)


class AppendSplitter(argparse.Action):
    """
    Custom action to split multiple parameters which are
    separated by a comma, and append then to a default list.
    """
    def __call__(self, _, namespace, values, option_string=None):
        items = self.default if isinstance(self.default, list) else []
        items.extend(values.split(","))
        setattr(namespace, self.dest, items)


class RealPath(argparse.Action):
    """
    Custom action to convert given path to a full canonical path,
    eliminating any symbolic links if encountered.
    """
    def __call__(self, _, namespace, value, option_string=None):
        setattr(namespace, self.dest, os.path.realpath(value))


class Track(object):
    """
    Class to handle mkv track information.

    :param dict track_data: The track data given by mkvmerge.
    """
    def __init__(self, track_data):
        self.lang = track_data["properties"].get("language", "und")
        self.codec = track_data["codec"]
        self.type = track_data["type"]
        self.id = track_data["id"]

    def __str__(self):
        return "Track #{}: {} - {}".format(self.id, self.lang, self.codec)


class MKVFile(object):
    """
    Extracts track information contained within a Matroska file and
    checks for unwanted audio & subtitle tracks.

    :param str path: Path to the Matroska file to process.
    """
    def __init__(self, path):
        self.dirpath, self.filename = os.path.split(path)
        self.subtitle_tracks = []
        self.video_tracks = []
        self.audio_tracks = []
        self.path = path

        # Commandline auguments for extracting info about the mkv file
        command = [cli_args.mkvmerge_bin, "-i", "-F", "json", path]

        # Ask mkvmerge for the json info
        process = subprocess.Popen(command, stdout=subprocess.PIPE)
        stdout, _ = process.communicate(timeout=10)
        if process.returncode:
            raise RuntimeError("[Error {}] mkvmerge failed to identify: {}".format(process.returncode, self.filename))

        # Process the json response
        json__data = json.loads(stdout)
        track_map = {"video": self.video_tracks, "audio": self.audio_tracks, "subtitles": self.subtitle_tracks}
        for track_data in json__data["tracks"]:
            track_obj = Track(track_data)
            track_map[track_obj.type].append(track_obj)

    @lru_cache()
    def _filtered_tracks(self, track_type):
        """
        Return a tuple consisting of tracks to keep and tracks to remove, if
        there are indeed tracks that need to be removed, else return False.

        Available track types:
            subtitle
            audio

        :param str track_type: The track type to check.

        :return: Tuple of tracks to keep and remove
        :rtype: tuple[list[Track]]
        """
        # Lists of track to keep & remove
        remove = []
        keep = []

        # Iterate through all tracks to find which track to keep or remove
        for track in {"audio": self.audio_tracks, "subtitle": self.subtitle_tracks}[track_type]:
            if track.lang in cli_args.language:
                # Tracks we want to keep
                keep.append(track)
            else:
                # Tracks we want to remove
                remove.append(track)

        return keep, remove

    @property
    def remux_required(self):
        """
        Check if any remuxing of the mkv files is required.

        :return: Return True if remuxing is required else False
        :rtype: bool
        """
        # Check if any tracks need to be removed
        # We will only remove tracks when there is also tracks that will be kepth
        for track_type in ("audio", "subtitle"):
            keep, remove = self._filtered_tracks(track_type)
            if keep and remove:
                return True

        # If we get this far then no remuxing is required
        return False

    def remove_tracks(self):
        """Remove the unwanted tracks."""
        # The command line args required to remux the mkv file
        command = [cli_args.mkvmerge_bin, "--output"]
        print("\nRemuxing:", self.filename)
        print("============================")

        # Output the remuxed file to a temp tile, This will protect
        # the original file from been currupted if anything goes wrong
        tmp_file = u"%s.tmp" % self.path
        command.append(tmp_file)
        command.extend(["--title", self.filename[:-4]])

        # Iterate all tracks and mark which tracks are to be kepth
        for track_type in ("audio", "subtitle"):
            keep, remove = self._filtered_tracks(track_type)
            if keep and remove:
                keep_ids = []

                print("Retaining %s track(s):" % track_type)
                for count, track in enumerate(keep):
                    keep_ids.append(str(track.id))
                    print("   ", track)

                    # Set the first track as default
                    command.extend(["--default-track", ":".join((str(track.id), "0" if count else "1"))])

                # Set which tracks are to be kepth
                command.extend(["--%s-tracks" % track_type, ",".join(keep_ids)])

                # This is just here to report what tracks will be removed
                print("Removing %s track(s):" % track_type)
                for track in remove:
                    print("   ", track)

                print("----------------------------")

        # Add source mkv file to command and remux
        command.append(self.path)
        if remux_file(command):
            replace_file(tmp_file, self.path)
        else:
            # If we get here then something went wrong
            # So time to do some cleanup
            if os.path.exists(tmp_file):
                os.remove(tmp_file)


@catch_interrupt
def main(params=None):
    """
    Check all mkv files an remove unnecessary tracks.

    :param params: [opt] List of arguments to pass to argparse.
    :type params: list or tuple
    """
    # Create Parser to parse the required arguments
    parser = argparse.ArgumentParser(description="Strips unnecessary tracks from MKV files.")
    parser.add_argument("path", action=RealPath,
                        help="Where your MKV files are stored. Can be a directory or a file.")
    parser.add_argument("-t", "--dry-run", action="store_true", help="Enable mkvmerge dry run for testing.")
    parser.add_argument("-b", "--mkvmerge-bin", action="store", metavar="path", required=True,
                        help="The path to the MKVMerge executable.")
    parser.add_argument("-l", "--language", default=["und"], metavar="lang", action=AppendSplitter, required=True,
                        help="3-character language code (e.g. eng). To retain multiple, "
                             "separate languages with a comma (e.g. eng,spa).")

    # Parse the list of given arguments
    globals()["cli_args"] = parser.parse_args(params)

    # Iterate over all found mkv files
    print("Searching for MKV files to process.")
    print("Warning: This may take some time...")
    for mkv_file in walk_directory(cli_args.path):
        mkv_obj = MKVFile(mkv_file)
        if mkv_obj.remux_required:
            mkv_obj.remove_tracks()


if __name__ == "__main__":
    main()
