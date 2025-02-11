#
# MIT License
#
# Copyright (c) 2020 Airbyte
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#


import json
from typing import Any, Iterable, Mapping, Optional
from unittest.mock import ANY

import pytest
import requests
from airbyte_cdk.models import SyncMode
from airbyte_cdk.sources.streams.http import HttpStream
from airbyte_cdk.sources.streams.http.exceptions import RequestBodyException, UserDefinedBackoffException


class StubBasicReadHttpStream(HttpStream):
    url_base = "https://test_base_url.com"
    primary_key = ""

    def __init__(self):
        super().__init__()
        self.resp_counter = 1

    def next_page_token(self, response: requests.Response) -> Optional[Mapping[str, Any]]:
        return None

    def path(
        self, stream_state: Mapping[str, Any] = None, stream_slice: Mapping[str, Any] = None, next_page_token: Mapping[str, Any] = None
    ) -> str:
        return ""

    def parse_response(
        self,
        response: requests.Response,
        stream_state: Mapping[str, Any],
        stream_slice: Mapping[str, Any] = None,
        next_page_token: Mapping[str, Any] = None,
    ) -> Iterable[Mapping]:
        stubResp = {"data": self.resp_counter}
        self.resp_counter += 1
        yield stubResp


def test_request_kwargs_used(mocker, requests_mock):
    stream = StubBasicReadHttpStream()
    request_kwargs = {"cert": None, "proxies": "google.com"}
    mocker.patch.object(stream, "request_kwargs", return_value=request_kwargs)
    mocker.patch.object(stream._session, "send", wraps=stream._session.send)
    requests_mock.register_uri("GET", stream.url_base)

    list(stream.read_records(sync_mode=SyncMode.full_refresh))

    stream._session.send.assert_any_call(ANY, **request_kwargs)


def test_stub_basic_read_http_stream_read_records(mocker):
    stream = StubBasicReadHttpStream()
    blank_response = {}  # Send a blank response is fine as we ignore the response in `parse_response anyway.
    mocker.patch.object(StubBasicReadHttpStream, "_send_request", return_value=blank_response)

    records = list(stream.read_records(SyncMode.full_refresh))

    assert [{"data": 1}] == records


class StubNextPageTokenHttpStream(StubBasicReadHttpStream):
    current_page = 0

    def __init__(self, pages: int = 5):
        super().__init__()
        self._pages = pages

    def next_page_token(self, response: requests.Response) -> Optional[Mapping[str, Any]]:
        while self.current_page < self._pages:
            page_token = {"page": self.current_page}
            self.current_page += 1
            return page_token
        return None


def test_next_page_token_is_input_to_other_methods(mocker):
    """Validates that the return value from next_page_token is passed into other methods that need it like request_params, headers, body, etc.."""
    pages = 5
    stream = StubNextPageTokenHttpStream(pages=pages)
    blank_response = {}  # Send a blank response is fine as we ignore the response in `parse_response anyway.
    mocker.patch.object(StubNextPageTokenHttpStream, "_send_request", return_value=blank_response)

    methods = ["request_params", "request_headers", "request_body_json"]
    for method in methods:
        # Wrap all methods we're interested in testing with mocked objects so we can later spy on their input args and verify they were what we expect
        mocker.patch.object(stream, method, wraps=getattr(stream, method))

    records = list(stream.read_records(SyncMode.full_refresh))

    # Since we have 5 pages, we expect 5 tokens which are {"page":1}, {"page":2}, etc...
    expected_next_page_tokens = [{"page": i} for i in range(pages)]
    for method in methods:
        # First assert that they were called with no next_page_token. This is the first call in the pagination loop.
        getattr(stream, method).assert_any_call(next_page_token=None, stream_slice=None, stream_state={})
        for token in expected_next_page_tokens:
            # Then verify that each method
            getattr(stream, method).assert_any_call(next_page_token=token, stream_slice=None, stream_state={})

    expected = [{"data": 1}, {"data": 2}, {"data": 3}, {"data": 4}, {"data": 5}, {"data": 6}]

    assert expected == records


