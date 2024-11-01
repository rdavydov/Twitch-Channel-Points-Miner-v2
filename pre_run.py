import logging
import os
import requests
import subprocess


class PreRun:
    # Set up the logger
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
        """
        Handles all pre-run tasks before starting the app

        Args:
        - self (PreRun): PreRun class instance
        - gh_token (str): GitHub personal access token
        - repo_owner (str): GitHub username of the repository owner
        - repo_name (str): Name of the GitHub repository
        - cookie_file (str): The name of the cookie file to be downloaded
        - entrypoint (str, optional): The name of the entrypoint script. Defaults to "run.py".
        - exit_on_error (bool, optional): Whether to halt further execution if an error occurs. Defaults to True.
        - log_level (int, optional): The logging level. Defaults to logging.INFO.

        Raises:
        - ValueError: If any of the required arguments is missing
        - PreRun.WebRequestError: If the request fails

        Example:
        >>> PreRun(
        ...     gh_token="ghp_f0ob4rb4z",
        ...     repo_owner="foo",
        ...     repo_name="bar",
        ...     cookie_file="baz.pkl",
        ...     entrypoint="main.py",
        ...     exit_on_error=False,
        ...     log_level=logging.DEBUG
        ... )
        """
        self.logger.setLevel(log_level)

        # Check for required arguments
        if not all([gh_token, repo_owner, repo_name, cookie_file, entrypoint]):
            self.logger.critical(
                f"Missing required arguments in {self.__class__.__name__}(). Cannot continue!"
            )
            exit(1)

        # Initialize instance variables
        self._token = gh_token
        self.repo_owner = repo_owner
        self.repo_name = repo_name
        self.cookie_file = cookie_file
        self.entrypoint = entrypoint
        self.exit_on_error = exit_on_error

        # Perform preparation tasks and start the entrypoint
        self.preparation_tasks()
        self.start_entrypoint()

    def preparation_tasks(self) -> None:
        """Performs pre-run tasks before starting the app"""
        self.logger.info("Started...")
        try:
            self.cookie_jar()
            self.logger.info("Complete!")
        except PreRun.WebRequestError as e:
            e.troubleshoot()
            if self.exit_on_error:
                self.logger.critical("Web request failed. Exiting...")
                exit(1)
            else:
                self.logger.warning("Web request failed. Continuing anyway...")

    def start_entrypoint(self) -> None:
        """Starts the app after all pre-run tasks are completed"""
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
        """
        Downloads a file from a private repo using an authorization token,
        then mounts the file in the working directory.

        Raises:
        - PreRun.WebRequestError: If the request fails
        """
        # Make a request to get file information
        response = self._make_request(
            f"https://api.github.com/repos/{self.repo_owner}/{self.repo_name}/contents/{self.cookie_file}"
        )

        # Prepare to download the file
        file_path = os.path.join(os.getcwd(), "cookies", response["name"])
        self._ensure_directory_exists(os.path.dirname(file_path))

        # Download and write the file
        download_url = response["download_url"]
        self._download_file(download_url, file_path)

        self.logger.info(f"Mounted '{file_path}'")

    def _make_request(self, url: str) -> dict:
        """Helper method to make a GET request and handle errors"""
        response = requests.get(
            url,
            headers={
                "Authorization": f"Bearer {self._token}",
                "Accept": "application/vnd.github.v3+raw",
            },
            timeout=60,
        )

        if response.status_code != 200:
            raise self.WebRequestError(response.status_code)
        return response.json()

    def _ensure_directory_exists(self, dir_path: str) -> None:
        """Helper method to ensure a directory exists"""
        if not os.path.exists(dir_path):
            os.makedirs(dir_path)

    def _download_file(self, url: str, file_path: str) -> None:
        """Helper method to download a file from a URL"""
        response = requests.get(url, timeout=60)
        with open(file_path, "wb") as f:
            f.write(response.content)

    class WebRequestError(Exception):
        """Helper class for errors related to GitHub API"""

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
            """Logs the error and provides troubleshooting hints if available"""
            PreRun.logger.error(self)
            if self.hint:
                PreRun.logger.debug(f"{self}\n  Troubleshooting:{self.hint}")

        def __str__(self) -> str:
            return f"{self.__class__.__name__} -> {self.message}"


# Configure and start the task runner
PreRun(
    gh_token=os.getenv("GITHUB_TOKEN"),
    repo_owner=os.getenv("CJ_OWNER"),
    repo_name=os.getenv("CJ_REPO"),
    cookie_file=os.getenv("CJ_FILE"),
    entrypoint="run.py",
    exit_on_error=False,
    log_level=logging.DEBUG,
)
