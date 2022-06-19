# notion-markdown

A simple script to download a [Notion](https://www.notion.so) page that includes a database of pages as markdown

It's designed to be used with [hugo](https://gohugo.io) or other static site generators (thus it transforms "properties" to frontmatter)

## Usage

```bash
usage: getter.py [-h] [--content-dir CONTENT_DIR] [--static-dir STATIC_DIR] [--static-url STATIC_URL] notiondbid

Download Notion.so database as markdown files

positional arguments:
  notiondbid            ID of the Page that has the Notion DB

options:
  -h, --help            show this help message and exit
  --content-dir CONTENT_DIR, -c CONTENT_DIR
                        Output directory for markdown files
  --static-dir STATIC_DIR, -d STATIC_DIR
                        Output directory for referenced files that get downloaded
  --static-url STATIC_URL, -u STATIC_URL
                        URL path that the static files are accessible
```

The aformentioned page is here: https://www.notion.so/dzervas/WhyNot-Fail-Blog-d3c3143aac9d4550993abb7ff2ac0467
