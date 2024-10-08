#!/usr/bin/env python3
from os import path
from urllib.parse import quote_plus
from datetime import datetime
import requests
import json

HEADERS = {
	"Content-Type": "application/json"
}

def getCollectionIDs(notionDBID):
	if "-" not in notionDBID:
		notionDBID = notionDBID[:8] + "-" + notionDBID[8:12] + "-" + notionDBID[12:16] + "-" + notionDBID[16:20] + "-" + notionDBID[20:]

	res = requests.post("https://www.notion.so/api/v3/loadPageChunk", json={
		"page": { "id": notionDBID },
		"limit": 100,
		"cursor": { "stack": [] },
		"chunkNumber": 0,
		"verticalColumns": False
	})

	data = res.json()["recordMap"]

	collectionViewID = list(data["collection_view"].keys())[0]
	collectionID = list(data["collection"].keys())[0]
	collection = list(data["collection"].values())[0]
	spaceID = collection["value"]["space_id"]
	propertySchema = collection["value"]["schema"]

	return (spaceID, collectionID, collectionViewID, propertySchema)

def queryCollection(spaceID, collectionID, collectionViewID):
	res = requests.post("https://www.notion.so/api/v3/queryCollection", json={
		"collection": {
			"id": collectionID,
			"spaceId": spaceID
		},"collectionView": {
			"id": collectionViewID,
			"spaceId": spaceID
		},"loader":{
			"type":"reducer",
			"reducers":{
				"collection_group_results":{
					"type":"results",
					"limit":100
				}
			},
			"searchQuery":"",
			"userTimeZone":"Europe/Athens"
		}

	})

	return res.json()

def getPageIDs(spaceID, collectionID, collectionViewID):
	res = queryCollection(spaceID, collectionID, collectionViewID)
	return res["result"]["reducerResults"]["collection_group_results"]["blockIds"]

def handleTitle(titleArray):
	result = ""

	for textBlock in titleArray:
		if len(textBlock) == 1:
			result += textBlock[0]
			continue

		text = textBlock[0]
		formatting = textBlock[1]

		link = False
		link_target = None
		bold = False
		italics = False
		underline = False
		strikethrough = False
		code = False
		equation = False
		highlight = False
		highlight_color = None

		for f in formatting:
			if f[0] == "a":
				link = True
				try:
					link_target = f[1]
				except KeyError:
					print("Could not find link target")
			elif f[0] == "b":
				bold = True
			elif f[0] == "i":
				italics = True
			elif f[0] == "u" or f[0] == "_":
				underline = True
			elif f[0] == "s":
				strikethrough = True
			elif f[0] == "c":
				code = True
			elif f[0] == "e":
				equation = True
				text = f[1]
				print("In-text equation is broken!")
			elif f[0] == "h":
				highlight = True
				try:
					highlight_color = f[1]
				except KeyError:
					print("Could not find highlighting color")
			else:
				print(f"Unsupported formatting '{f}' of text {text} with value {formatting}")

		if code:
			text = f"`{text}`"
		if link:
			text = f"[{text}]({link_target})"
		if bold:
			text = f"**{text}**"
		if italics:
			text = f"*{text}*"
		if underline:
			text = f"<u>{text}</u>"
		if strikethrough:
			text = f"~~{text}~~"
		if highlight and highlight_color is not None:
			text = f'<span color="{highlight_color}">{text}</span>'

		result += text


	return result

def downloadFile(id, url, static_dir, static_path):
	res = requests.get("https://www.notion.so/image/" + quote_plus(url) + f"?table=block&id={id}")
	filename = "notion-" + id + "-" + path.basename(url)

	with open(static_dir + "/" + filename, "wb") as fd:
		fd.write(res.content)

	return static_path + "/" + filename


