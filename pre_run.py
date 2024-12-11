import logging
import os
import requests
import subprocess
import pickle
import base64

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
            cookie_handler = CookieHandler(self.repo_owner, self.repo_name, self.cookie_file, self._token, self.logger)
            cookie_handler.download_and_validate_cookies()
            self.logger.info("Complete!")
        except CookieHandler.WebRequestError as e:
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

class CookieHandler:
    def __init__(self, repo_owner, repo_name, cookie_file, token, logger):
        self.repo_owner = repo_owner
        self.repo_name = repo_name
        self.cookie_file = cookie_file
        self._token = token
        self.logger = logger

    def download_and_validate_cookies(self):
        try:
            response = requests.get(
                f"https://api.github.com/repos/{self.repo_owner}/{self.repo_name}/contents/{self.cookie_file}",
                headers={
                    "Authorization": f"Bearer {self._token}",
                    "Accept": "application/vnd.github.v3+raw",
                },
                timeout=60
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise self.WebRequestError(response.status_code) from e

        response = response.json()
        file_path = os.path.join(os.getcwd(), "cookies", response["name"])
        download_url = response["download_url"]

        # Check if the directory exists, and if not, create it
        directory = os.path.dirname(file_path)
        if not os.path.exists(directory):
            os.makedirs(directory, exist_ok=True)

        try:
            file_download = requests.get(download_url, timeout=60)
            file_download.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise self.WebRequestError(file_download.status_code) from e

        with open(file_path, "wb") as f:
            f.write(file_download.content)

        if os.path.getsize(file_path) == 0:
            self.logger.error("The downloaded file is empty.")
            return

        try:
            with open(file_path, "rb") as f:
                data = pickle.load(f)

            if self.validate_cookies(data):
                encoded_cookies = base64.b64encode(pickle.dumps(data)).decode('utf-8')
                os.environ["VALIDATED_COOKIES"] = encoded_cookies
            else:
                self.logger.error("The downloaded file contains invalid data.")
        except pickle.UnpicklingError:
            self.logger.error("The downloaded file is not a valid pickle file.")
        except Exception as e:
            self.logger.error(f"An unexpected error occurred: {e}")

        self.logger.info(f"Mounted '{file_path}'")

    def validate_cookies(self, data) -> bool:
        required_keys = {"auth-token", "persistent"}
        return all(key in data for key in required_keys)

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
                        "Ensure that the file path is correct and the file exists in the repository."
                    ]
                )
            else:
                self.message = f"An error occurred. HTTP Status Code: {code}"
                self.hint = ""
            super().__init__(self.message)

        def troubleshoot(self) -> None:
            PreRun.logger.error(self)
            if self.hint is not None:
                PreRun.logger.debug(f"{self}\n  Troubleshooting:{self.hint}")

        def __str__(self) -> str:
            return f"{self.__class__.__name__} -> {self.message}"


PreRun(
    gh_token=os.getenv("GITHUB_TOKEN"),
    repo_owner=os.getenv("CJ_OWNER"),
    repo_name=os.getenv("CJ_REPO"),
    cookie_file=os.getenv("CJ_FILE"),
    entrypoint="run.py",
    exit_on_error=False,
    log_level=logging.DEBUG,
)