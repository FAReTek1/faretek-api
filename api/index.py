import flask
from flask import Flask, request
import sb2gs
import httpx
from pathlib import Path
from typing import Final
from zipfile import ZipFile
import json
import asyncio
from typing import Coroutine, Any
import shutil
import markdown_it

SB2GS_INPUT: Final[Path] = Path("sb2gs-input.sb3")
SB2GS_OUTPUT: Final[Path] = Path("sb2gs-output")
SB2GS_ZIPFILE: Final[Path] = Path("sb2gs-zipfile.zip")
HTTPY: Final[httpx.AsyncClient] = httpx.AsyncClient()
app = Flask(__name__)
MARKDOWNIT_PARSER = markdown_it.MarkdownIt()


@app.route('/')
def home():
    server_response = flask.Response()
    server_response.data = MARKDOWNIT_PARSER.render("""\
# Hello
I wrote this particular web page in markdown but I am using markdownit.py to render it as html. Pretty cool huh.
""")

    return server_response


@app.route('/about')
def about():
    return 'About'


@app.route('/sb2gs/')
async def decompile_sb2gs():
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
    project_token = (httpx.get(f"https://api.scratch.mit.edu/projects/{project_id}")
                     .raise_for_status()
                     .json()
                     .get("project_token"))

    if project_token is None:
        server_response.status = 404
        server_response.data = "Could not get a project token, but got json response."
        return server_response

    project_json_content = (httpx.get(f"https://projects.scratch.mit.edu/{project_id}",
                                      params={"token": project_token})
                            .raise_for_status()
                            .content)

    project_json = json.loads(project_json_content)
    data = ""

    md5exts: list[str] = []
    futures: list[Coroutine[Any, Any, httpx.Response]] = []
    for sprite in project_json["targets"]:
        for asset in sprite["costumes"] + sprite["sounds"]:
            md5ext: str = asset["md5ext"]
            md5exts.append(md5ext)
            futures.append(HTTPY.get(f"https://assets.scratch.mit.edu/internalapi/asset/{md5ext}/get/"))

    resps: list[httpx.Response] = await asyncio.gather(*futures)

    with ZipFile(SB2GS_INPUT, "w") as archive:
        archive.writestr("project.json", project_json_content)
        for md5ext, resp in zip(md5exts, resps):
            archive.writestr(md5ext, resp.content)

    sb2gs.decompile(SB2GS_INPUT, SB2GS_OUTPUT)
    for root, dirs, files in SB2GS_OUTPUT.walk():
        print(root, dirs, files)

    shutil.make_archive("sb2gs-zipfile", "zip", SB2GS_OUTPUT)
    print(SB2GS_ZIPFILE.absolute().as_posix())

    server_response.data = SB2GS_ZIPFILE.read_bytes()
    server_response.headers["Content-Type"] = "application/zip"

    return server_response


if __name__ == '__main__':
    app.run(debug=True)
