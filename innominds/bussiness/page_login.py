"""
playwright_login.py

This module defines the ums_login class, which handles browser automation
using Playwright for UI testing purposes. It provides methods to:

- Start and manage a browser instance.
- Open a web page and perform login using provided credentials.
- Reload the current page.
- Close the browser cleanly after tests.

Intended for use in UI automation frameworks where a consistent browser session
and login workflow are required. Can be used in pytest fixtures for test setup
and teardown, and integrates easily with Allure reporting for screenshots and test results.

## Author       : Pooja Swadi
## Email        : pooja.swadi_ext@igel.com
## Created On   : 16-Jan-2026
## Version      : 1.0
"""


from playwright.sync_api import sync_playwright
import time

class ums_login:
    """
    Class to manage browser automation using Playwright for UI testing.

    Attributes:
        url (str): The URL of the web application to open.
        username (str): Username for login.
        password (str): Password for login.
        playwright: Playwright instance.
        browser: Browser instance.
        context: Browser context.
        page: Current page object.
    """

    def __init__(self, url, username, password):
        """
        Initialize the ums_login instance with login credentials and target URL.

        Args:
            url (str): The URL of the web application.
            username (str): Username for login.
            password (str): Password for login.
        """
        self.url = url
        self.username = username
        self.password = password

        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None

    def start_browser(self):
        """
        Start a Playwright Chromium browser instance in non-headless mode.

        - Launches the browser maximized.
        - Creates a new browser context without viewport restrictions.
        - Opens a new page for automation.
        """
        self.playwright = sync_playwright().start()

        self.browser = self.playwright.chromium.launch(
            headless=False,
            args=["--start-maximized"]
        )

        self.context = self.browser.new_context(
            no_viewport=True,
            ignore_https_errors=True
        )

        self.page = self.context.new_page()
        print("Browser started and kept open")

    def login(self):
        """
        Navigate to the target URL and perform login using the provided credentials.

        - Waits for the page to finish loading before interacting.
        - Fills in username and password fields.
        - Clicks the login button.
        - Prints a confirmation message upon successful login.
        """
        self.page.goto(self.url)
        self.page.wait_for_load_state("networkidle")
        time.sleep(2)

        self.page.fill(
            "css=spike-input#username >> input#input-field",
            self.username
        )
        self.page.fill(
            "css=spike-password#password >> input#input-field",
            self.password
        )
        self.page.click(
            "css=spike-button#buttonLogin >> div#button-label"
        )

        print("Login successful!")

    def close_browser(self):
        """
        Close the browser and stop the Playwright instance.

        - Safely closes the browser if it is running.
        - Stops the Playwright instance to free resources.
        """
        if self.browser:
            self.browser.close()
        if self.playwright:
            self.playwright.stop()
        print("Browser closed")

    def reload_page(self):
        """
        Reload the current page in the browser.

        - Raises a RuntimeError if the page is not initialized.
        - Reloads the page and waits for DOM content to load.
        """
        if not self.page:
            raise RuntimeError("[ERROR] Page is not initialized. Call start_browser() first.")
        
        print("[INFO] Reloading browser page...")
        self.page.reload(wait_until="domcontentloaded")  # Correct: reload on Page, not Browser
        time.sleep(2)
        print("[INFO] Page reloaded.")