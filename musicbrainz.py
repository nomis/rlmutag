#!/usr/bin/env python3
import json
import sys
import urllib.request


def fix(text):
	text = text.replace("’", "'")
	text = text.replace("“", '"')
	text = text.replace("”", '"')
	text = text.replace("‐", "-")
	text = text.replace("…", "...")
	return text


with urllib.request.urlopen("https://musicbrainz.org/ws/2/release/" + sys.argv[1] + "?inc=artist-credits+recordings&fmt=json") as f:
	x = json.loads(f.read())

with open("a", "wt") as a:
	with open("t", "wt") as t:
		for media in x["media"]:
			for track in media["tracks"]:
				print(fix("".join([artist["name"] + artist["joinphrase"] for artist in track["artist-credit"]])), file=a)
				print(fix(track["title"]), file=t)
