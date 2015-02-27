mkvstrip
========

Python script that acts as a front end for mkvtoolnix to remove excess audio and subtitle streams from mkv files as well as correct title information. The intent is to allow someone to setup a cronjob to run this script at regular intervals (for example, every night) and this script will keep your Movie collection from collecting excessive tracks.

This script was designed for running in a FreeNAS jail (FreeBSD) but should run in any OS that meets the requirements of this script.

Requirements:

1.  MKVToolNix 7.0.0 and 7.1.0 tested (should work on all recent and future versions though)
2.  Python 2.7.x

The ultimate goal is to make this script something that can be setup by variables in the script and then run nightly as a cronjob to keep your collection optimal.  See bugs as doing this would cause very undesirable behavior.

Known bugs:

1.  Movies like Alien³, if titled properly, will fail on some systems that have the locale set to "C". This has to do with the character-set used in the filename.  This obviously needs to be fixed because quite a few movies, if titled properly, have odd symbols.

Future features to add:

1.  Clean up the output of -h to be a bit more "user friendly".
2.  Subtitles being streamed into the file.  If "Movie (1900).mkv" exists along with "Movie (1900).eng.srt" then assume the subtitle track needs to be added and add it as language english because that's what the file says it is.  Optionally we can also have it add subtitles as "und" if the filename doesn't specify a language.  After successful merging of the subtitle then delete the .srt file.

I am not an expert python coder so any help with bugs or features from the community is much appreciated!

Thanks to the following for their help with getting this working:

Terminus, willforde