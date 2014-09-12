#!/usr/bin/env python

"""
Welcome to mkvstrip.py.  This script can go through a folder looking for extraneous
audio and subtitle tracks and removes them.  Additionally you can choose to
overwrite the title field of the mkv.

Version = 1.0 (4/9/2014)
The latest version can always be found at https://github.com/cyberjock/mkvstrip

This python script has the following requirements:
1.  Mkvtoolnix installed: 7.0.0 and 7.1.0 were tested (should work with recent prior versions like 6.x and 5.x though)
2.  Python installed: 2.7.8_2 in FreeBSD/FreeNAS jail and 2.7.8 in Windows (should work with the entire 2.7.x series though)

Note that this script will remux the entire directory provided from the command line.
If you point this to a large amount of files this could potentially keep the storage location
near saturation speed until it completes.  In tests this could render the storage media for your movies or
tv shows so busy that it becomes nearly unresponsive until completion of this script (I was able to remux at over 1GB/sec in tests).
As this process is not CPU intensive your limiting factor is likely to be the throughput speed of the
storage location of the video files being checked/remuxed.

Keep in mind that because of how remuxing works this won't affect the quality of the included video/audio streams.
Using this over a file share is ***STRONGLY*** discouraged as this could take considerable time (days/weeks?)
to complete due to the throughput bottleneck of network speeds.

Use this script at your own risk (or reward).  Unknown bugs could result in this script eating your files.
There are a few "seatbelts" to ensure that nothing too undesirable happens. For example, if only one audio track exists
and it doesn't match your provided languages an ERROR is logged and the video file is skipped. 
I tested this extensively and I've used this for my collection, but there is no guarantee that bugs don't exist for you.
ALWAYS TEST A SMALL SAMPLE OF COPIES OF YOUR FILES TO ENSURE THE EXPECTED RESULT IS OBTAINED BEFORE UNLEASHING THIS SCRIPT ON YOUR MOVIES OR TV SHOWS BLINDLY.

Some default variables are provided below but all can be overwritten by command line parameters.
If the default variables are commented out then you MUST pass the appropriate info from the command line.

A remux should only occur if a change needs to be made to the file.
If no change is required then the file isn't remuxed.

For help with the command line parameters use the -h parameter.
"""

# Required Imports
import os, re, sys, subprocess, collections, logging, logging.handlers, time
import xml.etree.ElementTree as ElementTree
from cStringIO import StringIO
from argparse import ArgumentParser

# Constants
log = debug = path = dry_run = preserve_timestamp = log_subtitle = keep_commentary = rename_tv = rename_movie = mkvmerge_bin = mkvinfo_bin = mkvpropedit_bin = None
totalWarnings = totalErrors = totalProcessed = totalRenaming = totalSkipped = 0
audio_language = subtitle_language = list()
currentDir = os.path.dirname(os.path.realpath(__file__))

##########################################

# Log errors to file. Log file will be in the same directory as mkvstrip.py
# Note that the location always uses the / versus the \ for location despite what the OS uses (*cough* Windows).
log = os.path.join(currentDir, "mkvstrip.log")

# Log dubug messages to console output
debug = False

# The below parameter lets mkvstrip go through the motions of what it would do but
# won't actually change any files. This allows you to review the logs and ensure that
# everything in the log is what you'd actually like to do before actually doing it
dry_run = False

# preserve_timestamp keeps the timestamps of the old file if set.
# This prevents you from having an entire library that has a date/time stamp of today
preserve_timestamp = True

# Log files that have no subtitles in the languages chosen
# This is to allow you to be informed of videos that are missing your required subtitles so you can take action as necessary
log_subtitle = True

# Attempts to remove commentary tracks if set to false
# Recommended to set to False as commentary tracks can take up a bit of space
keep_commentary = False

# Rewrite the title field of mkv files to include the immediate parent directory
# If set to true it will rename the title field of the MKV to be in the format of "(parent directory) - (name of video file without .mkv extension)"
# This setting is mutually exclusive of rename_movie
rename_tv = False

