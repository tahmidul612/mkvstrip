# Standard Library
from functools import lru_cache
import subprocess
import os


class MKVFile(object):
    """
    Extracts track information contained within a Matroska file and
    checks for unwanted audio & subtitle tracks.

    :param str path: Path to the Matroska file to process.
    """
    def __init__(self, path, langs):
        self.dirpath, self.filename = os.path.split(path)
        self.subtitle_tracks = []
        self.video_tracks = []
        self.audio_tracks = []
        self.path = path
        self.langs = langs

        # Commandline auguments for extracting info about the mkv file
        command = [cli_args.mkvmerge_bin, "-i", "-F", "json", path]

        # Ask mkvmerge for the json info
        process = subprocess.Popen(command, stdout=subprocess.PIPE, universal_newlines=True)
        stdout, _ = process.communicate(timeout=10)
        if process.returncode:
            raise RuntimeError("[Error {}] mkvmerge failed to identify: {}".format(process.returncode, self.filename))

        # Process the json response
        json_data = json.loads(stdout)
        track_map = {"video": self.video_tracks, "audio": self.audio_tracks, "subtitles": self.subtitle_tracks}
        for track_data in json_data["tracks"]:
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
        languages_to_keep = self.langs
        if track_type == 'audio':
            tracks = self.audio_tracks
        elif track_type == 'subtitle':
            if cli_args.subs_language is not None:
                languages_to_keep = cli_args.subs_language
            tracks = self.subtitle_tracks
        else:
            assert False

        # Lists of track to keep & remove
        remove = []
        keep = []
        # Iterate through all tracks to find which track to keep or remove
        for track in tracks:
            if track.lang in languages_to_keep:
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
        if cli_args.verbose:
            print("Checking", self.path)

        # Check if any tracks need to be removed
        # We will only remove audio tracks when there is also audio tracks to keep

        audio_to_keep, audio_to_remove = self._filtered_tracks("audio")
        subs_to_keep, subs_to_remove = self._filtered_tracks("subtitle")

        has_no_audio = not self.audio_tracks
        has_something_to_remove = audio_to_remove or subs_to_remove
        if (has_no_audio or audio_to_keep) and has_something_to_remove:
            return True
        else:
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
            if ((track_type == "subtitle" and cli_args.no_subtitles)
                    or keep) and remove:
                keep_ids = []

                print("Retaining %s track(s):" % track_type)
                for count, track in enumerate(keep):
                    keep_ids.append(str(track.id))
                    print("   ", track)

                    # Set the first track as default
                    command.extend(["--default-track", ":".join((str(track.id), "0" if count else "1"))])

                # Set which tracks are to be kepth
                if keep_ids:
                    command.extend(["--%s-tracks" % track_type,
                                    ",".join(keep_ids)])
                elif track_type == "subtitle":
                    command.extend(["--no-subtitles"])

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