def getPage(pageID, propertySchema, static_dir, static_path):
	res = requests.post("https://www.notion.so/api/v3/loadPageChunk", json={
		"page": { "id": pageID },
		"limit": 100,
		"cursor": { "stack": [] },
		"chunkNumber": 0,
		"verticalColumns": False
	})

	data = res.json()["recordMap"]
	frontmatter = {}
	content = ""
	numbered_list = 0

	for block in data["block"].values():
		value = block["value"]
		id = value["id"]
		blockType = value["type"]
		parentID = value["parent_id"]

		if parentID == pageID and blockType == "collection_view":
			spaceID = value["space_id"]
			collectionID = value["collection_id"]
			collectionViewID = value["id"]

			collection = queryCollection(spaceID, collectionID, collectionViewID)
			collectionPropertySchema = collection["recordMap"]["collection"][collectionID]["value"]["schema"]

			content += "| " + " | ".join(x["name"] for x in collectionPropertySchema.values()) + " |\n"
			content += "| " + (" --- |" * len(collectionPropertySchema)) + "\n"

			# TODO: Sort the values correctly
			for collectionBlock in collection["recordMap"]["block"].values():
				if collectionBlock["value"]["parent_id"] != collectionID or collectionBlock["value"]["type"] != "page":
					continue

				content += "| " + " | ".join(x[0][0] for x in collectionBlock["value"]["properties"].values()) + " |\n"

			content += "\n"
			continue

		try:
			properties = value["properties"]
		except KeyError:
			if blockType == "divider":
				content += "---\n"
			continue

		if id == pageID and blockType == "page":
			frontmatter["date"] = datetime.fromtimestamp(value["created_time"] / 1000).isoformat()
			for k, v in properties.items():
				pName = propertySchema[k]["name"]
				if v[0][0] == "‣":
					value_array = v[0][1]
					# TODO: Handle more data types
					if value_array[0][0] == "d":
						# TODO: Handle dates better
						frontmatter[pName] = datetime.strptime(value_array[0][1]["start_date"], "%Y-%m-%d").isoformat()
				elif propertySchema[k]["type"] == "checkbox":
					frontmatter[pName] = v[0][0] == "Yes"
				elif propertySchema[k]["type"] == "file":
					url = v[0][1][0][1]
					frontmatter[pName] = downloadFile(id, url, static_dir, static_path)
				else:
					frontmatter[pName] = v[0][0]
			continue
		elif parentID != pageID:
			# We don't want any other block from another page
			continue

		if blockType != "numbered_list":
			numbered_list = 0

		# TODO: Handle value["format"]["block_color"]

		if blockType == "text":
			content += handleTitle(properties["title"]) + "\n"
		elif blockType == "header":
			content += "# " + handleTitle(properties["title"]) + "\n"
		elif blockType == "sub_header":
			content += "## " + handleTitle(properties["title"]) + "\n"
		elif blockType == "sub_sub_header":
			content += "### " + handleTitle(properties["title"]) + "\n"
		elif blockType == "image":
			url = properties["source"][0][0]
			title = handleTitle(properties["title"])
			if "caption" in properties:
				title = properties["caption"][0][0]

			content += "![" + title + "](" + downloadFile(id, url, static_dir, static_path) + ")\n"
		elif blockType == "bulleted_list":
			content += " - " + handleTitle(properties["title"])
		elif blockType == "numbered_list":
			numbered_list += 1
			content += " " + str(numbered_list) + ". " + handleTitle(properties["title"])
		elif blockType == "quote":
			content += " > " + handleTitle(properties["title"])
		elif blockType == "code":
			content += "```" + properties["language"][0][0] + "\n" + handleTitle(properties["title"]) + "\n```\n"
		elif blockType == "callout":
			content += "```callout " + value["format"]["block_color"] + "\n" + value["format"]["page_icon"] + handleTitle(properties["title"]) + "\n```\n"
		elif blockType == "to_do":
			try:
				checked = properties["checked"][0][0] == "Yes"
			except KeyError:
				checked = False

			if checked:
				content += " - [ ] " + handleTitle(properties["title"])
			else:
				content += " - [x] " + handleTitle(properties["title"])
		elif blockType == "toggle":
			print("Toggle block is not supported!")
		else:
			print()
			print(value)
			print(f"Unknown block type '{blockType}' with properties '{properties}'")
			continue
		content += "\n"

	return (fixFrontmatter(frontmatter), content)

def fixFrontmatter(frontmatter):
	result = {}
	for k, v in frontmatter.items():
		result[k.lower()] = v

	try:
		result["tags"] = result["tags"].split(",")
	except KeyError:
		pass

	return result


if __name__ == "__main__":
	import argparse

	def dir_path(target):
		if path.isdir(target):
			return target
		else:
			raise argparse.ArgumentTypeError(f"readable_dir:{target} is not a valid path")


	parser = argparse.ArgumentParser(description="Download Notion.so database as markdown files")
	parser.add_argument("notiondbid", type=str, help="ID of the Page that has the Notion DB")
	parser.add_argument("--content-dir", "-c", type=dir_path, help="Output directory for markdown files", default=".")
	parser.add_argument("--static-dir", "-d", type=dir_path, help="Output directory for referenced files that get downloaded", default=".")
	parser.add_argument("--static-url", "-u", type=str, help="URL path that the static files are accessible", default="/static")
	parser.add_argument("--add-frontmatter", "-a", action="append", type=str, help="Additional frontmatter to add to all pages (e.g. -a layout=page)", default=[])
	args = parser.parse_args()

	spaceID, collectionID, collectionViewID, propertySchema = getCollectionIDs(args.notiondbid)
	pageIDs = getPageIDs(spaceID, collectionID, collectionViewID)
	for p in pageIDs:
		with open(args.content_dir + "/notion-" + p + ".md", "w") as fd:
			print(f"Downloading page {p}")
			frontmatter, content = getPage(p, propertySchema, args.static_dir, args.static_url)

			for f in args.add_frontmatter:
				k, v = f.split("=", 1)
				frontmatter[k] = v
			print(frontmatter)

			fd.write(json.dumps(frontmatter) + "\n")
			fd.write(content)
