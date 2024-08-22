import logging
import sqlite3
import base64
from typing import Any, List, Dict, Tuple
import datetime
import os
from os import access, F_OK

MAX_SQLITE_VARIABLES = 1

SAME_SITE = {
    -1: "unspecified",
    0: "no_restriction",
    1: "lax",
    2: "strict",
}

log = logging.getLogger(__name__)
log.addHandler(logging.NullHandler())


class CookiesManager:
    def __init__(self, *args, **kwargs):
        self.profile_id = kwargs.get("profile_id")
        self.tmpdir = kwargs.get("tmpdir")

    def get_db(self):
        database = self.get_cookies_file_path()
        log.debug("FILEPATH %s", database)
        return sqlite3.connect(database=database)

    def get_chunked_insert_values(
        self, cookies_arr: List[dict]
    ) -> List[Tuple[str, List]]:
        today_unix = int(datetime.datetime.now().timestamp())
        chunked_cookies_arr = [
            cookies_arr[i : i + MAX_SQLITE_VARIABLES]
            for i in range(0, len(cookies_arr), MAX_SQLITE_VARIABLES)
        ]

        # for cookies in chunked_cookies_arr:
        # print('COOKIES::::::', cookies)
        result = []

        for cookies in chunked_cookies_arr:
            query_placeholders = ", ".join(
                ["(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"]
                * len(cookies)
            )
            query = f"insert or replace into cookies (creation_utc, host_key, top_frame_site_key, name, value, encrypted_value, path, expires_utc, is_secure, is_httponly, last_access_utc, has_expires, is_persistent, priority, samesite, source_scheme, source_port, is_same_party, last_update_utc) values {query_placeholders}"

            query_params = []
            for cookie in cookies:
                creation_date = cookie.get("creationDate", today_unix)
                expiration_date = (
                    0
                    if cookie.get("session", False)
                    else cookie.get("expirationDate", 0)
                )
                encrypted_value = cookie["value"]
                samesite = next(
                    key
                    for key, value in SAME_SITE.items()
                    if value == cookie.get("sameSite", "-1")
                )
                is_secure = (
                    1
                    if cookie["name"].startswith("__Host-")
                    or cookie["name"].startswith("__Secure-")
                    else int(cookie.get("secure", 0))
                )
                source_scheme = 2 if is_secure == 1 else 1
                source_port = 443 if is_secure == 1 else 80
                is_persistent = (
                    0 if cookie.get("session") else 1 if expiration_date != 0 else 0
                )

                if (
                    cookie.get("domain") == ".mail.google.com"
                    and cookie["name"] == "COMPASS"
                ):
                    expiration_date = 0
                    is_persistent = 0

                query_params.append(
                    (
                        creation_date,
                        cookie.get("domain", ""),
                        "",  # top_frame_site_key
                        cookie["name"],
                        "",  # value
                        encrypted_value,
                        cookie.get("path", ""),
                        expiration_date,
                        is_secure,
                        int(cookie.get("httpOnly", 0)),
                        0,  # last_access_utc
                        0 if expiration_date == 0 else 1,  # has_expires
                        is_persistent,
                        1,  # default priority value (https://github.com/chromium/chromium/blob/main/net/cookies/cookie_constants.h)
                        samesite,
                        source_scheme,
                        source_port,
                        0,  # is_same_party
                        0,  # last_update_utc
                    )
                )

            result.append((query, query_params))

        return result

    def load_cookies_from_file(self) -> List[Dict[str, Any]]:
        db = None
        cookies = []

        try:
            db = self.get_db()
            cookies_rows = db.execute("select * from cookies")
            cookies_rows = cookies_rows.fetchall()
            for row in cookies_rows:
                (
                    creation_utc,
                    host_key,
                    top_frame_site_key,
                    name,
                    value,
                    encrypted_value,
                    path,
                    expires_utc,
                    is_secure,
                    is_httponly,
                    last_access_utc,
                    has_expires,
                    is_persistent,
                    priority,
                    samesite,
                    source_scheme,
                    source_port,
                    is_same_party,
                    last_update_utc,
                    source_type,
                    has_cross_site_ancestor,
                ) = row
                cookies.append(
                    {
                        "url": self.build_cookie_url(host_key, is_secure, path),
                        "domain": host_key,
                        "name": name,
                        "value": encrypted_value,
                        "path": path,
                        "sameSite": SAME_SITE[samesite],
                        "secure": bool(is_secure),
                        "httpOnly": bool(is_httponly),
                        "hostOnly": not host_key.startswith("."),
                        "session": not is_persistent,
                        "expirationDate": self.ldap_to_unix(expires_utc),
                        "creationDate": self.ldap_to_unix(creation_utc),
                    }
                )
        except Exception as error:
            log.exception("load_cookies_from_file %s", error)
            raise error
        finally:
            if db:
                db.close()

        return cookies

    def unix_to_ldap(self, unixtime: int) -> int:
        if unixtime == 0:
            return unixtime

        win32filetime = datetime.datetime.utcfromtimestamp(0)
        win32filetime_utc = (
            win32filetime - datetime.datetime(1601, 1, 1)
        ).total_seconds()

        sum_ = unixtime - win32filetime_utc

        return int(sum_ * 1000000)

    def ldap_to_unix(self, ldap):
        ldap_str = str(int(ldap))  # Convert to integer first to avoid decimals
        ldap_length = len(ldap_str)

        if ldap == 0 or ldap_length > 18:
            return ldap

        _ldap = ldap
        if ldap_length < 18:
            _ldap = int(
                ldap_str + "0" * (18 - ldap_length)
            )  # Padding zeros to the integer part

        # Create a datetime object for January 1, 1601
        win32_epoch = datetime.datetime(1601, 1, 1, tzinfo=datetime.timezone.utc)
        # Convert this to a Unix timestamp in milliseconds
        win32filetime_epoch = int(win32_epoch.timestamp() * 1000)

        return (_ldap / 10000 + win32filetime_epoch) / 1000

    def build_cookie_url(self, domain: str, secure: bool, path: str) -> str:
        domain_without_dot = domain[1:] if domain.startswith(".") else domain
        protocol = "https://" if secure else "http://"

        return protocol + domain_without_dot + path

    def chunk(self, arr: List, chunk_size: int = 1) -> List[List]:
        if chunk_size <= 0:
            return []

        return [arr[i : i + chunk_size] for i in range(0, len(arr), chunk_size)]

    def get_cookies_file_path(self) -> str:
        if self.tmpdir is None:
            raise ValueError("tmpdir must be specified")

        base_cookies_file_path = os.path.join(
            self.tmpdir, f"gologin_{self.profile_id}", "Default", "Cookies"
        )
        bypass_cookies_file_path = os.path.join(
            self.tmpdir, f"gologin_{self.profile_id}", "Default", "Network", "Cookies"
        )

        if access(base_cookies_file_path, F_OK):
            return base_cookies_file_path

        if access(bypass_cookies_file_path, F_OK):
            return bypass_cookies_file_path

        return base_cookies_file_path

    def write_cookies_to_file(self, cookies):
        log.debug("write_cookies_to_file")
        result_cookies = [
            {"value": base64.b64encode(cookie["value"].encode()), **cookie}
            for cookie in cookies  # plain
            # {
            #     **cookie,
            #     "value": base64.b64encode(bytearray(cookie["value"]["data"])).decode('utf-8')
            # } for cookie in cookies # encrypted
        ]

        db = self.get_db()
        cursor = db.cursor()

        try:
            if result_cookies:
                query = "delete from cookies"
                cursor.execute(query)
                db.commit()

                chunk_insert_values = self.get_chunked_insert_values(result_cookies)
                # print('chunk_insert_values', chunk_insert_values)

                for query, query_params in chunk_insert_values:
                    for params in query_params:
                        cursor.execute(query, params)
                        # res = cursor.execute(query, params)
                        # print('params', params)
                        # print('res', res.rowcount, res.lastrowid, res.fetchall())
                db.commit()
            else:
                query = "delete from cookies"
                cursor.execute(query)
                db.commit()
            db.close()
            self.load_cookies_from_file()
            db.close()
        except Exception as error:
            log.exception("write_cookies_to_file exception: %s", error)
            raise error
        finally:
            if db:
                db.close()