# Rewrite the title field of mkv files to include the video file name without the .mkv extension
# This setting is mutually exclusive of rename_tv
rename_movie = True

# List of audio languages to retain.  Default is English (eng) and undetermined (und)
# "und" (undetermined) is always recommended in case audio tracks aren't identified.
audio_language = ["eng", "und"]

# List of subtitle languages to retain. Default is English (eng) and undetermined (und)
# "und" (undetermined) is always recommended in case subtitle tracks aren't identified.
subtitle_language = ["eng", "und"]

# Location for MKVToolNix executable binarys
# Note that the location always uses the / versus the \ for location despite what the OS uses (*cough* Windows).
mkvpropedit_bin = "/usr/local/bin/mkvpropedit"
mkvmerge_bin = "/usr/local/bin/mkvmerge"
mkvinfo_bin = "/usr/local/bin/mkvinfo"

# Directory or file to process
# Note that the location always uses the / versus the \ for location despite what the OS uses (*cough* Windows).
#path = "/mnt/vault/media/movies"

##########################################

# Create Parser to parse the required arguments
parser = ArgumentParser(description="Strips unnecessary tracks from MKV files.")

# Add arguments for log setting
group = parser.add_mutually_exclusive_group(required=log==None)
group.add_argument("-l", "--log", default=log, const=log or os.path.join(currentDir, "mkvstrip.log"), nargs="?", action="store", help="Log to file in addition to STDOUT and STDERR.", dest="log")
group.add_argument("--no-log", action="store_false", dest="log")

# Add arguments for debug setting
group = parser.add_mutually_exclusive_group(required=debug==None)
group.add_argument("-g", "--debug", default=debug, action="store_true", help="Enable debug logging", dest="debug")
group.add_argument("--no-debug", action="store_false", dest="debug")

# Add arguments for scan folder/file
group = parser.add_mutually_exclusive_group(required=path==None)
group.add_argument("-d", "--dir", default=path, action="store", help="Location of folder to scan", dest="path")
group.add_argument("-f", "--file", action="store", help="Location of file to scan", dest="path")

# Add arguments to enable dry run
group = parser.add_mutually_exclusive_group(required=dry_run==None)
group.add_argument("-y", "--dry-run", default=dry_run, action="store_true", help="Enable mkvmerge dry run for testing", dest="dry_run")
group.add_argument("--no-dry-run", action="store_false", dest="dry_run")

# Add arguments to enable or disable preserving of timestamp
group = parser.add_mutually_exclusive_group(required=preserve_timestamp==None)
group.add_argument("-p", "--preserve-timestamp", default=preserve_timestamp, action="store_true", help="Preserve timestamp of mkv file", dest="preserve_timestamp")
group.add_argument("--no-preserve-timestamp", action="store_false", dest="preserve_timestamp")

# Add arguments to enable or disable no subtitle logging
group = parser.add_mutually_exclusive_group(required=log_subtitle==None)
group.add_argument("-m", "--log-subtitle", default=log_subtitle, action="store_true", help="Log if file doesn\'t have a subtitle track.", dest="log_subtitle")
group.add_argument("--no-log-subtitle", action="store_false", dest="log_subtitle")

# Add arguments to enable or disable retaining of commentary tracks
group = parser.add_mutually_exclusive_group(required=keep_commentary==None)
group.add_argument("-c", "--keep-commentary", default=keep_commentary, action="store_true", help="Keep commentary audio and subtitle tracks.", dest="keep_commentary")
group.add_argument("--no-commentary", action="store_false", dest="keep_commentary")

# Add arguments to enable renmae tv or rename movie
renaming = parser.add_argument_group("renaming")
group = renaming.add_mutually_exclusive_group(required=rename_tv==None and rename_movie==None)
group.add_argument("-r", "--rename-tv", default=rename_tv, action="store_true", help="Rename video track names to include immediate parent directory.", dest="rename_tv")
group.add_argument("-e", "--rename-movie", default=rename_movie, action="store_true", help="Use the filename to rename the video track names.", dest="rename_movie")
renaming.add_argument("--no-rename-tv", action="store_false", dest="rename_tv")
renaming.add_argument("--no-rename-movie", action="store_false", dest="rename_movie")

