import httpx
import pytest

from common.http import FetchError, get_json


def make_client(responses):
    seq = iter(responses)

    def handler(request):
        item = next(seq)
        if isinstance(item, Exception):
            raise item
        return item

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_retries_on_5xx_and_transport_error():
    sleeps = []
    client = make_client(
        [
            httpx.Response(503),
            httpx.ConnectError("reset"),
            httpx.Response(429),
            httpx.Response(200, json={"ok": 1}),
        ]
    )
    assert get_json(client, "https://x/api", sleep=sleeps.append, backoff=1) == {"ok": 1}
    assert sleeps == [1, 2, 4]


def test_gives_up_after_retries():
    client = make_client([httpx.Response(500)] * 3)
    with pytest.raises(FetchError, match="3 próbach"):
        get_json(client, "https://x/api", retries=2, sleep=lambda s: None)


def test_client_error_not_retried():
    client = make_client([httpx.Response(400)])
    with pytest.raises(FetchError, match="HTTP 400"):
        get_json(client, "https://x/api", sleep=lambda s: pytest.fail("nie powinno ponawiać"))
