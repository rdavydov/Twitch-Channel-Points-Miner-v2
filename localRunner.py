import os
from dotenv import load_dotenv
import logging
from pathlib import Path
import subprocess
from typing import Dict

# Load environment variables from .env file
load_dotenv()

def configure_logger() -> logging.Logger:
    logger = logging.getLogger(__name__)
    _handler = logging.StreamHandler()
    _handler.setFormatter(
        logging.Formatter(
            "%(asctime)s - %(levelname)s - %(module)s - [%(funcName)s]: %(message)s",
            datefmt="%d/%m/%y %H:%M:%S",
        )
    )
    logger.addHandler(_handler)
    logger.setLevel(logging.INFO)
    return logger

logger = configure_logger()

class EnvVarNotSetException(Exception):
    pass

def check_env_var(key: str) -> str:
    value = os.getenv(key)
    if value is None:
        logger.error(f'{key} environment variable is not defined. Set it in the .env file.')
        raise EnvVarNotSetException(f'{key} environment variable is not defined. Set it in the .env file.')
    logger.info(f'{key} environment variable is set.')
    return value

def main():
    # Automatically check and set environment variables
    env_vars = ["USER", "PASSWORD", "WEBHOOK", "CHATID", "TELEGRAMTOKEN", "GITHUB_TOKEN", "CJ_OWNER", "CJ_REPO", "CJ_FILE"]
    env_values: Dict[str, str] = {var: check_env_var(var) for var in env_vars}

    cwd = Path.cwd()
    logger.info(f"Current Working Directory: {cwd}")

    cookies_path = cwd / "cookies"
    if not cookies_path.exists():
        logger.error("cookies directory does not exist")
        raise FileNotFoundError("cookies directory does not exist")

    logger.info(f"Cookies Path: {cookies_path}")

    cookies_file = env_values["CJ_FILE"]
    final_path = cookies_path / cookies_file
    if not final_path.exists():
        logger.error("cookies file was not found")
        raise FileNotFoundError("cookies file was not found")

    logger.info("localRunner - Everything is OK, starting run.py")

    # Run run.py after testing and setting is done
    subprocess.run(['py', 'run.py'], check=True, text=True)

if __name__ == "__main__":
    main()