# Add arguments for lanauage
language = parser.add_argument_group("language")
language.add_argument("-a", "--audio-language", default=audio_language, action="append", required=audio_language==[], help="Audio languages to retain. May be specified multiple times.", dest="audio_language")
language.add_argument("-s", "--subtitle-language", default=subtitle_language, action="append", help="Subtitle languages to retain. May be specified multiple times.", dest="subtitle_language")

# Add arguments for binary locations
binarys = parser.add_argument_group("binarys")
binarys.add_argument("-b", "--mkvmerge-bin", default=mkvmerge_bin, action="store", help="Path to mkvmerge binary.", dest="mkvmerge_bin")
binarys.add_argument("-i", "--mkvinfo-bin", default=mkvinfo_bin, action="store", help="Path to mkvinfo binary.", dest="mkvinfo_bin")
binarys.add_argument("-t", "--mkvpropedit-bin", default=mkvpropedit_bin, action="store", help="Path to mkvpropedit binary.", dest="mkvpropedit_bin")

# Parse All Args
args = parser.parse_args()

# Convert path to normalized absolutized version
systemEncoding = sys.stdin.encoding
args.log = os.path.abspath(args.log).decode(systemEncoding)
args.path = os.path.abspath(args.path).decode(systemEncoding)
args.mkvinfo_bin = os.path.abspath(args.mkvinfo_bin).decode(systemEncoding)
args.mkvmerge_bin = os.path.abspath(args.mkvmerge_bin).decode(systemEncoding)
args.mkvpropedit_bin = os.path.abspath(args.mkvpropedit_bin).decode(systemEncoding)

##########################################

# Make sure that both args.rename_tv and args.rename_movie are not true
if args.rename_tv is True and args.rename_movie is True:
	raise RuntimeError("Setting rename_tv = True and rename_movie = True at the same time is not allowed.")

# Create class to filter logger to Debug and Info logging
class InfoFilter(logging.Filter):
	def filter(self, rec):
		logLevel = rec.levelno
		if logLevel == logging.ERROR: totalErrors += 1
		elif logLevel == logging.WARNING: totalWarnings += 1
		return logLevel in (logging.DEBUG, logging.INFO)

# Create logger with name "spam_application"
logger = logging.getLogger("mkvstrip")
logger.setLevel(logging.DEBUG)

# Create formatter Object
formatter = logging.Formatter("[ %(asctime)s ] %(levelname)-7s --- %(message)s", "%Y-%m-%d %I:%M:%S %p")
cformatter = logging.Formatter("%(levelname)-7s --- %(message)s")

# Create console handler with a log level of debug and info
consoleHandler1Stdout = logging.StreamHandler(sys.stdout)
consoleHandler1Stdout.setLevel(logging.DEBUG if args.debug else logging.INFO)
consoleHandler1Stdout.setLevel(logging.INFO)
consoleHandler1Stdout.setFormatter(cformatter)
consoleHandler1Stdout.addFilter(InfoFilter())
logger.addHandler(consoleHandler1Stdout)

# Create console handler with a log level of warning and above
consoleHandlerStderr = logging.StreamHandler(sys.stderr)
consoleHandlerStderr.setLevel(logging.WARNING)
consoleHandlerStderr.setFormatter(cformatter)
logger.addHandler(consoleHandlerStderr)

# Create file handler which logs even debug messages
if args.log:
	fileHandler = logging.handlers.TimedRotatingFileHandler(args.log.encode("utf-8"), when="h", interval=12, backupCount=4)
	fileHandler.setLevel(logging.DEBUG)
	fileHandler.setFormatter(formatter)
	logger.addHandler(fileHandler)
	logger.debug("Log file opened at %s", args.log)

