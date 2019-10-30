.. image:: https://badge.fury.io/py/mkvstrip.svg
    :target: https://pypi.org/project/mkvstrip/

.. image:: https://travis-ci.org/willforde/mkvstrip.svg?branch=master
    :target: https://travis-ci.org/willforde/mkvstrip

.. image:: https://coveralls.io/repos/github/willforde/mkvstrip/badge.svg?branch=master
    :target: https://coveralls.io/github/willforde/mkvstrip?branch=master

.. image:: https://api.codacy.com/project/badge/Grade/181ade83b7c84a738ee74d913bbe9eeb
    :target: https://www.codacy.com/app/willforde/mkvstrip?utm_source=github.com&amp;utm_medium=referral&amp;utm_content=willforde/mkvstrip&amp;utm_campaign=Badge_Grade


MKVStrip
--------

Python script, that acts as a front end for mkvtoolnix to remove
excess audio and subtitle streams from mkv files. Also correcting
title information if needed. The intention is to allow someone
to setup a cronjob, to run this script at regular intervals
(for example, every night). Keeping your Movie collection
from collecting excessive tracks.

Requirements:

1.  MKVToolNix
2.  Python3

Install
-------
::

    pip install mkvstrip

Usage
-----
Posix::

    mkvstrip -b /usr/bin/mkvmerge -l eng,fre /mnt/movies

Windows::

    mkvstrip -b C:\\Program/ Files\MKVToolNix\mkvmerge.exe -l eng,fre \\nas\movies


CLI Arguments
-------------
::
    usage: mkvstrip.py [-h] [-t] [-b path] -l lang [-s subs-lang] [-n] [-v]
                    paths [paths ...]

    Strips unnecessary tracks from MKV files.

    positional arguments:
    paths                 Where your MKV files are stored. Can be a directories
                            or files.

    optional arguments:
    -h, --help            show this help message and exit
    -t, --dry-run         Enable mkvmerge dry run for testing.
    -b path, --mkvmerge-bin path
                            The path to the MKVMerge executable.
    -l lang, --language lang
                            Comma-separated list of subtitle and audio languages
                            to retain. E.g. eng,fre. Language codes can be either
                            the 3 letters bibliographic ISO-639-2 form (like "fre"
                            for French), or such a language code followed by a
                            dash and a country code for specialities in languages
                            (like "fre-ca" for Canadian French). Country codes are
                            the same as used for internet domains.
    -s subs-lang, --subs-language subs-lang
                            If specified, defines subtitle languages to retain.
                            See description of --language for syntax.
    -n, --no-subtitles    If no subtitles match the languages to retain, strip
                            all subtitles.
    -v, --verbose         Verbose output.
