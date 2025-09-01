import flask
from flask import Flask, request
from flask_headers import headers as flask_headers
import sb2gs
import httpx
from pathlib import Path
from typing import Final
from zipfile import ZipFile
import json
import asyncio
import shutil
import markdown_it


commons_headers: Final[dict[str, str]] = {
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/75.0.3770.142 Safari/537.36",
    "x-csrftoken": "a",
    "x-requested-with": "XMLHttpRequest",
    "referer": "https://scratch.mit.edu",
}

SB2GS_INPUT: Final[Path] = Path("/tmp/sb2gs-input.sb3")
SB2GS_OUTPUT: Final[Path] = Path("/tmp/sb2gs-output")
SB2GS_ZIPFILE: Final[Path] = Path("/tmp/sb2gs-zipfile.zip")
HTTPY: Final[httpx.AsyncClient] = httpx.AsyncClient()
"""Async httpx client for general async requests"""

app = Flask(__name__)
MARKDOWNIT_PARSER = markdown_it.MarkdownIt()


@app.route('/')
def home():
    return MARKDOWNIT_PARSER.render("""\
# Hello
I wrote this particular web page in markdown but I am using markdownit.py to render it as html. Pretty cool huh.
# [About](/about)
""")


@app.route('/about')
def about():
    return MARKDOWNIT_PARSER.render("""\
# About
The link worked. Anyway this is my api, and I'm hosting it on vercel.

- [My GitHub account](https://github.com/FAReTek1/)
- [Source code](https://github.com/FAReTek1/faretek-api/)

In the future I plan to host docs for this on my github pages.
- # `GET` [/api/sb2gs/?id=885002848](/api/sb2gs/?id=885002848)
  Decompile a project with sb2gs, and return it as a zip file.
  Query parameters:
  - `id`: The project id
""")


@app.route('/api/sb2gs/')
@flask_headers({
    "Access-Control-Allow-Origin": "*"
})
def decompile_sb2gs():
    """
    Decompile a project using sb2gs, convert to zip, and ship back.
    """

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    project_id = request.args.get('id')
    server_response = flask.Response()  # headers={'Content-Type': 'application/zip'})

    if project_id is None or not project_id.isnumeric():
        return flask.Response(status=404)

    project_id = int(project_id)
    data_json = (httpx.get(f"https://api.scratch.mit.edu/projects/{project_id}",
                           headers=commons_headers)
                     .raise_for_status()
                     .json())
    project_token = data_json.get("project_token")

    if project_token is None:
        server_response.status = 404
        server_response.data = f"Could not get a project token, but got json response: {data_json}"
        return server_response

    project_json_content = (httpx.get(f"https://projects.scratch.mit.edu/{project_id}",
                                      params={"token": project_token},
                                      headers=commons_headers)
                            .raise_for_status()
                            .content)

    project_json = json.loads(project_json_content)
    asset_data: dict[str, httpx.Response] = {}

    for sprite in project_json["targets"]:
        for asset in sprite["costumes"] + sprite["sounds"]:
            md5ext: str = asset.get("md5ext",
                                    asset["assetId"] + '.' + asset["dataFormat"])
            asset_data[md5ext] = httpx.get(f"https://assets.scratch.mit.edu/internalapi/asset/{md5ext}/get/")

    with ZipFile(SB2GS_INPUT, "w") as archive:
        archive.writestr("project.json", project_json_content)
        for md5ext, resp in asset_data.items():
            archive.writestr(md5ext, resp.content)

    try:
        sb2gs.decompile(SB2GS_INPUT, SB2GS_OUTPUT, True, True)
    except Exception as e:
        server_response.status = 424
        server_response.data = f"sb2gs decompile error: {e}"
        return server_response

    shutil.make_archive("/tmp/sb2gs-zipfile", "zip", SB2GS_OUTPUT)
    server_response.data = SB2GS_ZIPFILE.read_bytes()
    server_response.headers["Content-Type"] = "application/zip"

    return server_response


if __name__ == '__main__':
    app.run(debug=True)
