import logging

import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

log = logging.getLogger(__name__)


class APIClient:
    """
    Thin HTTP wrapper for UMS / WUMS APIs.
    """

    def __init__(self, base_url: str, raise_on_error: bool = False):
        self.base_url = base_url.rstrip("/")
        self.raise_on_error = raise_on_error
        self.session = requests.Session()
        self.session.verify = False  # internal certs

    def _check_response(self, resp: requests.Response) -> requests.Response:
        if self.raise_on_error and not resp.ok:
            log.error(
                "%s %s -> HTTP %s: %s",
                resp.request.method, resp.request.url,
                resp.status_code, resp.text[:200],
            )
            resp.raise_for_status()
        return resp

    def get(self, path: str, **kwargs):
        return self._check_response(
            self.session.get(f"{self.base_url}{path}", **kwargs)
        )

    def post(self, path: str, **kwargs):
        return self._check_response(
            self.session.post(f"{self.base_url}{path}", **kwargs)
        )

    def put(self, path: str, **kwargs):
        return self._check_response(
            self.session.put(f"{self.base_url}{path}", **kwargs)
        )

    def patch(self, path: str, **kwargs):
        return self._check_response(
            self.session.patch(f"{self.base_url}{path}", **kwargs)
        )

    def delete(self, path: str, **kwargs):
        return self._check_response(
            self.session.delete(f"{self.base_url}{path}", **kwargs)
        )