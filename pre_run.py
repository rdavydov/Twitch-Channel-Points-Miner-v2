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
            timeout=60)

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

        if os.path.getsize(file_path) == 0:
            print("Error: The downloaded file is empty.")
        else:
            try:
                with open(file_path, "rb") as f:
                    data = pickle.load(f)
                
                if self.validate_cookies(data):
                    encoded_cookies = base64.b64encode(pickle.dumps(data)).decode('utf-8')
                    os.environ["VALIDATED_COOKIES"] = encoded_cookies
                else:
                    print("Error: The downloaded file contains invalid data.")
            except pickle.UnpicklingError:
                print("Error: The downloaded file is not a valid pickle file.")
            except Exception as e:
                print(f"An unexpected error occurred: {e}")

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


PreRun(
    gh_token=os.getenv("GITHUB_TOKEN"),
    repo_owner=os.getenv("CJ_OWNER"),
    repo_name=os.getenv("CJ_REPO"),
    cookie_file=os.getenv("CJ_FILE"),
    entrypoint="run.py",
    exit_on_error=False,
    log_level=logging.DEBUG,
)