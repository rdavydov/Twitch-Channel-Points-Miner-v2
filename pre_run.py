# Copyright (c) 2024 benjammin4dayz
# https://github.com/benjammin4dayz
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

# https://stackoverflow.com/questions/18126559/how-can-i-download-a-single-raw-file-from-a-private-github-repo-using-the-comman
import os
import requests


def cookie_jar(token: str, repo_owner: str, repo_name: str, filename: str) -> None:
    """
    Downloads a file from a private repo using an authorization token

    Args:
    - token (str): The authorization token
    - repo_owner (str): The name of the repository owner
    - repo_name (str): The name of the repository
    - filename (str): The name of the file to download
    """

    # retrieve a file from a private repo by name
    response = requests.get(
        f"https://api.github.com/repos/{repo_owner}/{repo_name}/contents/{filename}",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github.v3+raw",
        },
    )

    # handle the response
    if response.status_code == 200:
        response = response.json()
    elif response.status_code == 404:
        # when a token or file is not valid, this endpoint will return 404
        raise Exception(
            "File could not be found. Ensure that a file with the given name exists and the access token is valid and has not yet expired."
        )
    else:
        raise Exception("Request failed. Status code:", response.status_code)

    # prepare to download the file
    file_path = os.path.join(os.getcwd(), "cookies", response["name"])
    download_url = response["download_url"]

    # ensure the directory exists
    dir_path = os.path.dirname(file_path)
    if not os.path.exists(dir_path):
        os.makedirs(dir_path)

    # download and write the file
    file_download = requests.get(download_url)
    with open(file_path, "wb") as f:
        f.write(file_download.content)

    print(f"!! Saved file to path {file_path}")


cookie_jar(
    token=os.getenv("GITHUB_TOKEN"),
    repo_owner=os.getenv("CJ_OWNER"),
    repo_name=os.getenv("CJ_REPO"),
    filename=os.getenv("CJ_FILE"),
)

os.system(f"python {os.path.join(os.getcwd(), 'run.py')}")
