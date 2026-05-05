###########################################################
# Title        : UMS UI Bearer Token Provider
# Description  : Reusable Playwright-based component that
#                authenticates against the UMS web UI and
#                intercepts network traffic to capture the
#                Authorization Bearer token required for
#                subsequent WUMS API interactions.
#
# Prerequisites:
#   - Python 3.10+
#   - playwright (sync API)
#   - allure-pytest
#   - Valid UMS web credentials
#   - core.logger.get_logger
#
# Author       : Sai Arokala
# Email        : Sai.Arakala_ext@igel.com
# Created On   : Dec-2025
# Version      : 1.2
############################################################



import allure
from playwright.sync_api import Response
from core.utils.logger import get_logger

log = get_logger(__name__)


class UMSAuthTokenService:
    """
    Reusable technical component:
    Login to UMS UI and capture Bearer token
    """

    def __init__(self, page):
        self.page = page
        self._bearer_token = None

    def _response_listener(self, response: Response):
        if "/wums-app/main-info/applicationinfo" not in response.url:
            return

        auth = response.request.headers.get("authorization")
        if auth and not self._bearer_token:
            self._bearer_token = auth
            log.info("Bearer token captured successfully")

    @allure.step("Login to UMS UI and capture Bearer token")
    def get_bearer_token(self, webapp_url, username, password, settle_timeout):
        # ---- RESET STATE ----
        self._bearer_token = None

        # ---- ENSURE SINGLE LISTENER ----
        try:
            self.page.remove_listener("response", self._response_listener)
        except Exception:
            pass

        self.page.on("response", self._response_listener)

        # ---- OPEN WEBAPP (NOT auth-service) ----
        self.page.goto(webapp_url, wait_until="load")

        # ---- LOGIN IF REQUIRED ----
        if self.page.locator('input[name="username"]').is_visible(timeout=5000):
            self.page.locator('input[name="username"]').fill(username)
            self.page.locator('input[name="password"]').fill(password)
            self.page.locator('button:has-text("Login")').click()

        # ---- WAIT FOR REDIRECT BACK TO WEBAPP ----
        self.page.wait_for_url("**/webapp/**", timeout=30000)

        # ---- WAIT FOR AUTH COOKIES TO SET ----
        self.page.wait_for_timeout(3000)

        # ---- FORCE AUTHENTICATED API CALL (CRITICAL) ----
        self.page.evaluate("""
            () => fetch(
                window.location.origin + '/rest/devices?limit=1',
                { credentials: 'include' }
            )
        """)

        # ---- WAIT FOR TOKEN ----
        max_wait = 30000
        poll = 500
        waited = 0

        while not self._bearer_token and waited < max_wait:
            self.page.wait_for_timeout(poll)
            waited += poll

        # ---- FAIL LOUDLY ----
        if not self._bearer_token:
            allure.attach(self.page.url, "Current URL", allure.attachment_type.TEXT)
            allure.attach(
                self.page.context.cookies(),
                "Cookies",
                allure.attachment_type.JSON
            )
            allure.attach(
                self.page.screenshot(),
                "bearer_token_failure",
                allure.attachment_type.PNG
            )
            raise RuntimeError("Bearer token not captured")

        return self._bearer_token


# ==========================================================
# AUTH HELPERS
# ==========================================================

def initial_auth(api, page, ums_cfg, CFG):
    log.info("[AUTH] Initial authentication")

    bearer = UMSAuthTokenService(page).get_bearer_token(
        ums_cfg["webapp_url"],
        ums_cfg["username"],
        ums_cfg["password"],
        CFG["timeouts"]["ui_settle"]
    )

    api.set_bearer(bearer)
    api.login_ums_api(
        ums_cfg["username"],
        ums_cfg["password"]
    )


def refresh_ums_auth(api, page, ums_cfg, CFG):
    log.warning("[AUTH] Refreshing authentication (403 detected)")

    # -------------------------------
    # Refresh WUMS Bearer
    # -------------------------------
    provider = UMSAuthTokenService(page)
    bearer = provider.get_bearer_token(
        webapp_url=ums_cfg["base_url"] + "/webapp",
        username=ums_cfg["username"],
        password=ums_cfg["password"],
        settle_timeout=30
    )
    api.set_bearer(bearer)

    # -------------------------------
    # Refresh UMS session ONLY if missing
    # -------------------------------
    if not api.session_id:
        log.info("[AUTH] No UMS session, logging in")
        api.login_ums_api(
            ums_cfg["username"],
            ums_cfg["password"]
        )
    else:
        log.info("[AUTH] UMS session already present, skipping login")
