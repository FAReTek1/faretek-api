# sb2gs

sb2gs is a decompiler for goboscript. The original source code can be found [here](https://github.com/aspizu/sb2gs),
however this API uses a modified version running on Python 3.12 so it can run on vercel.
The whl file is accessible [here](https://github.com/FAReTek1/faretek-api/blob/main/sb2gs-2.0.0-py3-none-any.whl).

## `GET` [/?id=885002848](https://faretek-api.vercel.app/api/sb2gs/?id=885002848)
> Decompile a project with sb2gs, and return it as a zip file.

#### Query params:

`id`
:   The project id
