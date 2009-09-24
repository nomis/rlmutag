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

if len(sys.argv) < 2:
	print "Usage: %s <tag> [tag] [tag]" % (sys.argv[0])
	sys.exit(EXIT_USAGE)

def get_history():
	lines = []
	for i in range(1, readline.get_current_history_length() + 1):
		lines.append(readline.get_history_item(i))
	return lines

def set_history(lines):
	readline.clear_history()
	for line in lines:
		readline.add_history(line)

def last_history(line):
	if readline.get_current_history_length() == 0 \
			or readline.get_history_item(readline.get_current_history_length()) != line:
		readline.add_history(line)

tags = sys.argv[1:]
last = {}
hist = {}

files = []
for file in os.listdir(os.getcwd()):
	if not os.path.islink(file) and os.path.isfile(file):
		files.append(file)
files.sort()

i = 0
j = 0
while i < len(files):
	file = files[i]
	while j < len(tags):
		tag = tags[j]
		if tag in hist:
			set_history(hist[tag])
		else:
			set_history([])

		get_tags = subprocess.Popen(["metaflac", "--show-tag=%s" % (tag), file], stdout=subprocess.PIPE)
		value = get_tags.communicate()[0]
		ret = get_tags.wait()
		if ret != 0:
			sys.exit("metaflac returned %d getting %s from %s" % (ret, tag, file))

		if value:
			value = value.splitlines()[0].partition("%s=" % (tag))[2]
		elif tag in last:
			value = last[tag]
		last_history(value)

		try:
			data = raw_input("%s %s [%s]: " % (file, tag, value))
		except KeyboardInterrupt:
			print
			sys.exit(EXIT_SUCCESS)
		except EOFError:
			print
			sys.exit(EXIT_SUCCESS)

		if data == ".":
			j += 1
			continue
		elif data == "!":
			if j > 0:
				j -= 1
				continue
			elif i > 0:
				i -= 2
				j = len(tags) - 1
				break
			else:
				continue
		elif data == "":
			data = value
			last_history(data)
		
		if data != "":
			ret = subprocess.Popen(["metaflac", "--remove-tag=%s" % (tag), file]).wait()
			if ret != 0:
				sys.exit("metaflac returned %d removing %s from %s" % (ret, tag, file))
			ret = subprocess.Popen(["metaflac", "--set-tag=%s=%s" % (tag, data), file]).wait()
			if ret != 0:
				sys.exit("metaflac returned %d setting %s for %s" % (ret, tag, file))

			last[tag] = data
		hist[tag] = get_history()

		j += 1
		if j == len(tags):
			j = 0
			break
	print
	i += 1

sys.exit(EXIT_SUCCESS)
