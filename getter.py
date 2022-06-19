import requests

HEADERS = {
	"Content-Type": "application/json"
}

def getCollectionIDs(notionDBID):
	res = requests.post("https://www.notion.so/api/v3/loadCachedPageChunk", json={
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

def getPageIDs(spaceID, collectionID, collectionViewID):
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
			# TODO: Filter by published
			# },"filter":{
			# 	"operator":"and",
			# 	"filters":[{
			# 		"property":"TerZ",
			# 		"filter":{
			# 			"operator":"checkbox_is",
			# 			"value": {"type":"exact","value":true}
			# 		}
			# 	}]
			},
			"searchQuery":"",
			"userTimeZone":"Europe/Athens"
		}

	})

	return res.json()["result"]["reducerResults"]["collection_group_results"]["blockIds"]

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
			elif f[0] == "u":
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
		if code:
			text = f"`{text}`"
		if highlight and highlight_color is not None:
			text = f'<span color="{highlight_color}">{text}</span>'

		result += text


	return result

def getPage(pageID, propertySchema):
	res = requests.post("https://www.notion.so/api/v3/loadCachedPageChunk", json={
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
		try:
			properties = value["properties"]
		except KeyError:
			continue
		parentID = value["parent_id"]

		if id == pageID and blockType == "page":
			for k, v in properties.items():
				pName = propertySchema[k]["name"]
				if propertySchema[k]["type"] == "checkbox":
					frontmatter[pName] = v[0][0] == "Yes"
				elif propertySchema[k]["type"] == "file":
					frontmatter[pName] = v[0][1][0][1]
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
			content += "![" + handleTitle(properties["title"]) + "](" + properties["source"][0][0] + ")\n"
			content += properties["caption"][0][0]
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
				content += " - [] " + handleTitle(properties["title"])
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
	from sys import argv
	spaceID, collectionID, collectionViewID, propertySchema = getCollectionIDs(argv[1])
	pageIDs = getPageIDs(spaceID, collectionID, collectionViewID)
	for p in pageIDs:
		with open(p + ".md", "w") as fd:
			print(f"Downloading page {p}")
			frontmatter, content = getPage(p, propertySchema)
			fd.write(str(frontmatter) + "\n")
			fd.write(content)
