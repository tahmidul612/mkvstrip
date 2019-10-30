# Standard Library
import argparse
import sys
import os

# Global parser namespace
cli_args = None


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


if sys.platform == "win32":
    BIN_DEFAULT = "C:\\\\Program Files\\MKVToolNix\\mkvmerge.exe"
else:
    BIN_DEFAULT = "mkvmerge"

# Create Parser to parse the required arguments
parser = argparse.ArgumentParser(
    description="Strips unnecessary tracks from MKV files."
)

parser.add_argument(
    "paths",
    nargs='+',
    help="Where your MKV files are stored. Can be a directories or files."
)

parser.add_argument(
    "-t",
    "--dry-run",
    action="store_true",
    help="Enable mkvmerge dry run for testing."
)

parser.add_argument(
    "-b",
    "--mkvmerge-bin",
    default=BIN_DEFAULT,
    action="store",
    metavar="path",
    help="The path to the MKVMerge executable."
)

parser.add_argument(
    "-l",
    "--language",
    default=["und"],
    metavar="lang",
    action=AppendSplitter,
    required=True,
    help="Comma-separated list of subtitle and audio languages to retain. E.g. eng,fre. "
         "Language codes can be either the 3 letters bibliographic ISO-639-2 form "
         "(like \"fre\" for French), or such a language code followed by a dash and a country code "
         "for specialities in languages (like \"fre-ca\" for Canadian French). "
         "Country codes are the same as used for internet domains."
)

parser.add_argument(
    "-s",
    "--subs-language",
    metavar="subs-lang",
    action=AppendSplitter,
    required=False,
    dest="subs_language",
    default=None,
    help="If specified, defines subtitle languages to retain. See description of --language for syntax."
)

parser.add_argument(
    "-n",
    "--no-subtitles",
    default=False,
    action="store_true",
    dest="no_subtitles",
    help="If no subtitles match the languages to retain, strip all subtitles."
)

parser.add_argument(
    "-v",
    "--verbose",
    action="store_true",
    default=False,
    help="Verbose output."
)

parser.add_argument(
    "-r",
    "--recurse",
    action="store_true",
    default=False,
    help="Recurse through all paths on the command line."
)


def main(params=None):
    """
    Check all mkv files an remove unnecessary tracks.

    :param params: [opt] List of arguments to pass to argparse.
    :type params: list or tuple
    """
    # Parse the list of given arguments
    globals()["cli_args"] = parser.parse_args(params)

    # Iterate over all found mkv files
    print("Searching for MKV files to process.")
    print("Warning: This may take some time...")
    for path in cli_args.paths:
        strip_tree(path)


if __name__ == "__main__":
    main()
