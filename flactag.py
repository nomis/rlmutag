#!/usr/bin/env python3
# encoding: utf-8
#
#	flagtag - tags all flac files interactively in the current directory
#
#	Copyright ©2011,2020,2023 Simon Arlott
#
#	This program is free software: you can redistribute it and/or modify
#	it under the terms of the GNU General Public License as published by
#	the Free Software Foundation, either version 3 of the License, or
#	(at your option) any later version.
#
#	This program is distributed in the hope that it will be useful,
#	but WITHOUT ANY WARRANTY; without even the implied warranty of
#	MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#	GNU General Public License for more details.
#
#	You should have received a copy of the GNU General Public License
#	along with this program.  If not, see <http://www.gnu.org/licenses/>.

import os
import readline
import subprocess
import sys

EXIT_SUCCESS, EXIT_FAILURE, EXIT_USAGE = list(range(3))
PROMPT = "{file} {tag} [{value}]: "

class Prev(Exception): pass
class Next(Exception): pass
class FastForward(Exception): pass

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

def check(**args):
	if args["ret"] != 0:
		if "tag" in args:
			print("{name} returned {ret} for {file} when {action} tag {tag}".format(**args))
		else:
			print("{name} returned {ret} for {file} when {action}".format(**args))
		sys.exit(EXIT_FAILURE)

if len(sys.argv) < 2 or (len(sys.argv) == 2 and sys.argv[1] == "--"):
	print("Usage: {0} <tag> [tag...] [-- <file> [file...]]".format(sys.argv[0]))
	print("       {0} -- <file> [file...]".format(sys.argv[0]))
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
		#   this must be done in advance or the "go back to
		#   previous file" process will not work properly
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

		if tag.endswith(".flac"):
			print(f"Unexpected tag: {tag}")
			sys.exit(EXIT_USAGE)
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
		check(name="metaflac", ret=ret, action="listing tags", file=file)

		for tag in [value.split("=", 2)[0] for value in value.splitlines()]:
			# metaflac allows an empty tag to be set... but can't show or remove it
			if tag != "" and not tag in uniq and not tag.startswith("REPLAYGAIN_"):
				uniq.add(tag)
				tags.append(tag)
		del uniq

	try:
		# skip files with no tags
		if len(tags) == 0:
			raise Next

		# if going back to previous file, use the last tag
		if j == -1:
			j = len(tags) - 1

		while j < len(tags):
			tag = tags[j]
			if tag in hist:
				set_history(hist[tag])
			else:
				set_history([])

			get_tags = subprocess.Popen(["metaflac", "--show-tag={tag}".format(tag=tag), "--", file], stdout=subprocess.PIPE, encoding="utf-8")
			value = get_tags.communicate()[0]
			ret = get_tags.wait()
			check(name="metaflac", ret=ret, action="getting", tag=tag, file=file)

			if value != "":
				# remove the tag name prefix, and only us the first value
				value = value.splitlines()[0].partition("{tag}=".format(tag=tag))[2]

			orig = value
			if value == "":
				fastforward = False
				if tag in last:
					value = last[tag]
			try:
				# append this value if it's not there, so it can be edited
				added = last_history(value)

				# fast forward or prompt for input
				if fastforward:
					print(PROMPT.format(file=file, tag=tag, value=value))
					data = value
				else:
					try:
						data = input(PROMPT.format(file=file, tag=tag, value=value))
					except KeyboardInterrupt:
						print()
						sys.exit(EXIT_SUCCESS)
					except EOFError:
						print()
						sys.exit(EXIT_SUCCESS)

					# remove the extra value if it got added but not used
					if added and data != "" and data != value:
						cut_history(value)

					if data == "":
						data = value
					elif data == "#":
						data = ""
					elif data == "<":
						raise Prev
					elif data == ".":
						raise Next
					elif data == "*":
						raise FastForward

				if data != orig:
					ret = subprocess.Popen(["metaflac", "--preserve-modtime", "--remove-tag={tag}".format(tag=tag), "--", file], encoding="utf-8").wait()
					check(name="metaflac", ret=ret, action="removing", tag=tag, file=file)

					if data != "":
						ret = subprocess.Popen(["metaflac", "--preserve-modtime", "--set-tag={tag}={data}".format(tag=tag, data=data), "--", file], encoding="utf-8").wait()
						check(name="metaflac", ret=ret, action="setting", tag=tag, file=file)

					st = os.stat(file)
					os.utime(file, (st.st_atime, st.st_mtime + 1))

				if data != "":
					last[tag] = data
				hist[tag] = get_history()

				raise Next
			except Prev:
				if j > 0:
					j -= 1
				else:
					raise Prev
			except Next:
				j += 1
			except FastForward:
				fastforward = True
			else:
				raise AssertionError

		raise Next
	except Prev:
		print()
		if i > 0:
			i -= 1
			j = -1
	except Next:
		print()
		i += 1
		j = 0
	else:
		raise AssertionError

sys.exit(EXIT_SUCCESS)
