import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class APIClient:
    """
    Thin HTTP wrapper for UMS / WUMS APIs.
    """

    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self.session.verify = False  # internal certs

    def get(self, path: str, **kwargs):
        return self.session.get(f"{self.base_url}{path}", **kwargs)

    def post(self, path: str, **kwargs):
        return self.session.post(f"{self.base_url}{path}", **kwargs)

    def put(self, path: str, **kwargs):
        return self.session.put(f"{self.base_url}{path}", **kwargs)

    def patch(self, path: str, **kwargs):
        return self.session.patch(f"{self.base_url}{path}", **kwargs)