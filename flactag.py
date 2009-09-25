#!/usr/bin/env python
# encoding: utf-8
#
#	flagtag - tags all flac files interactively in the current directory
#
#	Copyright ©2009 Simon Arlott
#
#	This program is free software; you can redistribute it and/or
#	modify it under the terms of the GNU General Public License v2
#	as published by the Free Software Foundation.
#
#	This program is distributed in the hope that it will be useful,
#	but WITHOUT ANY WARRANTY; without even the implied warranty of
#	MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#	GNU General Public License for more details.
#
#	You should have received a copy of the GNU General Public License
#	along with this program; if not, write to the Free Software
#	Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA 02111-1307, USA.
#	Or, point your browser to http://www.gnu.org/copyleft/gpl.html

import os
import readline
import subprocess
import sys

EXIT_SUCCESS, EXIT_FAILURE, EXIT_USAGE = range(3)

class Retry(Exception):
	pass

class Prev(Exception):
	pass

class Next(Exception):
	pass

class GoBack(Exception):
	pass

# python's readline module has no "history -> list" function
def get_history():
	lines = []
	for i in range(1, readline.get_current_history_length() + 1):
		lines.append(readline.get_history_item(i))
	return lines

# python's readline module has no "list -> history" function
def set_history(lines):
	readline.clear_history()
	for line in lines:
		readline.add_history(line)

def last_history(line):
	if line == "":
		return False
	if (readline.get_current_history_length() == 0
			or readline.get_history_item(
				readline.get_current_history_length()) != line):
		readline.add_history(line)
		return True
	return False

def cut_history(line):
	if (readline.get_current_history_length() > 0
			and readline.get_history_item(
				readline.get_current_history_length()) == line):
		# not a mistake, getting is 1+, removing is 0+ ...
		readline.remove_history_item(readline.get_current_history_length() - 1)

if len(sys.argv) < 2 or (len(sys.argv) == 2 and sys.argv[1] == "--"):
	print "Usage: %s <tag> [tag...] [-- <file> [file...]]" % (sys.argv[0])
	print "       %s -- <file> [file...]" % (sys.argv[0])
	sys.exit(EXIT_USAGE)

args = sys.argv[1:]
try:
	split = args.index("--")
	files = args[split+1:]
	args = args[:split]
except ValueError:
	files = []
	for file in os.listdir(os.getcwd()):
		# filter out links and non-files
		#  (this must be done in advance  or the "go back to
		#    previous file" process will not work properly)
		if (not os.path.islink(file)
				and os.path.isfile(file)
				and file.endswith(".flac")):
			files.append(file)
	files.sort()

auto_tags = len(args) == 0
if not auto_tags:
	tags = []
	uniq = set()
	for tag in args:
		# metaflac allows an empty tag to be set... but can't show or remove it
		if tag != "" and tag not in uniq:
			uniq.add(tag)
			tags.append(tag)
	del uniq

last = {}
hist = {}
fastforward = False
i = 0
j = 0
while i < len(files):
	file = files[i]

	if auto_tags:
		# enumerate all tags in the file, excluding replaygain
		tags = []
		uniq = set()
		get_tags = subprocess.Popen(["metaflac", "--export-tags-to=-", "--", file], stdout=subprocess.PIPE)
		value = get_tags.communicate()[0]
		ret = get_tags.wait()
		if ret != 0:
			sys.exit("metaflac returned %d getting tags from %s" % (ret, file))

		for value in value.splitlines():
			tag = value.split("=", 2)[0]
			# metaflac allows an empty tag to be set... but can't show or remove it
			if tag != "" and not tag in uniq and not tag.startswith("REPLAYGAIN_"):
				uniq.add(tag)
				tags.append(tag)
		del uniq

	# skip files with no tags
	if len(tags) == 0:
		i += 1
		continue

	# if going back to previous file, use the last tag
	if j == -1:
		j = len(tags) - 1

	while j < len(tags):
		tag = tags[j]
		if tag in hist:
			set_history(hist[tag])
		else:
			set_history([])

		get_tags = subprocess.Popen(["metaflac", "--show-tag=%s" % (tag), "--", file], stdout=subprocess.PIPE)
		value = get_tags.communicate()[0]
		ret = get_tags.wait()
		if ret != 0:
			sys.exit("metaflac returned %d getting %s from %s" % (ret, tag, file))

		if value != "":
			# remove the tag name prefix, and only us the first value
			value = value.splitlines()[0].partition("%s=" % (tag))[2]

		if value == None or value == "":
			fastforward = False
			if tag in last:
				value = last[tag]

		try:
			# append this value if it's not there, so it can be edited
			added = last_history(value)

			# fast forward or prompt for input
			if fastforward:
				print "%s %s [%s]: " % (file, tag, value)
				data = value
			else:
				try:
					data = raw_input("%s %s [%s]: " % (file, tag, value))
				except KeyboardInterrupt:
					print
					print
					raise Retry
				except EOFError:
					print
					sys.exit(EXIT_SUCCESS)
	
				# remove the extra value if it got added but not used
				if added and data != "" and data != value:
					cut_history(value)
	
				if data == ".": # skip this item
					raise Next
				elif data == "<": # go back
					if j > 0:
						raise Prev
					elif i > 0:
						raise GoBack
					else:
						raise Retry
				elif data == "*": # fast forward to first unset file
					fastforward = True
					continue
				elif data == "#": # unset
					data = ""
				elif data == "": # reuse existing/last value
					data = value
		
			if data != value:
				ret = subprocess.Popen(["metaflac", "--remove-tag=%s" % (tag), "--", file]).wait()
				if ret != 0:
					sys.exit("metaflac returned %d removing %s from %s" % (ret, tag, file))

				if data != "":
					ret = subprocess.Popen(["metaflac", "--set-tag=%s=%s" % (tag, data), "--", file]).wait()
					if ret != 0:
						sys.exit("metaflac returned %d setting %s for %s" % (ret, tag, file))
	
			if data != "":
				last[tag] = data
			hist[tag] = get_history()

			raise Next
		except Retry:
			continue
		except Prev:
			j -= 1
		except Next:
			j += 1
		except GoBack:
			i -= 2
			j -= 1
			break

	# Can't do this at the start of the loop because
	# we may be going back to the previous file
	if j == len(tags):
		j = 0

	print
	i += 1

sys.exit(EXIT_SUCCESS)
