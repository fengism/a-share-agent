import json
from typing import Any

import requests


def request(method: str, url: str, *, params: dict | None = None, data: Any = None, json_body: Any = None, headers: dict | None = None, timeout: int | float = 10) -> requests.Response:
    response = requests.request(
        method,
        url,
        params=params,
        data=data,
        json=json_body,
        headers=headers,
        timeout=timeout,
    )
    response.raise_for_status()
    return response


def get(url: str, **kwargs) -> requests.Response:
    return request("GET", url, **kwargs)


def post(url: str, **kwargs) -> requests.Response:
    return request("POST", url, **kwargs)


def parse_text_json(response: requests.Response) -> Any:
    return json.loads(response.text.strip())