class StubBadUrlHttpStream(StubBasicReadHttpStream):
    url_base = "bad_url"


def test_stub_bad_url_http_stream_read_records(mocker):
    stream = StubBadUrlHttpStream()

    with pytest.raises(requests.exceptions.RequestException):
        list(stream.read_records(SyncMode.full_refresh))


class StubCustomBackoffHttpStream(StubBasicReadHttpStream):
    def backoff_time(self, response: requests.Response) -> Optional[float]:
        return 0.5


def test_stub_custom_backoff_http_stream(mocker):
    mocker.patch("time.sleep", lambda x: None)
    stream = StubCustomBackoffHttpStream()
    req = requests.Response()
    req.status_code = 429

    mocker.patch.object(requests.Session, "send", return_value=req)

    with pytest.raises(UserDefinedBackoffException):
        list(stream.read_records(SyncMode.full_refresh))

    # TODO(davin): Figure out how to assert calls.


class PostHttpStream(StubBasicReadHttpStream):
    http_method = "POST"

    def parse_response(self, response: requests.Response, **kwargs) -> Iterable[Mapping]:
        """Returns response data as is"""
        yield response.json()


class TestRequestBody:
    """Suite of different tests for request bodies"""

    json_body = {"key": "value"}
    data_body = "key:value"
    form_body = {"key1": "value1", "key2": 1234}
    urlencoded_form_body = "key1=value1&key2=1234"

    def request2response(self, request, context):
        return json.dumps({"body": request.text, "content_type": request.headers.get("Content-Type")})

    def test_json_body(self, mocker, requests_mock):

        stream = PostHttpStream()
        mocker.patch.object(stream, "request_body_json", return_value=self.json_body)

        requests_mock.register_uri("POST", stream.url_base, text=self.request2response)
        response = list(stream.read_records(sync_mode=SyncMode.full_refresh))[0]

        assert response["content_type"] == "application/json"
        assert json.loads(response["body"]) == self.json_body

    def test_text_body(self, mocker, requests_mock):

        stream = PostHttpStream()
        mocker.patch.object(stream, "request_body_data", return_value=self.data_body)

        requests_mock.register_uri("POST", stream.url_base, text=self.request2response)
        response = list(stream.read_records(sync_mode=SyncMode.full_refresh))[0]

        assert response["content_type"] is None
        assert response["body"] == self.data_body

    def test_form_body(self, mocker, requests_mock):

        stream = PostHttpStream()
        mocker.patch.object(stream, "request_body_data", return_value=self.form_body)

        requests_mock.register_uri("POST", stream.url_base, text=self.request2response)
        response = list(stream.read_records(sync_mode=SyncMode.full_refresh))[0]

        assert response["content_type"] == "application/x-www-form-urlencoded"
        assert response["body"] == self.urlencoded_form_body

    def test_text_json_body(self, mocker, requests_mock):
        """checks a exception if both functions were overridden"""
        stream = PostHttpStream()
        mocker.patch.object(stream, "request_body_data", return_value=self.data_body)
        mocker.patch.object(stream, "request_body_json", return_value=self.json_body)
        requests_mock.register_uri("POST", stream.url_base, text=self.request2response)
        with pytest.raises(RequestBodyException):
            list(stream.read_records(sync_mode=SyncMode.full_refresh))

    def test_body_for_all_methods(self, mocker, requests_mock):
        """Stream must send a body for POST/PATCH/PUT methods only"""
        stream = PostHttpStream()
        methods = {
            "POST": True,
            "PUT": True,
            "PATCH": True,
            "GET": False,
            "DELETE": False,
            "OPTIONS": False,
        }
        for method, with_body in methods.items():
            stream.http_method = method
            mocker.patch.object(stream, "request_body_data", return_value=self.data_body)
            requests_mock.register_uri(method, stream.url_base, text=self.request2response)
            response = list(stream.read_records(sync_mode=SyncMode.full_refresh))[0]
            if with_body:
                assert response["body"] == self.data_body
            else:
                assert response["body"] is None
