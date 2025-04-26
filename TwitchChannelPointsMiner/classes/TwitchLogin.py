# Based on https://github.com/derrod/twl.py
# Original Copyright (c) 2020 Rodney
# The MIT License (MIT)

import copy
# import getpass
import logging
import os
import pickle

# import webbrowser
# import browser_cookie3

import requests

from TwitchChannelPointsMiner.classes.Exceptions import (
    BadCredentialsException,
    WrongCookiesException,
)
from TwitchChannelPointsMiner.constants import CLIENT_ID, GQLOperations, USER_AGENTS

from datetime import datetime, timedelta, timezone
from time import sleep

logger = logging.getLogger(__name__)

"""def interceptor(request) -> str:
    if (
        request.method == 'POST'
        and request.url == 'https://passport.twitch.tv/protected_login'
    ):
        import json
        body = request.body.decode('utf-8')
        data = json.loads(body)
        data['client_id'] = CLIENT_ID
        request.body = json.dumps(data).encode('utf-8')
        del request.headers['Content-Length']
        request.headers['Content-Length'] = str(len(request.body))"""


class TwitchLogin(object):
    __slots__ = [
        "client_id",
        "device_id",
        "token",
        "login_check_result",
        "session",
        "session",
        "username",
        "password",
        "user_id",
        "email",
        "cookies",
        "shared_cookies"
    ]

    def __init__(self, client_id, device_id, username, user_agent, password=None):
        self.client_id = client_id
        self.device_id = device_id
        self.token = None
        self.login_check_result = False
        self.session = requests.session()
        self.session.headers.update(
            {"Client-ID": self.client_id,
                "X-Device-Id": self.device_id, "User-Agent": user_agent}
        )
        self.username = username
        self.password = password
        self.user_id = None
        self.email = None

        self.cookies = []
        self.shared_cookies = []

    def login_flow(self):
        logger.info("You'll have to login to Twitch!")

        post_data = {
            "client_id": self.client_id,
            "scopes": (
                "channel_read chat:read user_blocks_edit "
                "user_blocks_read user_follows_edit user_read"
            )
        }
        # login-fix
        use_backup_flow = False
        # use_backup_flow = True
        while True:
            logger.info("Trying the TV login method..")

            login_response = self.send_oauth_request(
                "https://id.twitch.tv/oauth2/device", post_data)

            # {
            #     "device_code": "40 chars [A-Za-z0-9]",
            #     "expires_in": 1800,
            #     "interval": 5,
            #     "user_code": "8 chars [A-Z]",
            #     "verification_uri": "https://www.twitch.tv/activate"
            # }

            if login_response.status_code != 200:
                logger.error("TV login response is not 200. Try again")
                break

            login_response_json = login_response.json()

            if "user_code" in login_response_json:
                user_code: str = login_response_json["user_code"]
                now = datetime.now(timezone.utc)
                device_code: str = login_response_json["device_code"]
                interval: int = login_response_json["interval"]
                expires_at = now + \
                    timedelta(seconds=login_response_json["expires_in"])
                logger.info(
                    "Open https://www.twitch.tv/activate"
                )
                logger.info(
                    f"and enter this code: {user_code}"
                )
                logger.info(
                    f"Hurry up! It will expire in {int(login_response_json['expires_in'] / 60)} minutes!"
                )
                # twofa = input("2FA token: ")
                # webbrowser.open_new_tab("https://www.twitch.tv/activate")

                post_data = {
                    "client_id": CLIENT_ID,
                    "device_code": device_code,
                    "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                }

                while True:
                    # sleep first, not like the user is gonna enter the code *that* fast
                    sleep(interval)
                    login_response = self.send_oauth_request(
                        "https://id.twitch.tv/oauth2/token", post_data)
                    if now == expires_at:
                        logger.error("Code expired. Try again")
                        break
                    # 200 means success, 400 means the user haven't entered the code yet
                    if login_response.status_code != 200:
                        continue
                    # {
                    #     "access_token": "40 chars [A-Za-z0-9]",
                    #     "refresh_token": "40 chars [A-Za-z0-9]",
                    #     "scope": [...],
                    #     "token_type": "bearer"
                    # }
                    login_response_json = login_response.json()
                    if "access_token" in login_response_json:
                        self.set_token(login_response_json["access_token"])
                        return self.check_login()
            # except RequestInvalid:
                # the device_code has expired, request a new code
                # continue
                # invalidate_after is not None
                # account for the expiration landing during the request
                # and datetime.now(timezone.utc) >= (invalidate_after - session_timeout)
            # ):
                # raise RequestInvalid()
                    else:
                        if "error_code" in login_response:
                            err_code = login_response["error_code"]

                        logger.error(f"Unknown error: {login_response}")
                        raise NotImplementedError(
                            f"Unknown TwitchAPI error code: {err_code}"
                        )

            if use_backup_flow:
                break

        if use_backup_flow:
            # self.set_token(self.login_flow_backup(password))
            self.set_token(self.login_flow_backup())
            return self.check_login()

        return False

    def set_token(self, new_token):
        self.token = new_token
        self.session.headers.update({"Authorization": f"Bearer {self.token}"})

    # def send_login_request(self, json_data):
    def send_oauth_request(self, url, json_data):
        # response = self.session.post("https://passport.twitch.tv/protected_login", json=json_data)
        """response = self.session.post("https://passport.twitch.tv/login", json=json_data, headers={
            'Accept': 'application/vnd.twitchtv.v3+json',
            'Accept-Encoding': 'gzip',
            'Accept-Language': 'en-US',
            'Content-Type': 'application/json; charset=UTF-8',
            'Host': 'passport.twitch.tv'
        },)"""
        response = self.session.post(url, data=json_data, headers={
            'Accept': 'application/json',
            'Accept-Encoding': 'gzip',
            'Accept-Language': 'en-US',
            "Cache-Control": "no-cache",
            "Client-Id": CLIENT_ID,
            "Host": "id.twitch.tv",
            "Origin": "https://android.tv.twitch.tv",
            "Pragma": "no-cache",
            "Referer": "https://android.tv.twitch.tv/",
            "User-Agent": USER_AGENTS["Android"]["TV"],
            "X-Device-Id": self.device_id
        },)
        return response

    def login_flow_backup(self, password=None):
        """Backup OAuth Selenium login
        from undetected_chromedriver import ChromeOptions
        import seleniumwire.undetected_chromedriver.v2 as uc
        from selenium.webdriver.common.by import By
        from time import sleep

        HEADLESS = False

        options = uc.ChromeOptions()
        if HEADLESS is True:
            options.add_argument('--headless')
        options.add_argument('--log-level=3')
        options.add_argument('--disable-web-security')
        options.add_argument('--allow-running-insecure-content')
        options.add_argument('--lang=en')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-gpu')
        # options.add_argument("--user-agent=\"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/107.0.0.0 Safari/537.36\"")
        # options.add_argument("--window-size=1920,1080")
        # options.set_capability("detach", True)

        logger.info(
            'Now a browser window will open, it will login with your data.')
        driver = uc.Chrome(
            options=options, use_subprocess=True  # , executable_path=EXECUTABLE_PATH
        )
        driver.request_interceptor = interceptor
        driver.get('https://www.twitch.tv/login')

        driver.find_element(By.ID, 'login-username').send_keys(self.username)
        driver.find_element(By.ID, 'password-input').send_keys(password)
        sleep(0.3)
        driver.execute_script(
            'document.querySelector("#root > div > div.scrollable-area > div.simplebar-scroll-content > div > div > div > div.Layout-sc-nxg1ff-0.gZaqky > form > div > div:nth-child(3) > button > div > div").click()'
        )

        logger.info(
            'Enter your verification code in the browser and wait for the Twitch website to load, then press Enter here.'
        )
        input()

        logger.info("Extracting cookies...")
        self.cookies = driver.get_cookies()
        # print(self.cookies)
        # driver.close()
        driver.quit()
        self.username = self.get_cookie_value("login")
        # print(f"self.username: {self.username}")

        if not self.username:
            logger.error("Couldn't extract login, probably bad cookies.")
            return False

        return self.get_cookie_value("auth-token")"""

        # logger.error("Backup login flow is not available. Use a VPN or wait a while to avoid the CAPTCHA.")
        # return False

        """Backup OAuth login flow in case manual captcha solving is required"""
        browser = input(
            "What browser do you use? Chrome (1), Firefox (2), Other (3): "
        ).strip()
        if browser not in ("1", "2"):
            logger.info("Your browser is unsupported, sorry.")
            return None

        input(
            "Please login inside your browser of choice (NOT incognito mode) and press Enter..."
        )
        logger.info("Loading cookies saved on your computer...")
        twitch_domain = ".twitch.tv"
        if browser == "1":  # chrome
            cookie_jar = browser_cookie3.chrome(domain_name=twitch_domain)
        else:
            cookie_jar = browser_cookie3.firefox(domain_name=twitch_domain)
        # logger.info(f"cookie_jar: {cookie_jar}")
        cookies_dict = requests.utils.dict_from_cookiejar(cookie_jar)
        # logger.info(f"cookies_dict: {cookies_dict}")
        self.username = cookies_dict.get("login")
        self.shared_cookies = cookies_dict
        return cookies_dict.get("auth-token")

    def check_login(self):
        if self.login_check_result:
            return self.login_check_result
        if self.token is None:
            return False

        self.login_check_result = self.__set_user_id()
        return self.login_check_result

    def save_cookies(self, cookies_file):
        logger.info("Saving cookies to your computer..")
        cookies_dict = self.session.cookies.get_dict()
        # print(f"cookies_dict2pickle: {cookies_dict}")
        cookies_dict["auth-token"] = self.token
        if "persistent" not in cookies_dict:  # saving user id cookies
            cookies_dict["persistent"] = self.user_id

        # old way saves only 'auth-token' and 'persistent'
        self.cookies = []
        # cookies_dict = self.shared_cookies
        # print(f"cookies_dict2pickle: {cookies_dict}")
        for cookie_name, value in cookies_dict.items():
            self.cookies.append({"name": cookie_name, "value": value})
        # print(f"cookies2pickle: {self.cookies}")
        pickle.dump(self.cookies, open(cookies_file, "wb"))

    def get_cookie_value(self, key):
        for cookie in self.cookies:
            if cookie["name"] == key:
                if cookie["value"] is not None:
                    return cookie["value"]
        return None

    def load_cookies(self, cookies_file):
        if os.path.isfile(cookies_file):
            self.cookies = pickle.load(open(cookies_file, "rb"))
        else:
            raise WrongCookiesException("There must be a cookies file!")

    def get_user_id(self):
        persistent = self.get_cookie_value("persistent")
        user_id = (
            int(persistent.split("%")[
                0]) if persistent is not None else self.user_id
        )
        if user_id is None:
            if self.__set_user_id() is True:
                return self.user_id
        return user_id

    def __set_user_id(self):
        json_data = copy.deepcopy(GQLOperations.ReportMenuItem)
        json_data["variables"] = {"channelLogin": self.username}
        response = self.session.post(GQLOperations.url, json=json_data)

        if response.status_code == 200:
            json_response = response.json()
            if (
                "data" in json_response
                and "user" in json_response["data"]
                and json_response["data"]["user"]["id"] is not None
            ):
                self.user_id = json_response["data"]["user"]["id"]
                return True
        return False

    def get_auth_token(self):
        return self.get_cookie_value("auth-token")
