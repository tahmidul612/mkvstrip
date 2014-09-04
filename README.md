mkvstrip
========

Python script that acts as a front end for mkvtoolnix to remove excess audio and subtitle streams from mkv files as well as correct title information. The intent is to allow someone to setup a cronjob to run this script at regular intervals (for example, every night) and this script will keep your Movie collection from collecting excessive tracks.

This script was designed for running in a FreeNAS jail (FreeBSD) but should run in any OS that meets the requirements of this script.

Requirements:

1.  MKVToolNix 7.0.0 and 7.1.0 tested (should work on all recent and future versions though)
2.  Python 2.7.x

The ultimate goal is to make this script something that can be setup by variables in the script and then run nightly as a cronjob to keep your collection optimal.

Future features to add:

1.  Clean up the output of -h to be a bit more "user friendly".

Thanks to the following for their help with getting this working:

Terminus, cyberjock

Cyberjock is the original creator of this script. I just heavily modifyed it for my own use.
Original repo here (https://github.com/cyberjock/mkvstrip)