# Loop each argument and log to file
logger.info("=========")
logger.info("Running %s with configuration:", os.path.basename(__file__))
logger.info("=========")
for key, value in vars(args).iteritems():
	if isinstance(value, unicode): logger.info("%s = %s", key.upper(), value.encode("utf-8"))
	else: logger.info("%s = %s", key.upper(), value)

##########################################

# Create Classes to store the Required data, VideoTracks, unWantedAudio and SubtitleTrack.
class Track(object):
	def __init__(self):
		self._id = None
		self._name = None
		self._codec = None
		self._language = u"und"
	
	def __str__(self):
		return "Track #%s (%s): %s - %s" % (self._id.encode("utf-8"), self._language.encode("utf-8"), self._codec.encode("utf-8"), self._name.encode("utf-8") if self._name else "")
	
	def __makeUnicode(self, data):
		if data is None or isinstance(data, unicode): return data
		else: return data.decode("utf-8")
	
	@property
	def id(self): return self._id
	
	@id.setter
	def id(self, value): self._id = self.__makeUnicode(value)
	
	@property
	def name(self): return self._name
	
	@name.setter
	def name(self, value): self._name = self.__makeUnicode(value)
	
	@property
	def codec(self): return self._codec
	
	@codec.setter
	def codec(self, value): self._codec = self.__makeUnicode(value)
	
	@property
	def language(self): return self._language
	
	@language.setter
	def language(self, value): self._language = self.__makeUnicode(value)

# Remove unwanted characters from tag strings
def cleanXMLTags(tag):
	# Clean up Tags
	tag = tag.title()
	for char, replacement in ((" ","-"),("(","B"),(")","B"),(",",""),("@",""),(":","")):
		tag = tag.replace(char,replacement)
	return tag

# Method to convert mkvinfo output to XML
def mkvToXML(input):
	# Global Vars
	lastIndent = 0
	rootElement = ElementTree.Element("mkvinfo")
	elementTracker = [rootElement]
	
	# Loop each line of the output and parse data to xml
	for line in StringIO(input):
		# Split Sections and Calculate Indentation Level
		indent, line = line.split("+ ", 1)
		indent = len(indent)
		
		# Fetch Tag and Value Elements of Data Section
		colonPos = line.find(":")
		bracketPos = line.find("(")
		if (colonPos < 1) or (bracketPos > 0 and colonPos > bracketPos):
			tag = line.strip()
			value = None
		else:
			tag, value = line.split(": ",1)
			value = value.strip()
			tag = tag.strip()
		
		try:
			attrs = {}
			# Search for attributes within brackets
			if "(" in tag and ")" in tag:
				startB = tag.find("(")
				endB = tag.find(")")
				extra = tag[startB+1:endB]
				tag = tag[:startB].strip()
				key2, value2 = extra.split(": ", 1)
				attrs[cleanXMLTags(key2)] = value2
			
			# Search for attributes separated by ","
			if "," in tag:
				temp, attr = tag.split(", ")
				key2, value2 = attr.split(" ")
				attrs[cleanXMLTags(key2)] = value2
				tag = temp
		
		except:
			# Failed to Parse extra attributes
			pass
		
		finally:
			# Clean up Tags
			tag = cleanXMLTags(tag)
		
		# Check if finished with last set of elements
		if lastIndent > indent: elementTracker = elementTracker[:indent+1]
		
		# Fetch Required element to append child element to
		element = elementTracker[indent]
		if len(elementTracker) != indent+1: elementTracker.pop()
		
		# Create Child Element and append to Tracking List
		subElement = ElementTree.SubElement(element, tag, attrs)
		elementTracker.append(subElement)
		
		# Add Value to Chile if valid
		if value: subElement.text = value
		
		# Log the Current Indent level for next run
		lastIndent = indent
	
	# Return output as XML ElementTree Object
	return rootElement

