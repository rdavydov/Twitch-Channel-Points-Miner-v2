# Based on https://github.com/derrod/twl.py
# Original Copyright (c) 2020 Rodney
# The MIT License (MIT)

import copy
import getpass
import logging
import os
import pickle
import pyotp

import requests

from TwitchChannelPointsMiner.classes.Exceptions import (
    BadCredentialsException,
    WrongCookiesException,
)
from TwitchChannelPointsMiner.constants import CLIENT_ID, GQLOperations

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
        "otp_secret",
        "user_id",
        "email",
        "cookies"
    ]

    def __init__(self, client_id, device_id, username, user_agent, otp_secret,password=None):
        self.client_id = client_id
        self.device_id = device_id
        self.token = None
        self.login_check_result = False
        self.session = requests.session()
        self.session.headers.update(
            { "Client-ID": self.client_id, "X-Device-Id": self.device_id, "User-Agent": user_agent }
        )
        self.username = username
        self.password = password
        self.otp_secret = otp_secret
        self.user_id = None
        self.email = None

        self.cookies = []

    def login_flow(self):
        logger.info("You'll have to login to Twitch!")

        post_data = {
            "client_id": self.client_id,
            "undelete_user": False,
            "remember_me": True,
        }
        # login-fix
        use_backup_flow = False
        #use_backup_flow = True

        for attempt in range(0, 25):
            password = (
                getpass.getpass(f"Enter Twitch password for {self.username}: ")
                if self.password in [None, ""]
                else self.password
            )

            post_data["username"] = self.username
            post_data["password"] = password

            while True:
                # Try login without 2FA
                login_response = self.send_login_request(post_data)

                if "captcha_proof" in login_response:
                    post_data["captcha"] = dict(proof=login_response["captcha_proof"])

                if "error_code" in login_response:
                    err_code = login_response["error_code"]
                    if err_code in [3011, 3012]:  # missing 2fa token
                        if err_code == 3011:
                            if self.otp_secret == "":
                                logger.info(
                                "Two factor authentication enabled, please enter token below."
                                )
                            else:
                                post_data["authy_token"] = pyotp.TOTP(self.otp_secret).now() #HIER MAX
                                continue
                        else:
                            logger.info("Invalid two factor token, please try again.")
            

                        twofa = input("2FA token: ")
                        post_data["authy_token"] = twofa.strip()
                        continue

                    elif err_code in [3022, 3023]:  # missing 2fa token
                        if err_code == 3022:
                            logger.info("Login Verification code required.")
                            self.email = login_response["obscured_email"]
                        else:
                            logger.info(
                                "Invalid Login Verification code entered, please try again."
                            )

                        twofa = input(
                            f"Please enter the 6-digit code sent to {self.email}: "
                        )
                        post_data["twitchguard_code"] = twofa.strip()
                        continue

                    # invalid password, or password not provided
                    elif err_code in [3001, 3003]:
                        logger.info("Invalid username or password, please try again.")

                        # If the password is loaded from run.py, require the user to fix it there.
                        if self.password not in [None, ""]:
                            raise BadCredentialsException(
                                "Username or password is incorrect."
                            )

                        # If the user didn't load the password from run.py we can just ask for it again.
                        break
                    # login-fix
                    elif err_code == 1000:
                    #elif err_code in [1000, 5022]:
                        logger.info(
                            "Console login unavailable (CAPTCHA solving required)."
                        )
                        use_backup_flow = True
                        break
                    else:
                        logger.error(f"Unknown error: {login_response}")
                        raise NotImplementedError(
                            f"Unknown TwitchAPI error code: {err_code}"
                        )

                if "access_token" in login_response:
                    self.set_token(login_response["access_token"])
                    return self.check_login()

            if use_backup_flow:
                break

        if use_backup_flow:
            self.set_token(self.login_flow_backup(password))
            return self.check_login()

        return False

    def set_token(self, new_token):
        self.token = new_token
        self.session.headers.update({"Authorization": f"Bearer {self.token}"})

    def send_login_request(self, json_data):
        #response = self.session.post("https://passport.twitch.tv/protected_login", json=json_data)
        response = self.session.post("https://passport.twitch.tv/login", json=json_data, headers={
                    'Accept': 'application/vnd.twitchtv.v3+json',
                    'Accept-Encoding': 'gzip',
                    'Accept-Language': 'en-US',
                    'Content-Type': 'application/json; charset=UTF-8',
                    'Host': 'passport.twitch.tv'
                },)
        return response.json()

    def login_flow_backup(self, password = None):
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
        #options.add_argument("--user-agent=\"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/107.0.0.0 Safari/537.36\"")
        #options.add_argument("--window-size=1920,1080")
        #options.set_capability("detach", True)

        logger.info('Now a browser window will open, it will login with your data.')
        driver = uc.Chrome(
            options=options, use_subprocess=True#, executable_path=EXECUTABLE_PATH
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
        #print(self.cookies)
        #driver.close()
        driver.quit()
        self.username = self.get_cookie_value("login")
        #print(f"self.username: {self.username}")

        if not self.username:
            logger.error("Couldn't extract login, probably bad cookies.")
            return False

        return self.get_cookie_value("auth-token")"""
        logger.error("Backup login flow is not available. Use a VPN or wait a while to avoid the CAPTCHA.")
        return False

    def check_login(self):
        if self.login_check_result:
            return self.login_check_result
        if self.token is None:
            return False

        self.login_check_result = self.__set_user_id()
        return self.login_check_result

    def save_cookies(self, cookies_file):
        #pickle.dump(self.cookies, open(cookies_file, "wb"))
        # ^ only this line was needed with Selenium ^
        cookies_dict = self.session.cookies.get_dict()
        cookies_dict["auth-token"] = self.token
        if "persistent" not in cookies_dict:  # saving user id cookies
            cookies_dict["persistent"] = self.user_id

        self.cookies = []
        for cookie_name, value in cookies_dict.items():
            self.cookies.append({"name": cookie_name, "value": value})
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
            int(persistent.split("%")[0]) if persistent is not None else self.user_id
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
