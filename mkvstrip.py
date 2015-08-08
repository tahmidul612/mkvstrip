#!/usr/bin/env python

"""
Welcome to mkvstrip.py.  This script can go through a folder looking for extraneous
audio and subtitle tracks and removes them.  Additionally you can choose to
overwrite the title field of the mkv.

Version = 0.9.5 (27/2/2015)
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
import os, re, sys, subprocess, ConfigParser, collections, logging, logging.handlers, time, locale, platform
import xml.etree.ElementTree as ElementTree
from cStringIO import StringIO
from argparse import ArgumentParser

# Constants
totalWarnings = totalErrors = totalProcessed = totalRenaming = totalSkipped = 0
audio_language = subtitle_language = list()
currentDir = os.path.dirname(os.path.realpath(__file__))

# Fetch System Encoding
systemEncoding = locale.getpreferredencoding()
if "ascii" in systemEncoding.lower(): systemEncoding = "UTF-8"

##########################################

# Custom ConfigParser
class CustomParser(ConfigParser.ConfigParser):
	def safeget(self, section, option, default=None):
		try: return ConfigParser.ConfigParser.get(self, section, option)
		except: return default
	
	def safegetboolean(self, section, option, default=False):
		try: return ConfigParser.ConfigParser.getboolean(self, section, option)
		except: return default
	
	def safegetlist(self, section, option, default=[]):
		try: return [item.strip() for item in ConfigParser.ConfigParser.get(self, section, option).split(",")]
		except: return default
	
	def removeUnset(self):
		# Remove unset options
		for section in self.sections():
			for option, value in self.items(section):
				if value == "": self.remove_option(section, option)

# Fetch config defaults
config = CustomParser()
config.read(os.path.join(currentDir, "defaults.ini"))
osDefaults = os.path.join(currentDir, "defaults-%s.ini" % platform.system().lower())
if os.path.exists(osDefaults): config.read(osDefaults)
config.removeUnset()

# Create Parser to parse the required arguments
parser = ArgumentParser(description="Strips unnecessary tracks from MKV files.")

# Add arguments for log setting
group = parser.add_mutually_exclusive_group(required=not config.has_option("global", "log"))
group.add_argument("-l", "--log", default=config.safeget("global", "log"), const=config.safeget("global", "log", os.path.join(currentDir, "mkvstrip.log")), nargs="?", action="store", help="Log to file in addition to STDOUT and STDERR.", dest="log")
group.add_argument("--no-log", action="store_false", dest="log")

# Add arguments for debug setting
group = parser.add_mutually_exclusive_group(required=not config.has_option("global", "debug"))
group.add_argument("-g", "--debug", default=config.safegetboolean("global", "debug", False), action="store_true", help="Enable debug logging", dest="debug")
group.add_argument("--no-debug", action="store_false", dest="debug")

# Add arguments to enable dry run
group = parser.add_mutually_exclusive_group(required=not config.has_option("global", "dry_run"))
group.add_argument("-y", "--dry-run", default=config.safegetboolean("global", "dry_run", False), action="store_true", help="Enable mkvmerge dry run for testing", dest="dry_run")
group.add_argument("--no-dry-run", action="store_false", dest="dry_run")

# Add arguments to enable or disable preserving of timestamp
group = parser.add_mutually_exclusive_group(required=not config.has_option("global", "preserve_timestamp"))
group.add_argument("-p", "--preserve-timestamp", default=config.safegetboolean("global", "preserve_timestamp", True), action="store_true", help="Preserve timestamp of mkv file", dest="preserve_timestamp")
group.add_argument("--no-preserve-timestamp", action="store_false", dest="preserve_timestamp")

# Add arguments to enable or disable no subtitle logging
group = parser.add_mutually_exclusive_group(required=not config.has_option("global", "log_subtitle"))
group.add_argument("-m", "--log-subtitle", default=config.safegetboolean("global", "log_subtitle", False), action="store_true", help="Log if file doesn\'t have a subtitle track.", dest="log_subtitle")
group.add_argument("--no-log-subtitle", action="store_false", dest="log_subtitle")

# Add arguments to enable or disable retaining of commentary tracks
group = parser.add_mutually_exclusive_group(required=not config.has_option("global", "remove_commentary"))
group.add_argument("-c", "--remove-commentary", default=config.safegetboolean("global", "remove_commentary", True), action="store_true", help="Keep commentary audio and subtitle tracks.", dest="remove_commentary")
group.add_argument("--keep-commentary", action="store_false", dest="remove_commentary")

# Add arguments for lanauage
language = parser.add_argument_group("language")
language.add_argument("-a", "--audio-language", default=config.safegetlist("global", "audio_language", ["eng", "und"]), action="append", required=not config.has_option("global", "audio_language"), help="Audio languages to retain. May be specified multiple times.", dest="audio_language")
language.add_argument("-s", "--subtitle-language", default=config.safegetlist("global", "subtitle_language", ["eng", "und"]), action="append", help="Subtitle languages to retain. May be specified multiple times.", dest="subtitle_language")

# Add arguments for binary locations
binarys = parser.add_argument_group("binarys")
binarys.add_argument("-b", "--mkvmerge-bin", default=config.safeget("global", "mkvmerge"), action="store", required=not config.has_option("global", "mkvmerge"), help="Path to mkvmerge binary.", dest="mkvmerge_bin")
binarys.add_argument("-i", "--mkvinfo-bin", default=config.safeget("global", "mkvinfo"), action="store", required=not config.has_option("global", "mkvinfo"), help="Path to mkvinfo binary.", dest="mkvinfo_bin")
binarys.add_argument("-t", "--mkvpropedit-bin", default=config.safeget("global", "mkvpropedit"), action="store", required=not config.has_option("global", "mkvpropedit"), help="Path to mkvpropedit binary.", dest="mkvpropedit_bin")

# Fetch Directorys or files to scan
pathList = []
for section in (item for item in config.sections() if not item == "global"):
	if not config.has_option(section, "path"): continue
	else:
		# Fetch Rename Value if set
		if config.has_option(section, "rename_movie") and config.safegetboolean(section, "rename_movie") is True: pathList.append((config.safeget(section, "path").decode(systemEncoding), u"movie"))
		elif config.has_option(section, "rename_tv") and config.safegetboolean(section, "rename_tv") is True: pathList.append((config.safeget(section, "path").decode(systemEncoding), u"tv"))
		else: pathList.append((config.safeget(section, "path").decode(systemEncoding), False))

# Add arguments for scan folder/file
group = parser.add_mutually_exclusive_group(required=pathList==[])
group.add_argument("-d", "--dir", default=None, action="store", help="Location of folder to scan", dest="path")
group.add_argument("-f", "--file", default=None, action="store", help="Location of file to scan", dest="path")

# Add arguments to enable rename tv or rename movie
renaming = parser.add_argument_group("renaming")
group = renaming.add_mutually_exclusive_group(required=pathList==[])
group.add_argument("-r", "--rename-tv", default=None, action="store_true", help="Rename video track names to include immediate parent directory.", dest="rename_tv")
group.add_argument("-e", "--rename-movie", default=None, action="store_true", help="Use the filename to rename the video track names.", dest="rename_movie")
renaming.add_argument("--no-rename-tv", action="store_false", dest="rename_tv")
renaming.add_argument("--no-rename-movie", action="store_false", dest="rename_movie")

# Parse All Args
args = parser.parse_args()

# Make sure that both args.rename_tv and args.rename_movie are not true
if args.path is not None:
	if args.rename_tv is True and args.rename_movie is True:
		raise RuntimeError("Setting rename_tv = True and rename_movie = True at the same time is not allowed.")
	elif args.rename_movie is True:
		pathList = [(args.path.decode(systemEncoding), u"movie")]
	elif args.rename_tv is True:
		pathList = [(args.path.decode(systemEncoding), u"tv")]
	else:
		pathList = [(args.path.decode(systemEncoding), False)]

# Convert path to normalized absolutized version
args.log = args.log.decode(systemEncoding)
args.mkvinfo_bin = args.mkvinfo_bin.decode(systemEncoding)
args.mkvmerge_bin = args.mkvmerge_bin.decode(systemEncoding)
args.mkvpropedit_bin = args.mkvpropedit_bin.decode(systemEncoding)

##########################################

# Create class to filter logger to Debug and Info logging
class InfoFilter(logging.Filter):
	def filter(self, rec):
		logLevel = rec.levelno
		if logLevel == logging.ERROR:
			global totalErrors
			totalErrors += 1
		elif logLevel == logging.WARNING:
			global totalWarnings
			totalWarnings += 1
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
	if os.path.exists(args.log.encode(systemEncoding)):
		fileHandler = logging.handlers.TimedRotatingFileHandler(args.log.encode(systemEncoding), when="h", interval=1, backupCount=4)
		fileHandler.doRollover()
	else: fileHandler = logging.handlers.TimedRotatingFileHandler(args.log.encode(systemEncoding), when="h", interval=1, backupCount=4)
	fileHandler.setLevel(logging.DEBUG)
	fileHandler.setFormatter(formatter)
	logger.addHandler(fileHandler)
	logger.debug("Log file opened at %s", args.log.encode(systemEncoding))

# Loop each argument and log to file
logger.info("=========")
logger.info("Running %s with configuration:", os.path.basename(__file__))
logger.info("=========")
logger.info("SYSTEM_ENCODING = %s" % systemEncoding)
for key, value in vars(args).iteritems():
	if key == "path": continue
	if isinstance(value, unicode): logger.info("%s = %s", key.upper(), value.encode(systemEncoding))
	else: logger.info("%s = %s", key.upper(), value)

for path, rename in pathList:
	logger.info("Path = %s", path)
	logger.info("Rename = %s", rename)

##########################################

# Create Classes to store the Required data, VideoTracks, unWantedAudio and SubtitleTrack.
class Track(object):
	def __init__(self):
		self._id = None
		self._name = None
		self._codec = None
		self._language = u"und"
	
	def __str__(self):
		return (u"Track #%s (%s): %s - %s" % (self._id, self._language, self._codec, self._name if self._name else "")).encode("UTF-8")
	
	def __makeUnicode(self, data):
		if data is None or isinstance(data, unicode): return data
		else: return data.decode("UTF-8")
	
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
		else: return title.decode("UTF-8")

##########################################
logger.info("=========")
logger.info("Searching for MKV files to process...")
totalSaved = list()
processList = list()

# Creates a sorted list of file to be processed
for path, rename in pathList:
	if os.path.isfile(path.encode(systemEncoding)): processList.append((path, rename))
	else:
		# Walk through the directory and sort by filename
		unsortedList = list()
		for dirpath, dirnames, filenames in os.walk(path.encode(systemEncoding)):
			if isinstance(dirpath, str): dirpath = dirpath.decode(systemEncoding)
			mkvFilenames = []
			for filename in filenames:
				if isinstance(filename, str): filename = filename.decode(systemEncoding)
				if filename.lower().endswith(u".mkv"): mkvFilenames.append(filename)
			
			mkvFilenames.sort()
			unsortedList.append((dirpath, mkvFilenames))
		
		# Now sort by Directory and append to processList
		unsortedList.sort(key=lambda dirTuple: dirTuple[0])
		for dirpath, filenames in unsortedList:
			for filename in filenames:
				processList.append((os.path.join(dirpath, filename), rename))
	
# Check for the ammount of files to process
totalMKVs = len(processList)

# Loop each file and remux if needed
for count, pathData in enumerate(processList, start=1):
	# Split pathData into path and rename
	path, rename = pathData
	
	# Attempt to identify file
	logger.info("=========")
	logger.info("Identifying video (%s/%s) %s", count, totalMKVs, path.encode(systemEncoding))
	command = [args.mkvinfo_bin.encode(systemEncoding), "--command-line-charset", systemEncoding, "--output-charset", "UTF-8", path.encode(systemEncoding)]
	try: rootElement = mkvToXML(subprocess.check_output(command))
	except subprocess.CalledProcessError as e:
		logger.error("Failed to identify %s", path.encode(systemEncoding))
		logger.debug(e.cmd)
		logger.debug(e.output)
		continue
	except:
		logger.error("Failed to identify %s", path.encode(systemEncoding))
		continue
	
	# Fetch parent, title of mkv file If renaming of file is requeste 
	if rename:
		# Split out the separated part of the path
		tail = os.path.splitdrive(path)[1]
		parent = os.path.split(os.path.dirname(tail))[-1]
		name = os.path.splitext(os.path.basename(tail))[0].strip()
		title = checkTitle(rootElement)
		
		# Change title name to add the parent directory for tv renaming
		if rename == u"tv": name = u"%s: %s" % (parent, name)
		
		# Rewrite the title field of mkv file to include the modifyed title if needed
		if title != name:
			modifyCMD = [args.mkvpropedit_bin.encode(systemEncoding), path.encode(systemEncoding), "--command-line-charset", systemEncoding, "--set", "title=%s" % name.encode(systemEncoding)]
			logger.info("Renaming title of mkv to %s" % name.encode(systemEncoding))
			if args.dry_run is True: logger.info("Renaming are not being applied because you are in dry run mode")
			else:
				try: subprocess.check_output(modifyCMD)
				except subprocess.CalledProcessError as e:
					logger.error("Failed to modify %s", path.encode(systemEncoding))
					logger.debug(e.cmd)
					logger.debug(e.output)
				except:
					logger.error("Failed to modify %s", path.encode(systemEncoding))
				else:
					totalRenaming += 1
	
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
			
			elif track.language.encode("ascii") in args.audio_language and (args.remove_commentary is False or not u"commentary" in unicode(track.name).lower()):
				# Append track to audio tracks list
				wantedAudio.append(track)
		
		# Skip files that have invalid track info
		if wantedAudio is None:
			logger.error("Invalid track info found for %s... Skipping.", path.encode(systemEncoding))
			continue
		
		# Skip files that don't have the specified language audio tracks
		elif len(wantedAudio) == 0:
			logger.error("No audio tracks matching specified language(s) for %s... Skipping.", path.encode(systemEncoding))
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
		logger.error("No audio track(s) found for %s... Skipping.", path.encode(systemEncoding))
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
			
			elif track.language.encode("ascii") in args.subtitle_language and (args.remove_commentary is False or not u"commentary" in unicode(track.name).lower()):
				# Append track to subtitle tracks list
				wantedSubtitle.append(track)
		
		# Skip files that have invalid track info
		if wantedSubtitle is None:
			if args.log_subtitle: logger.warning("Invalid track info found for %s", path.encode(systemEncoding))
		
		# Skip files that don't have the specified language subtitle tracks
		elif len(wantedSubtitle) == 0:
			if args.log_subtitle: logger.warning("No subtitle tracks matching specified language(s) for %s", path.encode(systemEncoding))
		
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
		logger.warning("No subtitle track(s) found for %s.", path.encode(systemEncoding))
		unWantedSubtitle = list()
		wantedSubtitle = list()
	
	# Skip files that don't need processing
	if remuxRequired is False:
		logger.info("No changes required for %s", path.encode(systemEncoding))
		totalSkipped += 1
		continue
	
	# Create build command
	buildCMD = [args.mkvmerge_bin.encode(systemEncoding), "--command-line-charset", systemEncoding, "--output"]
	target = u"%s.tmp" % path
	buildCMD.append(target.encode(systemEncoding))
	
	# Add audio tracks to build command
	if len(unWantedAudio) > 0:
		buildCMD.extend(["--audio-tracks", "!"+",".join((track.id.encode("ascii") for track in unWantedAudio))])
		for count, track in enumerate(wantedAudio): buildCMD.extend(["--default-track", ":".join((track.id.encode("ascii"), "0" if count else "1"))])
		
	# Add subtitles tracks to build command
	if len(unWantedSubtitle) > 0:
		buildCMD.extend(["--subtitle-tracks", "!"+",".join((track.id.encode("ascii") for track in unWantedSubtitle))])
		for count, track in enumerate(wantedSubtitle): buildCMD.extend(["--default-track", ":".join((track.id.encode("ascii"), "0"))])
	
	# Add source file to build command
	buildCMD.append(path.encode(systemEncoding))
	
	# Attempt to process file
	logger.info("Processing %s...", path.encode(systemEncoding))
	if args.dry_run is True: logger.info("Remux is not being applied because you are in dry run mode")
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
			else: logger.info("Remux of %s successful", path.encode(systemEncoding))
			totalProcessed += 1
		
		except subprocess.CalledProcessError as e:
			logger.error("Remux of %s failed!", path.encode(systemEncoding))
			logger.error(e.cmd)
			logger.error(e.output)
			continue
	
	# Preserve timestamp
	if args.preserve_timestamp is True:
		logger.info("Preserving timestamp of %s", path.encode(systemEncoding))
		if args.dry_run is True: logger.info("Preserving timestamp is not being applied because you are in dry run mode")
		else:
			stat = os.stat(path.encode(systemEncoding))
			os.utime(target.encode(systemEncoding), (stat.st_atime, stat.st_mtime))
	
	# Check how much space was saved 
	if args.dry_run is False:
		orgSize = float(os.path.getsize(path.encode(systemEncoding)))
		newSize = float(os.path.getsize(target.encode(systemEncoding)))
		saved = orgSize - newSize
		logger.info("Saved %.2fMB of disk space", saved / 1024 / 1024)
		totalSaved.append(saved)
	
	# Overwrite original file
	if args.dry_run is False:
		try: os.unlink(path)
		except:
			os.unlink(target)
			logger.error("Renaming of %s to %s failed!", target.encode(systemEncoding), path.encode(systemEncoding))
		else:
			# Rename temp file to original path
			os.rename(target.encode(systemEncoding), path.encode(systemEncoding))

logger.info("=========")
logger.info("Finished processing.")
if len(totalSaved) > 0: logger.info("Total disk space saved: %.2fMB", sum(totalSaved) / 1024 / 1024)
if totalProcessed: logger.info("Total amount of files processed: %s", totalProcessed)
if totalRenaming: logger.info("Total amount of files needing renaming: %s", totalRenaming)
if totalSkipped: logger.info("Total amount of files skipped: %s", totalSkipped)
if totalWarnings: logger.info("Total amount of warnings: %s", totalWarnings)
if totalErrors: logger.info("Total amount of errors found: %s", totalErrors)