# Method to fetch a dict of "video", "audio", "subtitle" Tracks
def checkTracks(element):
	trackData = collections.defaultdict(list)
	for Atrack in element.find("Segment").find("Segment-Tracks").findall("A-Track"):
		# Fetch language and Codec Name
		trackInfo = Track()
		
		# Fetch Trank Language
		try:
			language = Atrack.find("Language").text
			if language: trackInfo.language = language.lower()
			else: trackInfo.language = "und"
		except: logger.debug("No Language was found for track %s", Atrack)
		
		# Fetch Track Name
		try: trackInfo.name = Atrack.find("Name").text.split("_",1)[-1]
		except: logger.debug("No name was found for track %s", Atrack)
		
		# Fetch Track Codec
		try: trackInfo.codec = Atrack.find("Codec-Id").text.split("_",1)[-1]
		except: logger.debug("No Codec-Id was found for track %s", Atrack)
		
		# Fetch Track ID Number
		try: trackInfo.id = Atrack.find("Track-Number").text.replace(")","").split(" ")[-1].strip()
		except: logger.debug("No Track-Number was found for track %s", Atrack)
		
		# Save track info to dict
		trackData[str(Atrack.find("Track-Type").text)].append(trackInfo)
	
	# Return dict of available tracks
	return trackData

def checkTitle(element):
	try: title = element.find("Segment").find("Segment-Information").find("Title").text
	except: return None
	else:
		if title is None or isinstance(title, unicode): return title
		else: return title.decode("utf-8")

##########################################
totalSaved = list()

# Creates a sorted list of file to be processed
if os.path.isfile(args.path) is True:
	processList = [args.path]
	totalMKVs = 1
else:
	# Walk through the directory and sort by filename
	unsortedList = list()
	for dirpath, dirnames, filenames in os.walk(args.path):
		mkvFilenames = [filename for filename in filenames if filename.lower().endswith(u".mkv")]
		mkvFilenames.sort()
		unsortedList.append((dirpath, mkvFilenames))
	
	# Now sort by Directory and append to processList
	processList = list()
	unsortedList.sort(key=lambda dirTuple: dirTuple[0])
	for dirpath, filenames in unsortedList:
		for filename in filenames:
			processList.append(os.path.abspath(os.path.join(dirpath, filename)))
	
	# Check for the ammount of files to process
	totalMKVs = len(processList)

