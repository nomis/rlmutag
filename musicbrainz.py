#!/usr/bin/env python3
import json
import urllib.request
import sys


def fix(text):
	text = text.replace("’", "'")
	text = text.replace("“", '"')
	text = text.replace("”", '"')
	text = text.replace("‐", '-')
	return text


with urllib.request.urlopen("https://musicbrainz.org/ws/2/release/" + sys.argv[1] + "?inc=artist-credits+recordings&fmt=json") as f:
	x = json.loads(f.read())

for media in x["media"]:
	for track in media["tracks"]:
		if sys.argv[2] == "artist":
			print(fix("".join([artist["name"] + artist["joinphrase"] for artist in track["artist-credit"]])))
		elif sys.argv[2] == "title":
			print(fix(track["title"]))
