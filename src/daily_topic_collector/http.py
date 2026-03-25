from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


@dataclass(frozen=True)
class HttpResponse:
    status: int
    text: str

    def json_value(self) -> object:
        return json.loads(self.text)

    def json_dict(self) -> dict[str, object]:
        data = self.json_value()
        if isinstance(data, dict):
            return data
        raise ValueError("Expected a JSON object response")


class HttpClient:
    def get(self, url: str, headers: Mapping[str, str] | None = None, params: Mapping[str, str] | None = None) -> HttpResponse:
        target = url
        if params:
            target = f"{url}?{urlencode(params)}"
        request = Request(target, headers=dict(headers or {}), method="GET")
        return self._send(request)

    def post_json(self, url: str, payload: Mapping[str, object], headers: Mapping[str, str] | None = None) -> HttpResponse:
        body = json.dumps(payload).encode("utf-8")
        merged_headers = {"Content-Type": "application/json", **dict(headers or {})}
        request = Request(url, data=body, headers=merged_headers, method="POST")
        return self._send(request)

    def post_form(self, url: str, form: Mapping[str, str], headers: Mapping[str, str] | None = None) -> HttpResponse:
        body = urlencode(form).encode("utf-8")
        merged_headers = {"Content-Type": "application/x-www-form-urlencoded", **dict(headers or {})}
        request = Request(url, data=body, headers=merged_headers, method="POST")
        return self._send(request)

    def _send(self, request: Request) -> HttpResponse:
        try:
            with urlopen(request, timeout=30) as response:
                return HttpResponse(status=response.status, text=response.read().decode("utf-8"))
        except HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"HTTP {exc.code} for {request.full_url}: {body}") from exc
        except URLError as exc:
            raise RuntimeError(f"Request failed for {request.full_url}: {exc}") from exc