# Loop each file and remux if needed
for count, path in enumerate(processList, start=1):
	# Attempt to identify file
	logger.info("=========")
	logger.info("Identifying video (%s/%s) %s", count, totalMKVs, path.encode("utf-8"))
	
	# Call mkvinfo and convert output to xml
	try: rootElement = mkvToXML(subprocess.check_output([args.mkvinfo_bin.encode("utf-8"), "--output-charset", "utf-8", path.encode("utf-8")]))
	except subprocess.CalledProcessError:
		logger.error("Failed to identify %s", path.encode("utf-8"))
		continue
	
	# Fetch parent, title of mkv file If renaming of file is requeste 
	if args.rename_tv is True or args.rename_movie is True:
		# Split out the separated part of the path
		tail = os.path.splitdrive(path)[1]
		parent = os.path.split(os.path.dirname(tail))[-1]
		name = os.path.splitext(os.path.basename(tail))[0].strip()
		title = checkTitle(rootElement)
		
		# Change title name to add the parent directory for tv renaming
		if args.rename_tv is True: name = u"%s: %s" % (parent, name)
		
		# Rewrite the title field of mkv file to include the modifyed title if needed
		if title != name:
			modifyCMD = [args.mkvpropedit_bin.encode("utf-8"), path.encode("utf-8"), "--command-line-charset", "utf-8", "--set", "title=%s" % name.encode("utf-8")]
			logger.info("Renaming title of mkv to %s" % name.encode("utf-8"))
			if args.dry_run is True: logger.info("Changes are not being applied because you are in dry run mode")
			else:
				try: subprocess.check_output(modifyCMD)
				except subprocess.CalledProcessError as e:
					logger.error("Failed to modify %s", path.encode("utf-8"))
					logger.error(e.cmd)
					logger.error(e.output)
				else: totalRenaming += 1
	
	# Find video, audio, and subtitle tracks
	trackData = checkTracks(rootElement)
	remuxRequired = False
	
	# Display all found tracks
	for key, tracks in trackData.items():
		logger.info("Found %s track(s): %s", key, len(tracks))
		for track in tracks:
			logger.info("    %s", track)
	
	# Check if any audio tracks are available, if not found then Skip
	if "audio" in trackData:
		# Filter out tracks that don't match languages specified
		logger.info("Filtering audio track(s)...")
		unWantedAudio = list()
		wantedAudio = list()
		
		# To be absolutely sure check if the track ID is valid
		for track in trackData["audio"]:
			if track.id is None or not track.id.isdigit():
				# Reset audio Tracks and break out of loop
				wantedAudio = None
				break
			
			elif track.language.encode("ascii") in args.audio_language and (args.keep_commentary is True or not u"commentary" in unicode(track.name).lower()):
				# Append track to audio tracks list
				wantedAudio.append(track)
		
		# Skip files that have invalid track info
		if wantedAudio is None:
			logger.error("Invalid track info found for %s... Skipping.", path.encode("utf-8"))
			continue
		
		# Skip files that don't have the specified language audio tracks
		elif len(wantedAudio) == 0:
			logger.error("No audio tracks matching specified language(s) for %s... Skipping.", path.encode("utf-8"))
			continue
		
		# Audio Tracks found, Log each track
		else:
			# Retaining Log
			logger.info("Retaining audio language(s): %s", len(wantedAudio))
			for track in wantedAudio:
				logger.info("    %s", track)
			
			# Removing Log
			unWantedAudio = [track for track in trackData["audio"] if not track in wantedAudio]
			if len(unWantedAudio) == 0: logger.info("Removing audio languages(s): None")
			else:
				remuxRequired = True
				logger.info("Removing audio languages(s): %s", len(unWantedAudio))
				for track in unWantedAudio:
					logger.info("    %s", track)
	
	else:
		# No audio track(s) found, Skipping
		logger.error("No audio track(s) found for %s... Skipping.", path.encode("utf-8"))
		continue
	
	# Check if any subtitle tracks are available, if not found then log warning
	if "subtitles" in trackData:
		# Filter out tracks that don't match languages specified
		logger.info("Filtering subtitle track(s)...")
		unWantedSubtitle = list()
		wantedSubtitle = list()
		
		# To be absolutely sure check if the track ID is valid
		for track in trackData["subtitles"]:
			if track.id is None or not track.id.isdigit():
				# Reset subtitle Tracks and break out of loop
				wantedSubtitle = None
				break
			
			elif track.language.encode("ascii") in args.subtitle_language and (args.keep_commentary is True or not u"commentary" in unicode(track.name).lower()):
				# Append track to subtitle tracks list
				wantedSubtitle.append(track)
		
		# Skip files that have invalid track info
		if wantedSubtitle is None:
			if args.log_subtitle: logger.warning("Invalid track info found for %s", path.encode("utf-8"))
		
		# Skip files that don't have the specified language subtitle tracks
		elif len(wantedSubtitle) == 0:
			if args.log_subtitle: logger.warning("No subtitle tracks matching specified language(s) for %s", path.encode("utf-8"))
		
		# Subtitle Tracks found, Log each track
		else:
			# Retaining Log
			logger.info("Retaining subtitle language(s): %s", len(wantedSubtitle))
			for track in wantedSubtitle:
				logger.info("    %s", track)
			
			# Removing Log
			unWantedSubtitle = [track for track in trackData["subtitles"] if not track in wantedSubtitle]
			if len(unWantedSubtitle) == 0: logger.info("Removing subtitle languages(s): None")
			else:
				remuxRequired = True
				logger.info("Removing subtitle languages(s): %s", len(unWantedSubtitle))
				for track in unWantedSubtitle:
					logger.info("    %s", track)
	
	elif args.log_subtitle:
		# No subtitle track(s) found, Skipping
		logger.warning("No subtitle track(s) found for %s.", path.encode("utf-8"))
		unWantedSubtitle = list()
		wantedSubtitle = list()
	
	# Skip files that don't need processing
	if remuxRequired is False:
		logger.info("No changes required for %s", path.encode("utf-8"))
		totalSkipped += 1
		continue
	
	# Create build command
	buildCMD = [args.mkvmerge_bin.encode("utf-8"), "--output"]
	target = u"%s.tmp" % path
	buildCMD.append(target.encode("utf-8"))
	
	# Add audio tracks to build command
	if len(unWantedAudio) > 0:
		buildCMD.extend(["--audio-tracks", "!"+",".join((track.id.encode("ascii") for track in unWantedAudio))])
		for count, track in enumerate(wantedAudio): buildCMD.extend(["--default-track", ":".join((track.id.encode("ascii"), "0" if count else "1"))])
		
	# Add subtitles tracks to build command
	if len(unWantedSubtitle) > 0:
		buildCMD.extend(["--subtitle-tracks", "!"+",".join((track.id.encode("ascii") for track in unWantedSubtitle))])
		for count, track in enumerate(wantedSubtitle): buildCMD.extend(["--default-track", ":".join((track.id.encode("ascii"), "0"))])
	
	# Add source file to build command
	buildCMD.append(path.encode("utf-8"))
	
	# Attempt to process file
	logger.info("Processing %s...", path.encode("utf-8"))
	if args.dry_run is True: logger.info("Changes are not being applied because you are in dry run mode")
	else:
		try:
			# Call subprocess command to remux file
			process = subprocess.Popen(buildCMD, stdout=subprocess.PIPE, universal_newlines=True)
			
			# Display Percentage complete until subprocess has finished
			retcode = process.poll()
			while retcode is None:
				# Sleep for half a second and then dislay progress
				time.sleep(.5)
				for line in iter(process.stdout.readline, ""):
					if "progress" in line.lower():
						sys.stdout.write("\r%s%s" % (" "*12, line.strip()))
						sys.stdout.flush()
				
				# Check return code of subprocess
				retcode = process.poll()
			
			# Check if return code indicates an error
			sys.stdout.write("\n")
			if retcode: raise subprocess.CalledProcessError(retcode, buildCMD, output=process.communicate()[0])
			else: logger.info("Remux of %s successful", path.encode("utf-8"))
			totalProcessed += 1
		
		except subprocess.CalledProcessError as e:
			logger.error("Remux of %s failed!", path.encode("utf-8"))
			logger.error(e.cmd)
			logger.error(e.output)
			continue
	
	# Preserve timestamp
	if args.preserve_timestamp is True:
		logger.info("Preserving timestamp of %s", path.encode("utf-8"))
		if args.dry_run is True: logger.info("Changes are not being applied because you are in dry run mode")
		else:
			stat = os.stat(path.encode("utf-8"))
			os.utime(target, (stat.st_atime, stat.st_mtime))
	
	# Check how much space was saved 
	if args.dry_run is False:
		orgSize = float(os.path.getsize(path))
		newSize = float(os.path.getsize(target))
		saved = orgSize - newSize
		logger.info("Saved %.2fMB of disk space", saved / 1024 / 1024)
		totalSaved.append(saved)
	
	# Overwrite original file
	if args.dry_run is False:
		try: os.unlink(path)
		except:
			os.unlink(target)
			logger.error("Renaming of %s to %s failed!", target, path)
		else:
			# Rename temp file to original path
			os.rename(target, path)

logger.info("=========")
logger.info("Finished processing.")
if len(totalSaved) > 0: logger.info("Total disk space saved: %.2fMB", sum(totalSaved) / 1024 / 1024)
if totalProcessed: logger.info("Total amount of files processed: %s", totalProcessed)
if totalRenaming: logger.info("Total amount of files needing renaming: %s", totalRenaming)
if totalSkipped: logger.info("Total amount of files skipped: %s", totalSkipped)
if totalWarnings: logger.info("Total amount of warnings: %s", totalWarnings)
if totalErrors: logger.info("Total amount of errors found: %s", totalErrors)