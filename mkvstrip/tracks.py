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
