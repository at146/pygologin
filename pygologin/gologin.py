import json
import time
import os
import stat
import sys
import shutil
from typing import Any, Dict, List, Union
import requests
import zipfile
import subprocess
import pathlib
import tempfile
import math
import socket
import random
import psutil
import logging

from requests import Response

from pygologin.cookiesManager.cookiesManager import CookiesManager
from pygologin.exceptions import ProtocolException
from pygologin.extensionsManager.extensionsManager import ExtensionsManager


API_URL = "https://api.gologin.com"
PROFILES_URL = "https://gprofiles-new.gologin.com/"
GET_TIMEZONE_URL = "https://geo.myip.link"
FILES_GATEWAY = "https://files-gateway.gologin.com"


log = logging.getLogger(__name__)
log.addHandler(logging.NullHandler())


class GoLogin(object):
    def __init__(self, options: Dict[str, Any]) -> None:
        self.access_token: Union[str, None] = options.get("token")
        self.profile_id: Union[str, None] = options.get("profile_id")
        self.tmpdir: str = options.get("tmpdir", tempfile.gettempdir())
        self.address: str = options.get("address", "127.0.0.1")
        self.extra_params: List[str] = options.get("extra_params", [])
        self.port: int = options.get("port", 3500)
        self.local: bool = options.get("local", False)
        self.spawn_browser: bool = options.get("spawn_browser", True)
        self.credentials_enable_service = options.get("credentials_enable_service")
        self.cleaningLocalCookies: bool = options.get("cleaningLocalCookies", False)
        self.uploadCookiesToServer: bool = options.get("uploadCookiesToServer", False)
        self.writeCookiesFromServer: bool = options.get("writeCookiesFromServer", False)
        self.executablePath: str = ""
        self.is_cloud_headless: bool = options.get("is_cloud_headless", True)
        self.is_new_cloud_browser: bool = options.get("is_new_cloud_browser", True)

        home = str(pathlib.Path.home())
        browser_gologin = os.path.join(home, ".gologin", "browser")
        try:
            for orbita_browser in os.listdir(browser_gologin):
                if (
                    not orbita_browser.endswith(".zip")
                    and not orbita_browser.endswith(".tar.gz")
                    and orbita_browser.startswith("orbita-browser")
                ):
                    self.executablePath = options.get(
                        "executablePath",
                        os.path.join(browser_gologin, orbita_browser, "chrome"),
                    )
                    if (
                        not os.path.exists(self.executablePath)
                        and not orbita_browser.endswith(".tar.gz")
                        and sys.platform == "darwin"
                    ):
                        self.executablePath = os.path.join(
                            home,
                            browser_gologin,
                            orbita_browser,
                            "Orbita-Browser.app/Contents/MacOS/Orbita",
                        )

        except Exception:
            self.executablePath = ""

        if not self.executablePath:
            raise Exception(
                f"Orbita executable file not found in HOME ({browser_gologin}). Is gologin installed on your system?"
            )

        if self.extra_params:
            log.debug("extra_params %s", self.extra_params)
        self.setProfileId(options.get("profile_id"))
        self.preferences: Dict[str, Any] = {}
        self.pid = int()

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *args, **kwargs):
        self.stop()

    def setProfileId(self, profile_id: Union[str, None]) -> None:
        self.profile_id = profile_id
        if self.profile_id is None:
            return
        self.profile_path = os.path.join(self.tmpdir, "gologin_" + self.profile_id)
        self.profile_zip_path = os.path.join(
            self.tmpdir, "gologin_" + self.profile_id + ".zip"
        )
        self.profile_zip_path_upload = os.path.join(
            self.tmpdir, "gologin_" + self.profile_id + "_upload.zip"
        )

    def loadExtensions(self) -> Union[str, None]:
        profile = self.profile
        chromeExtensions = profile.get("chromeExtensions", [])
        extensionsManagerInst = ExtensionsManager()
        pathToExt = ""
        profileExtensionsCheck = []
        for ext in chromeExtensions:
            try:
                ver = extensionsManagerInst.downloadExt(ext)
                pathToExt += os.path.join(
                    pathlib.Path.home(),
                    ".gologin",
                    "extensions",
                    "chrome-extensions",
                    ext + "@" + ver + ",",
                )
                profileExtensionsCheck.append(
                    os.path.join(
                        pathlib.Path.home(),
                        ".gologin",
                        "extensions",
                        "chrome-extensions",
                        ext + "@" + ver,
                    )
                )
            except Exception:
                continue

        pref_file = os.path.join(self.profile_path, "Default", "Preferences")
        with open(pref_file, "r", encoding="utf-8") as pfile:
            preferences = json.load(pfile)

        noteExtExist = ExtensionsManager().extensionIsAlreadyExisted(
            preferences, profileExtensionsCheck
        )

        if noteExtExist:
            return
        else:
            return pathToExt

    def spawnBrowser(self) -> str:
        proxy = self.proxy
        proxy_host = ""
        if proxy:
            if proxy.get("mode") is None or proxy.get("mode") == "geolocation":
                proxy["mode"] = "http"
            proxy_host = proxy.get("host")
            proxy = self.formatProxyUrl(proxy)

        tz = self.tz.get("timezone")

        params = [
            self.executablePath,
            "--remote-debugging-port=" + str(self.port),
            "--user-data-dir=" + self.profile_path,
            "--password-store=basic",
            "--tz=" + tz,
            "--gologin-profile=" + self.profile_name,
            "--lang=en-US",
        ]

        chromeExtensions = self.profile.get("chromeExtensions", [])
        if chromeExtensions:
            paths = self.loadExtensions()
            if paths is not None:
                extToParams = "--load-extension=" + paths
                params.append(extToParams)

        if proxy:
            hr_rules = '"MAP * 0.0.0.0 , EXCLUDE %s"' % (proxy_host)
            params.append("--proxy-server=" + proxy)
            params.append("--host-resolver-rules=" + hr_rules)

        for param in self.extra_params:
            params.append(param)

        if sys.platform == "darwin":
            open_browser = subprocess.Popen(params)
            self.pid = open_browser.pid
        else:
            open_browser = subprocess.Popen(params, start_new_session=True)
            self.pid = open_browser.pid

        try_count = 1
        url = str(self.address) + ":" + str(self.port)
        while try_count < 100:
            try:
                requests.get("http://" + url + "/json").content
                break
            except Exception:
                try_count += 1
                time.sleep(1)
        return url

    def start(self) -> str:
        log.debug("start")
        profile_path = self.createStartup()
        if self.spawn_browser is True:
            return self.spawnBrowser()
        return profile_path

    def zipdir(self, path, ziph) -> None:
        for root, dirs, files in os.walk(path):
            for file in files:
                path = os.path.join(root, file)
                if not os.path.exists(path):
                    continue
                if stat.S_ISSOCK(os.stat(path).st_mode):
                    continue
                try:
                    ziph.write(path, path.replace(self.profile_path, ""))
                except Exception:
                    continue

    def waitUntilProfileUsing(self, try_count=0) -> None:
        if try_count > 10:
            return
        time.sleep(1)
        profile_path = self.profile_path
        if os.path.exists(profile_path):
            try:
                os.rename(profile_path, profile_path)
            except OSError:
                log.debug("waiting chrome termination")
                self.waitUntilProfileUsing(try_count + 1)

    def stop(self) -> None:
        for proc in psutil.process_iter(["pid"]):
            if proc.info.get("pid") == self.pid:
                proc.kill()
        self.waitUntilProfileUsing()
        self.sanitizeProfile()
        if self.local is False:
            self.commitProfile()
            os.remove(self.profile_zip_path_upload)
            shutil.rmtree(self.profile_path)
        log.debug("profile stopped")

    def commitProfile(self) -> None:
        log.debug("commitProfile")
        zipf = zipfile.ZipFile(self.profile_zip_path_upload, "w", zipfile.ZIP_DEFLATED)
        self.zipdir(self.profile_path, zipf)
        zipf.close()

        if self.access_token is None:
            raise ValueError("access_token is None")

        headers = {
            "Authorization": "Bearer " + self.access_token,
            "User-Agent": "Selenium-API",
            "Content-Type": "application/zip",
            "browserId": self.profile_id,
        }

        data = requests.put(
            FILES_GATEWAY + "/upload",
            data=open(self.profile_zip_path_upload, "rb"),
            headers=headers,
        )
        log.debug("commitProfile completed %s", data)

    def commitProfileOld(self) -> None:
        zipf = zipfile.ZipFile(self.profile_zip_path_upload, "w", zipfile.ZIP_DEFLATED)
        self.zipdir(self.profile_path, zipf)
        zipf.close()

        # print('profile size=', os.stat(self.profile_zip_path_upload).st_size)

        if self.profile_id is None:
            raise ValueError("profile_id is None")

        signedUrl = requests.get(
            API_URL + "/browser/" + self.profile_id + "/storage-signature",
            headers=self.headers(),
        ).content.decode("utf-8")

        requests.put(signedUrl, data=open(self.profile_zip_path_upload, "rb"))

        # print('commit profile complete')

    def sanitizeProfile(self) -> None:
        if self.cleaningLocalCookies:
            path_to_coockies = os.path.join(
                self.profile_path, "Default", "Network", "Cookies"
            )
            os.remove(path_to_coockies)

        SEPARATOR = os.sep

        remove_dirs = [
            f"Default{SEPARATOR}Cache",
            f"Default{SEPARATOR}Service Worker",
            f"Default{SEPARATOR}Code Cache",
            f"Default{SEPARATOR}GPUCache",
            f"Default{SEPARATOR}Service Worker",
            f"Default{SEPARATOR}Extensions",
            f"Default{SEPARATOR}IndexedDB",
            f"Default{SEPARATOR}GPUCache",
            f"Default{SEPARATOR}DawnCache",
            f"Default{SEPARATOR}fonts_config",
            "GrShaderCache",
            "ShaderCache",
            "biahpgbdmdkfgndcmfiipgcebobojjkp",
            "afalakplffnnnlkncjhbmahjfjhmlkal",
            "cffkpbalmllkdoenhmdmpbkajipdjfam",
            "Dictionaries",
            "enkheaiicpeffbfgjiklngbpkilnbkoi",
            "oofiananboodjbbmdelgdommihjbkfag",
            "SafetyTips",
            "fonts",
        ]

        for d in remove_dirs:
            fpath = os.path.join(self.profile_path, d)
            if os.path.exists(fpath):
                try:
                    shutil.rmtree(fpath)
                except Exception:
                    continue

    def formatProxyUrl(self, proxy: Dict[str, Any]) -> str:
        return (
            proxy.get("mode", "http")
            + "://"
            + proxy.get("host", "")
            + ":"
            + str(proxy.get("port", 80))
        )

    def formatProxyUrlPassword(self, proxy: Dict[str, Any]) -> str:
        mode = "socks5h" if proxy.get("mode") == "socks5" else proxy.get("mode", "http")
        if proxy.get("username", "") == "":
            return (
                mode + "://" + proxy.get("host", "") + ":" + str(proxy.get("port", 80))
            )
        else:
            return (
                mode
                + "://"
                + proxy.get("username", "")
                + ":"
                + proxy.get("password")
                + "@"
                + proxy.get("host", "")
                + ":"
                + str(proxy.get("port", 80))
            )

    def getTimeZone(self) -> Dict[str, Any]:
        proxy = self.proxy
        if proxy:
            proxies = {
                "http": self.formatProxyUrlPassword(proxy),
                "https": self.formatProxyUrlPassword(proxy),
            }
            data = requests.get(GET_TIMEZONE_URL, proxies=proxies)
        else:
            data = requests.get(GET_TIMEZONE_URL)
        return json.loads(data.content.decode("utf-8"))

    def getProfile(self, profile_id: Union[str, None] = None) -> Dict[str, Any]:
        profile_id = self.profile_id if profile_id is None else profile_id

        if profile_id is None:
            raise ValueError("profile_id is None")

        data = json.loads(
            requests.get(
                API_URL + "/browser/" + profile_id, headers=self.headers()
            ).content.decode("utf-8")
        )
        if data.get("statusCode") == 404:
            raise Exception(data.get("error") + ": " + data.get("message"))
        return data

    def downloadProfileZip(self) -> None:
        log.debug("downloadProfileZip")
        s3path = self.profile.get("s3Path", "")
        log.debug("s3path %s", s3path)
        data = ""

        if self.access_token is None:
            raise ValueError("access_token is None")

        headers = {
            "Authorization": "Bearer " + self.access_token,
            "User-Agent": "Selenium-API",
            "browserId": self.profile_id,
        }

        data = requests.get(FILES_GATEWAY + "/download", headers=headers).content

        if len(data) == 0:
            log.debug("data is 0 - creating empty profile")
            self.createEmptyProfile()
        else:
            with open(self.profile_zip_path, "wb") as f:
                f.write(data)

        try:
            log.debug("extracting profile")
            self.extractProfileZip()
        except Exception as e:
            log.exception("ERROR! %s", e)
            self.uploadEmptyProfile()
            self.createEmptyProfile()
            self.extractProfileZip()

        # if not os.path.exists(os.path.join(self.profile_path, 'Default', 'Preferences')):
        #     print('preferences not found - creating fresh profile content')
        #     self.uploadEmptyProfile()
        #     self.createEmptyProfile()
        #     self.extractProfileZip()

    def downloadProfileZipOld(self) -> None:
        log.debug("downloadProfileZip")
        s3path = self.profile.get("s3Path", "")
        data = ""
        if s3path == "":
            # print('downloading profile direct')
            if self.profile_id is None:
                raise ValueError("profile_id is None")
            data = requests.get(
                API_URL + "/browser/" + self.profile_id, headers=self.headers()
            ).content
        else:
            # print('downloading profile s3')
            s3url = PROFILES_URL + s3path.replace(" ", "+")
            data = requests.get(s3url).content

        if len(data) == 0:
            log.debug("data is 0 - creating fresh profile content")
            self.createEmptyProfile()
        else:
            log.debug("data is not 0")
            with open(self.profile_zip_path, "wb") as f:
                f.write(data)

        try:
            log.debug("extracting profile")
            self.extractProfileZip()
        except Exception as e:
            log.exception("exception %s", e)
            self.uploadEmptyProfile()
            self.createEmptyProfile()
            self.extractProfileZip()

        if not os.path.exists(
            os.path.join(self.profile_path, "Default", "Preferences")
        ):
            log.debug("preferences not found - creating fresh profile content")
            self.uploadEmptyProfile()
            self.createEmptyProfile()
            self.extractProfileZip()

    def uploadEmptyProfile(self) -> None:
        log.debug("uploadEmptyProfile")
        upload_profile = open(r"./gologin_zeroprofile.zip", "wb")
        source = requests.get(PROFILES_URL + "zero_profile.zip")
        upload_profile.write(source.content)
        upload_profile.close

    def createEmptyProfile(self) -> None:
        log.debug("createEmptyProfile")
        empty_profile = "../gologin_zeroprofile.zip"

        if not os.path.exists(empty_profile):
            empty_profile = "gologin_zeroprofile.zip"

        if os.path.exists(empty_profile):
            shutil.copy(empty_profile, self.profile_zip_path)

        if not os.path.exists(empty_profile):
            log.debug("downloading zero profile")
            source = requests.get(PROFILES_URL + "zero_profile.zip")
            with open(self.profile_zip_path, "wb") as profile_zip:
                profile_zip.write(source.content)

    def extractProfileZip(self) -> None:
        with zipfile.ZipFile(self.profile_zip_path, "r") as zip_ref:
            zip_ref.extractall(self.profile_path)
        log.debug("profile extracted %s", self.profile_path)
        os.remove(self.profile_zip_path)

    def getGeolocationParams(
        self,
        profileGeolocationParams: Dict[str, Any],
        tzGeolocationParams: Dict[str, Any],
    ) -> Dict[str, Any]:
        if profileGeolocationParams.get("fillBasedOnIp"):
            return {
                "mode": profileGeolocationParams["mode"],
                "latitude": float(tzGeolocationParams["latitude"]),
                "longitude": float(tzGeolocationParams["longitude"]),
                "accuracy": float(tzGeolocationParams["accuracy"]),
            }

        return {
            "mode": profileGeolocationParams["mode"],
            "latitude": profileGeolocationParams["latitude"],
            "longitude": profileGeolocationParams["longitude"],
            "accuracy": profileGeolocationParams["accuracy"],
        }

    def convertPreferences(self, preferences: Dict[str, Any]) -> Dict[str, Any]:
        resolution = preferences.get("navigator", {}).get("resolution", "1920x1080")
        preferences["screenWidth"] = int(resolution.split("x")[0])
        preferences["screenHeight"] = int(resolution.split("x")[1])
        self.preferences = preferences
        self.tz = self.getTimeZone()
        # print('tz=', self.tz)
        tzGeoLocation = {
            "latitude": self.tz.get("ll", [0, 0])[0],
            "longitude": self.tz.get("ll", [0, 0])[1],
            "accuracy": self.tz.get("accuracy", 0),
        }

        preferences["geoLocation"] = self.getGeolocationParams(
            preferences["geolocation"], tzGeoLocation
        )

        preferences["webRtc"] = {
            "mode": "public"
            if preferences.get("webRTC", {}).get("mode") == "alerted"
            else preferences.get("webRTC", {}).get("mode"),
            "publicIP": self.tz["ip"]
            if preferences.get("webRTC", {}).get("fillBasedOnIp")
            else preferences.get("webRTC", {}).get("publicIp"),
            "localIps": preferences.get("webRTC", {}).get("localIps", []),
        }

        preferences["timezone"] = {"id": self.tz.get("timezone")}

        preferences["webgl_noise_value"] = preferences.get("webGL", {}).get("noise")
        preferences["get_client_rects_noise"] = preferences.get("webGL", {}).get(
            "getClientRectsNoise"
        )
        preferences["canvasMode"] = preferences.get("canvas", {}).get("mode")
        preferences["canvasNoise"] = preferences.get("canvas", {}).get("noise")
        if preferences.get("clientRects", {}).get("mode") == "noise":
            preferences["client_rects_noise_enable"] = True
        preferences["audioContextMode"] = preferences.get("audioContext", {}).get(
            "mode"
        )
        preferences["audioContext"] = {
            "enable": preferences.get("audioContextMode") != "off",
            "noiseValue": preferences.get("audioContext").get("noise"),
        }

        preferences["webgl"] = {
            "metadata": {
                "vendor": preferences.get("webGLMetadata", {}).get("vendor"),
                "renderer": preferences.get("webGLMetadata", {}).get("renderer"),
                "mode": preferences.get("webGLMetadata", {}).get("mode") == "mask",
            }
        }

        if preferences.get("navigator", {}).get("userAgent"):
            preferences["userAgent"] = preferences.get("navigator", {}).get("userAgent")

        if preferences.get("navigator", {}).get("doNotTrack"):
            preferences["doNotTrack"] = preferences.get("navigator", {}).get(
                "doNotTrack"
            )

        if preferences.get("navigator", {}).get("hardwareConcurrency"):
            preferences["hardwareConcurrency"] = preferences.get("navigator", {}).get(
                "hardwareConcurrency"
            )

        if preferences.get("navigator", {}).get("language"):
            preferences["languages"] = preferences.get("navigator", {}).get("language")

        if preferences.get("isM1", False):
            preferences["is_m1"] = preferences.get("isM1", False)

        if preferences.get("os") == "android":
            devicePixelRatio = preferences.get("devicePixelRatio")
            deviceScaleFactorCeil = math.ceil(devicePixelRatio or 3.5)
            deviceScaleFactor = devicePixelRatio
            if deviceScaleFactorCeil == devicePixelRatio:
                deviceScaleFactor += 0.00000001

            preferences["mobile"] = {
                "enable": True,
                "width": preferences["screenWidth"],
                "height": preferences["screenHeight"],
                "device_scale_factor": deviceScaleFactor,
            }

        return preferences

    def updatePreferences(self) -> None:
        pref_file = os.path.join(self.profile_path, "Default", "Preferences")
        with open(pref_file, "r", encoding="utf-8") as pfile:
            preferences = json.load(pfile)
        profile = self.profile
        profile["profile_id"] = self.profile_id

        if "navigator" in profile:
            if "deviceMemory" in profile["navigator"]:
                profile["deviceMemory"] = profile["navigator"]["deviceMemory"] * 1024

        if "gologin" in preferences:
            if "navigator" in preferences["gologin"]:
                if "deviceMemory" in preferences["gologin"]["navigator"]:
                    profile["deviceMemory"] = (
                        preferences["gologin"]["navigator"]["deviceMemory"] * 1024
                    )
            if "deviceMemory" in preferences["gologin"]:
                profile["deviceMemory"] = preferences["gologin"]["deviceMemory"]

        proxy = self.profile.get("proxy")
        # print('proxy=', proxy)
        if proxy and (proxy.get("mode") == "gologin" or proxy.get("mode") == "tor"):
            autoProxyServer = profile.get("autoProxyServer")
            splittedAutoProxyServer = autoProxyServer.split("://")
            splittedProxyAddress = splittedAutoProxyServer[1].split(":")
            port = splittedProxyAddress[1]

            proxy = {
                "mode": "http",
                "host": splittedProxyAddress[0],
                "port": port,
                "username": profile.get("autoProxyUsername"),
                "password": profile.get("autoProxyPassword"),
                "timezone": profile.get("autoProxyTimezone", "us"),
            }

            profile["proxy"]["username"] = profile.get("autoProxyUsername")
            profile["proxy"]["password"] = profile.get("autoProxyPassword")

        if not proxy or proxy.get("mode") == "none":
            log.debug("no proxy")
            proxy = None

        if proxy and proxy.get("mode") == "geolocation":
            proxy["mode"] = "http"

        if proxy and proxy.get("mode") is None:
            proxy["mode"] = "http"

        self.proxy = proxy
        self.profile_name = profile.get("name")
        if self.profile_name is None:
            log.debug("empty profile name")
            log.debug("profile= %s", profile)
            exit()

        gologin = self.convertPreferences(profile)
        if self.credentials_enable_service is not None:
            preferences["credentials_enable_service"] = self.credentials_enable_service
        preferences["gologin"] = gologin
        pfile = open(pref_file, "w")
        json.dump(preferences, pfile)

    def createStartup(self) -> str:
        log.debug("createStartup %s", self.profile_path)
        if self.local is False and os.path.exists(self.profile_path):
            try:
                shutil.rmtree(self.profile_path)
            except Exception:
                log.error("error removing profile %s", self.profile_path)
        self.profile = self.getProfile()
        if self.local is False:
            self.downloadProfileZip()
        self.updatePreferences()

        log.debug("writeCookiesFromServer %s", self.writeCookiesFromServer)
        if self.writeCookiesFromServer:
            self.downloadCookies()
            log.debug("cookies downloaded")
        return self.profile_path

    def downloadCookies(self) -> None:
        cookiesManagerInst = CookiesManager(
            profile_id=self.profile_id, tmpdir=self.tmpdir
        )
        try:
            response = requests.get(
                f"{API_URL}/browser/{self.profile_id}/cookies",
                headers=self.headers(),
            )

            cookies = response.json()
            log.debug("COOKIES LENGTH %s", len(cookies))
            cookiesManagerInst.write_cookies_to_file(cookies)
        except Exception as e:
            log.exception("downloadCookies exc %s %s", e, e.__traceback__.tb_lineno)
            raise e

    def get_cookies(self, profile_id: Union[str, None] = None) -> Response:
        profile_id = self.profile_id if profile_id is None else profile_id
        if profile_id is None:
            raise ValueError("profile_id is None")
        response = requests.get(
            f"{API_URL}/browser/{self.profile_id}/cookies", headers=self.headers()
        )
        return response

    def uploadCookies(
        self, cookies: List[Dict[str, Any]], profile_id: Union[str, None] = None
    ) -> Response:
        profile_id = self.profile_id if profile_id is None else profile_id
        if profile_id is None:
            raise ValueError("profile_id is None")
        response = requests.post(
            f"{API_URL}/browser/{self.profile_id}/cookies",
            headers=self.headers(),
            json=cookies,
        )
        return response

    def headers(self) -> Dict[str, str]:
        if self.access_token is None:
            raise ValueError("access_token is None")
        return {
            "Authorization": "Bearer " + self.access_token,
            "User-Agent": "Selenium-API",
        }

    def getRandomFingerprint(self, options: Dict[str, Any]) -> Dict[str, Any]:
        os_type = options.get("os", "lin")
        return json.loads(
            requests.get(
                API_URL + "/browser/fingerprint?os=" + os_type, headers=self.headers()
            ).content.decode("utf-8")
        )

    def profiles(self) -> Dict[str, Any]:
        return json.loads(
            requests.get(
                API_URL + "/browser/v2", headers=self.headers()
            ).content.decode("utf-8")
        )

    def create(self, options: Dict[str, Any] = {}) -> str:
        profile_options = self.getRandomFingerprint(options)
        navigator = options.get("navigator")
        if options.get("navigator"):
            resolution = navigator.get("resolution")
            userAgent = navigator.get("userAgent")
            language = navigator.get("language")
            hardwareConcurrency = navigator.get("hardwareConcurrency")
            deviceMemory = navigator.get("deviceMemory")

            if resolution == "random" or userAgent == "random":
                options.pop("navigator")
            if resolution != "random" and userAgent != "random":
                options.pop("navigator")
            if resolution == "random" and userAgent != "random":
                profile_options["navigator"]["userAgent"] = userAgent
            if userAgent == "random" and resolution != "random":
                profile_options["navigator"]["resolution"] = resolution
            if resolution != "random" and userAgent != "random":
                profile_options["navigator"]["userAgent"] = userAgent
                profile_options["navigator"]["resolution"] = resolution
            if (
                hardwareConcurrency != "random"
                and userAgent != "random"
                and hardwareConcurrency is not None
            ):
                profile_options["navigator"]["hardwareConcurrency"] = (
                    hardwareConcurrency
                )
            if (
                deviceMemory != "random"
                and userAgent != "random"
                and deviceMemory is not None
            ):
                profile_options["navigator"]["deviceMemory"] = deviceMemory

            profile_options["navigator"]["language"] = language

        profile = {
            "name": "default_name",
            "notes": "auto generated",
            "browserType": "chrome",
            "os": "lin",
            "googleServicesEnabled": True,
            "lockEnabled": False,
            "audioContext": {"mode": "noise"},
            "canvas": {"mode": "noise"},
            "webRTC": {
                "mode": "disabled",
                "enabled": False,
                "customize": True,
                "fillBasedOnIp": True,
            },
            "fonts": {"families": profile_options.get("fonts")},
            "navigator": profile_options.get("navigator", {}),
            "profile": json.dumps(profile_options),
        }

        if options.get("webGLMetadata") is None:
            profile["webGLMetadata"] = profile_options["webGLMetadata"]
            profile["webGLMetadata"]["mode"] = "mask"

        if options.get("webglParams") is None:
            profile["webglParams"] = profile_options.get("webglParams")

        if options.get("storage"):
            profile["storage"] = options.get("storage")

        for k, v in options.items():
            profile[k] = v

        response = json.loads(
            requests.post(
                API_URL + "/browser", headers=self.headers(), json=profile
            ).content.decode("utf-8")
        )
        if response.get("statusCode") is not None:
            raise ProtocolException(response)
        return response.get("id")

    def delete(self, profile_id: Union[str, None] = None) -> None:
        profile_id = self.profile_id if profile_id is None else profile_id
        if profile_id is None:
            raise ValueError("profile_id is None")
        requests.delete(API_URL + "/browser/" + profile_id, headers=self.headers())

    def update(self, options: Dict[str, Any]) -> None:
        self.profile_id = options.get("id")
        profile = self.getProfile()
        # print("profile", profile)
        for k, v in options.items():
            profile[k] = v

        if self.profile_id is None:
            raise ValueError("profile_id is None")

        requests.put(
            API_URL + "/browser/" + self.profile_id,
            headers=self.headers(),
            json=profile,
        ).content.decode("utf-8")
        # print("update", resp)
        # return json.loads(resp)

    def waitDebuggingUrl(
        self, delay_s: int, remote_orbita_url: str, try_count: int = 3
    ) -> Dict[str, str]:
        url = remote_orbita_url + "/json/version"
        wsUrl = ""
        try_number = 1
        while wsUrl == "":
            time.sleep(delay_s)
            try:
                response = json.loads(requests.get(url).content)
                wsUrl = response.get("webSocketDebuggerUrl", "")
            except Exception:
                pass
            if try_number >= try_count:
                return {"status": "failure", "wsUrl": wsUrl}
            try_number += 1

        remote_orbita_url_without_protocol = remote_orbita_url.replace("https://", "")
        wsUrl = wsUrl.replace("ws://", "wss://").replace(
            "127.0.0.1", remote_orbita_url_without_protocol
        )

        return {"status": "success", "wsUrl": wsUrl}

    def startRemote(self, delay_s: int = 3) -> Dict[str, str]:
        if self.profile_id is None:
            raise ValueError("profile_id is None")
        responseJson = requests.post(
            API_URL + "/browser/" + self.profile_id + "/web",
            headers=self.headers(),
            json={
                "isNewCloudBrowser": self.is_new_cloud_browser,
                "isHeadless": self.is_cloud_headless,
            },
        ).content.decode("utf-8")
        response = json.loads(responseJson)
        log.debug("profileResponse %s", response)

        remote_orbita_url = "https://" + self.profile_id + ".orbita.gologin.com"
        if self.is_new_cloud_browser:
            if not response["remoteOrbitaUrl"]:
                raise Exception("Couldn' start the remote browser")
            remote_orbita_url = response["remoteOrbitaUrl"]

        return self.waitDebuggingUrl(delay_s, remote_orbita_url=remote_orbita_url)

    def stopRemote(self) -> None:
        if self.profile_id is None:
            raise ValueError("profile_id is None")
        requests.delete(
            API_URL + "/browser/" + self.profile_id + "/web",
            headers=self.headers(),
            params={"isNewCloudBrowser": self.is_new_cloud_browser},
        )

    def clearCookies(self, profile_id: Union[str, None] = None) -> Dict[str, str]:
        self.cleaningLocalCookies = True

        profile_id = self.profile_id if profile_id is None else profile_id
        if profile_id is None:
            raise ValueError("profile_id is None")
        resp = requests.post(
            API_URL + "/browser/" + profile_id + "/cookies?cleanCookies=true",
            headers=self.headers(),
            json=[],
        )

        if resp.status_code == 204:
            return {"status": "success"}
        else:
            return {"status": "failure"}

    def update_proxy(
        self,
        profile_id: Union[str, None] = None,
        proxy: Dict[str, Union[str, int]] = {"mode": "none"},
    ) -> Response:
        profile_id = self.profile_id if profile_id is None else profile_id
        if profile_id is None:
            raise ValueError("profile_id is None")
        response = requests.patch(
            f"{API_URL}/browser/{profile_id}/proxy",
            headers=self.headers(),
            json=proxy,
        )
        return response

    async def normalizePageView(self, page) -> None:
        if self.preferences.get("screenWidth") is None:
            self.profile = self.getProfile()
            self.preferences["screenWidth"] = int(
                self.profile.get("navigator").get("resolution").split("x")[0]
            )
            self.preferences["screenHeight"] = int(
                self.profile.get("navigator").get("resolution").split("x")[1]
            )
        width = self.preferences.get("screenWidth")
        height = self.preferences.get("screenHeight")
        await page.setViewport({"width": width, "height": height})


def getRandomPort() -> int:
    while True:
        port = random.randint(1000, 35000)
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        result = sock.connect_ex(("127.0.0.1", port))
        if result == 0:
            continue
        else:
            return port
        sock.close()
