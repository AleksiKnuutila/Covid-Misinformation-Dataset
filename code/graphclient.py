import requests
import json
from tenacity import Retrying, retry_if_exception_type, wait_fixed
import urllib3
from loguru import logger


class RateLimitError(Exception):
    pass


class GraphClient:
    def __init__(self, tokens):
        self.tokens = tokens
        self.current_token = 0

    def _get_token(self):
        return self.tokens[self.current_token]

    def _switch_token(self, retry_state):
        self.current_token += 1
        self.current_token = self.current_token % len(self.tokens)

    def get_engagement(self, url):
        r = Retrying(
            retry=retry_if_exception_type(
                (
                    RateLimitError,
                    OSError,
                    requests.exceptions.ConnectionError,
                    urllib3.exceptions.MaxRetryError,
                    urllib3.exceptions.NewConnectionError,
                )
            ),
            before_sleep=self._switch_token,
            wait=wait_fixed(5),
        )
        return r.call(self.api_call, url)

    def api_call(self, url):
        URL = "https://graph.facebook.com/v7.0/"
        parameters = {
            "fields": "engagement",
            "access_token": self._get_token(),
            "id": url,
        }
        resp = requests.get(URL, params=parameters)
        try:
            data = json.loads(resp.text)
        except:
            return None
        if (
            "error" in data
            and "Application request limit reached" in data["error"]["message"]
        ):
            raise RateLimitError
        elif "error" in data:
            return None
        return {**{"url": data["id"]}, **data["engagement"]}
