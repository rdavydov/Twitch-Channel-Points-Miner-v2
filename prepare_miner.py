import os
import logging
import requests
import subprocess
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Function to set environment variable if not already set
def set_env_var(key):
    value = os.getenv(key)
    if value is None:
        raise Exception(f'{key} environment variable is not defined. Set it in the .env file.')

# Automatically check and set environment variables
env_vars = ["USER", "PASSWORD", "WEBHOOK", "CHATID", "TELEGRAMTOKEN", "GITHUB_TOKEN", "CJ_OWNER", "CJ_REPO", "CJ_FILE"]
for var in env_vars:
    set_env_var(var)

# Check for cookies directory
cwd = os.getcwd()
cookies_path = "cookies"
if not os.path.exists(os.path.join(cwd, cookies_path)):
    raise Exception("cookies directory does not exist")

# Check for cookies file
cookies_file = os.getenv("CJ_FILE")
if cookies_file is None:
    raise Exception('CJ_FILE environment variable is not defined. Set it with the following command: `export CJ_FILE="<filename>"`')

# Fetch environment variables
gh_token = os.getenv("GITHUB_TOKEN")
repo_owner = os.getenv("CJ_OWNER")
repo_name = os.getenv("CJ_REPO")

# Check if any required environment variable is missing
if not all([gh_token, repo_owner, repo_name, cookies_file]):
    raise ValueError("Missing required environment variables. Cannot continue!")

class PreRun:
    logger = logging.getLogger(__name__)
    _handler = logging.StreamHandler()
    _handler.setFormatter(
        logging.Formatter(
            "%(asctime)s - %(levelname)s - %(module)s - [%(funcName)s]: %(message)s",
            datefmt="%d/%m/%y %H:%M:%S",
        )
    )
    logger.addHandler(_handler)

    def __init__(
        self,
        gh_token: str | None,
        repo_owner: str | None,
        repo_name: str | None,
        cookie_file: str | None,
        entrypoint: str | None = "run.py",
        exit_on_error: bool = True,
        log_level: int = logging.INFO,
    ) -> None:
        self.logger.setLevel(log_level)

        if (
            gh_token is None
            or repo_owner is None
            or repo_name is None
            or cookie_file is None
            or entrypoint is None
        ):
            self.logger.critical(
                f"Missing required arguments in {self.__class__.__name__}(). Cannot continue!"
            )
            exit(1)

        self._token = gh_token
        self.repo_owner = repo_owner
        self.repo_name = repo_name
        self.cookie_file = cookie_file
        self.entrypoint = entrypoint
        self.exit_on_error = exit_on_error

        self.preparation_tasks()
        self.start_entrypoint()

    def preparation_tasks(self) -> None:
        self.logger.info("Started...")
        try:
            self.cookie_jar()
            self.logger.info("Complete!")
        except PreRun.WebRequestError as e:
            e.troubleshoot()
            if self.exit_on_error is True:
                self.logger.critical("Web request failed. Exiting...")
                exit(1)
            else:
                self.logger.warning("Web request failed. Continuing anyway...")
                pass

    def start_entrypoint(self) -> None:
        self.logger.info("Starting app...")
        try:
            subprocess.run(
                ["python", os.path.join(os.getcwd(), self.entrypoint)],
                check=True,
                stderr=subprocess.PIPE,
            )
        except subprocess.CalledProcessError as e:
            self.logger.debug(e.stderr.decode("utf-8"))
            self.logger.critical(e)
            exit(1)

    def cookie_jar(self) -> None:
        response = requests.get(
            f"https://api.github.com/repos/{self.repo_owner}/{self.repo_name}/contents/{self.cookie_file}",
            headers={
                "Authorization": f"Bearer {self._token}",
                "Accept": "application/vnd.github.v3+raw",
            },
            timeout=60
        )

        if response.status_code != 200:
            raise self.WebRequestError(response.status_code)
        response = response.json()

        file_path = os.path.join(os.getcwd(), "cookies", response["name"])
        download_url = response["download_url"]

        dir_path = os.path.dirname(file_path)
        if not os.path.exists(dir_path):
            os.makedirs(dir_path)

        file_download = requests.get(download_url, timeout=60)
        with open(file_path, "wb") as f:
            f.write(file_download.content)

        self.logger.info(f"Mounted '{file_path}'")

    class WebRequestError(Exception):
        def __init__(self, code: int) -> None:
            __sep = "\n     \U00002713 "
            if code == 401:
                self.message = "Authorization token is invalid."
                self.hint = __sep.join(
                    ["", "Ensure that $GITHUB_TOKEN was set and has not yet expired."]
                )
            elif code == 404:
                self.message = "Requested file could not be found."
                self.hint = __sep.join(
                    [
                        "",
                        "Ensure that $CJ_OWNER and $CJ_REPO were set and point to the private repository.",
                        "Ensure that $CJ_FILE was set and points to a file that exists in the repository.",
                    ]
                )
            else:
                self.message = f"Unexpected error. Status code: {code}"
                self.hint = None

            super().__init__(self.message)
            self.code = code

        def troubleshoot(self) -> None:
            PreRun.logger.error(self)
            if self.hint is not None:
                PreRun.logger.debug(f"{self}\n  Troubleshooting:{self.hint}")

        def __str__(self) -> str:
            return f"{self.__class__.__name__} -> {self.message}"

# configure and start the task runner
PreRun(
    gh_token=gh_token,
    repo_owner=repo_owner,
    repo_name=repo_name,
    cookie_file=cookies_file,
    entrypoint="run.py",
    exit_on_error=False,
    log_level=logging.INFO,
)