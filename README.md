[![Codacy Badge](https://api.codacy.com/project/badge/Grade/181ade83b7c84a738ee74d913bbe9eeb)](https://www.codacy.com/app/willforde/mkvstrip?utm_source=github.com&amp;utm_medium=referral&amp;utm_content=willforde/mkvstrip&amp;utm_campaign=Badge_Grade)

mkvstrip
========

Python script that acts as a front end for mkvtoolnix to remove excess
audio and subtitle streams from mkv files as well as correct title
information. The intent is to allow someone to setup a cronjob to run
this script at regular intervals (for example, every night) and this
script will keep your Movie collection from collecting excessive tracks.

Requirements:

1.  MKVToolNix
2.  Python3

Usage
=====

```
mkvstrip.py [-h] [-t] -b path -l lang path

positional arguments:
  path                          Path to where your MKVs are stored. Can be a directory
                                or a file.

optional arguments:
  -h, --help                    show this help message and exit
  -t, --dry-run                 Enable mkvmerge dry run for testing.
  -b path, --mkvmerge-bin path  The path to the MKVMerge executable.
  -l lang, --language lang      3-character language code (e.g. eng). To retain
                                multiple, separate languages with a comma (e.g.
                                eng,spa).
```
