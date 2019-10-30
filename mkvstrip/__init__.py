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

__version__ = "1.1.0"
