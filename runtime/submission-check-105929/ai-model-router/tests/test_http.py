import json
import threading
from urllib.request import Request, urlopen
from urllib.error import HTTPError
import pytest
from app import make_server
from routerlib.service import RouterService
from test_router import FakeProvider
from routerlib.settings import SettingsStore


@pytest.fixture
def server(tmp_path):
    server = make_server(0, RouterService(tmp_path, FakeProvider()), SettingsStore(tmp_path/"settings.json"))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()
    server.server_close()
    thread.join()


def test_http_run(server):
    req = Request(server+"/api/run", json.dumps({"prompt":"你好","confirm_live":True}).encode(), {"Content-Type":"application/json"})
    with urlopen(req) as response:
        assert json.load(response)["ok"]
    with urlopen(server+"/") as response:
        assert b"RouteLab" in response.read()
        assert "frame-ancestors 'none'" in response.headers["Content-Security-Policy"]


def test_http_origin_and_path(server):
    req = Request(server+"/api/run", b'{}', {"Content-Type":"application/json", "Origin":"https://evil.invalid"})
    with pytest.raises(HTTPError) as exc: urlopen(req)
    assert exc.value.code == 403
    with pytest.raises(HTTPError) as exc: urlopen(server+"/.env")
    assert exc.value.code == 404


def test_http_invalid_json(server):
    req = Request(server+"/api/run", b'not-json', {"Content-Type":"application/json"})
    with pytest.raises(HTTPError) as exc: urlopen(req)
    assert json.load(exc.value)["error"]["code"] == "INVALID_JSON"


def test_settings_dynamic_and_redacted(server):
    key = "sk-unit-test-http-1234567890"
    def post(path, body):
        req = Request(server+path, json.dumps(body).encode(), {"Content-Type":"application/json"})
        with urlopen(req) as response: return json.load(response)
    result = post("/api/settings", {"api_key":key})
    assert result["configured"] and key not in json.dumps(result)
    with urlopen(server+"/api/settings") as response:
        assert key not in response.read().decode()
    with pytest.raises(HTTPError) as exc:
        post("/api/settings", {"api_key":key,"api_base":"https://evil.invalid"})
    assert exc.value.code == 400
    req = Request(server+"/api/settings", b'{}', {"Content-Type":"application/json","Origin":"https://evil.invalid"})
    with pytest.raises(HTTPError) as exc: urlopen(req)
    assert exc.value.code == 403
    post("/api/settings/clear", {})
