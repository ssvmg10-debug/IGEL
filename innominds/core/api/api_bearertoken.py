############################################################
## Scenario
## Title        : Capture UMS Authorization Bearer Token
##
## Description :
## This script automates login to the UMS web application
## using Playwright and intercepts the backend
## `applicationinfo` API call to extract the
## Authorization (Bearer) token from the request headers.
##
## The captured token can be reused for authenticated
## API automation and testing without manual login.
##
## Prerequisites:
## - Python 3.9+
## - Playwright installed (`pip install playwright`)
## - Browsers installed (`playwright install`)
## - Network access to UMS server
## - Valid UMS username and password
##
## Scope:
## - Automates UMS login
## - Monitors network responses
## - Captures Authorization header from
##   `/wums-app/main-info/applicationinfo`
## - Prints Bearer token for API usage
##
## Author       : Sai Kumar Arokala, Laxmikanth Ghali
## Email        : laxmikanth.ghali_ext@igel.com
## Created On   : 28-Dec-2026
## Version      : 1.1
############################################################

# core_components/barer_token.py
import requests
import urllib3
import asyncio
from playwright.async_api import async_playwright
import nest_asyncio
from config.read_config import ums_cred, device_cred, root_path
# -------------------------------------------------

# Allow asyncio to run inside a running event loop
nest_asyncio.apply()
# Disable SSL warnings (optional but recommended)
# -------------------------------------------------
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# -------------------------------------------------
# UMS Bearer Token Provider (Browser-based)
# -------------------------------------------------
class UMSAuthTokenProvider:

    def __init__(self, page):
        self.page = page
        self._bearer_token = None

    async def _response_listener(self, response):
        auth = response.request.headers.get("authorization")
        if auth and not self._bearer_token:
            self._bearer_token = auth
            print(f"[INFO] Bearer token captured from URL: {response.url}")

    async def _login_and_capture_token(self, url, username, password, settle_timeout):
        self.page.on("response", self._response_listener)

        await self.page.goto(url, wait_until="domcontentloaded")
        await self.page.wait_for_url("**/auth-service/login**", timeout=15000)

        await self.page.fill('input[name="username"]', username)
        await self.page.fill('input[name="password"]', password)
        await self.page.click('button:has-text("Login")')

        await self.page.wait_for_url("**/webapp/#/**", timeout=30000)
        await self.page.wait_for_timeout(settle_timeout)

        if not self._bearer_token:
            raise RuntimeError("Bearer token not captured")

        print("[INFO] Bearer token captured successfully")
        return self._bearer_token

    @classmethod
    async def get_bearer_token_via_browser(
        cls, url, username, password, settle_timeout=5000, headless=True
    ):
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=headless)
            context = await browser.new_context(ignore_https_errors=True)
            page = await context.new_page()

            provider = cls(page)
            token = await provider._login_and_capture_token(
                url, username, password, settle_timeout
            )

            await browser.close()
            return token

    @classmethod
    def get_bearer_token_sync(cls, url, username, password, settle_timeout=5000, headless=True):
        """
        Loop-safe synchronous wrapper for pytest / sync code.
        """
        coro = cls.get_bearer_token_via_browser(
            url, username, password, settle_timeout, headless
        )
        # Now works even if the event loop is already running
        return asyncio.get_event_loop().run_until_complete(coro)

# -------------------------------------------------
# API Class (uses bearer token)
# -------------------------------------------------
class ApiWithBearerToken:

    def __init__(self, bearer_token):
        self.bearer_token = bearer_token
        self.session = requests.Session()
        self.weburl=ums_cred["weburl"]

    def _assign_or_unassign_profile(self, profile_id, device_id, unassign):
        """
        Shared implementation for assign/detach profile operations.

        Args:
            profile_id: dict with 'id' key
            device_id: dict with 'id' key
            unassign: False to assign, True to detach
        """
        action = "Detach" if unassign else "Assign"
        p_id = profile_id["id"]
        d_id = device_id["id"]

        payload = {
            "assignOrUnassignObjects": [
                {"objectId": p_id, "objectType": "PROFILE", "unassign": unassign}
            ],
            "deviceId": d_id,
            "updateTime": "NOW"
        }

        response = self.session.post(
            (self.weburl + "/wums-app/device-profile/assignOrUnassignObjectToDevice"),
            headers={
                "Authorization": self.bearer_token,
                "Content-Type": "application/json"
            },
            json=payload,
            verify=False
        )

        print(f"[INFO] Status Code: {response.status_code}")
        print(f"[INFO] Response Body: {response.text}")

        if response.status_code != 200:
            raise Exception(f"Profile {action.lower()} failed: {response.text}")

        print(f"[INFO] Profile {action.lower()} request sent successfully")
        return response.json()

    def assign_profile_to_device_now(self, profile_id, device_id):
        """
        Assign a profile to a device using the bearer token.
        profile_id and device_id should be dictionaries with 'id' keys.
        """
        return self._assign_or_unassign_profile(profile_id, device_id, unassign=False)

    def detach_profile_to_device_now(self, profile_id, device_id):
        """
        Detach a profile from a device using the bearer token.
        profile_id and device_id should be dictionaries with 'id' keys.
        """
        return self._assign_or_unassign_profile(profile_id, device_id, unassign=True)



