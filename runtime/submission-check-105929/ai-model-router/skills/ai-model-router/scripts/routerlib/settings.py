"""Local credentials: Windows DPAPI ciphertext bound to the current user."""
import base64
import ctypes
from ctypes import wintypes
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
import threading
from urllib.request import Request, build_opener, HTTPRedirectHandler
from .config import API_BASE, PROJECT_ROOT, RouterError


def _dpapi(raw, decrypt=False):
    class Blob(ctypes.Structure):
        _fields_ = [("size", wintypes.DWORD), ("data", ctypes.POINTER(ctypes.c_ubyte))]
    buf = ctypes.create_string_buffer(raw)
    src = Blob(len(raw), ctypes.cast(buf, ctypes.POINTER(ctypes.c_ubyte)))
    dst = Blob()
    crypt = ctypes.WinDLL("crypt32", use_last_error=True)
    fn = crypt.CryptUnprotectData if decrypt else crypt.CryptProtectData
    fn.argtypes = [ctypes.POINTER(Blob), ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(Blob)]
    fn.restype = wintypes.BOOL
    if not fn(ctypes.byref(src), None, None, None, None, 1, ctypes.byref(dst)):
        raise RouterError("KEY_STORAGE_ERROR", "无法读取本机密钥，请在当前 Windows 账户重新配置。")
    try:
        return ctypes.string_at(dst.data, dst.size)
    finally:
        kernel = ctypes.WinDLL("kernel32")
        kernel.LocalFree.argtypes = [ctypes.c_void_p]
        kernel.LocalFree.restype = ctypes.c_void_p
        kernel.LocalFree(dst.data)


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


class SettingsStore:
    def __init__(self, path=None):
        self.path = Path(path or os.environ.get("ROUTER_SETTINGS_FILE", str(PROJECT_ROOT / "runtime/settings.json")))
        self.lock = threading.RLock()

    def key(self):
        with self.lock:
            if self.path.exists():
                try:
                    entry = json.loads(self.path.read_text(encoding="utf-8"))
                    if entry["storage"] == "windows-dpapi":
                        return _dpapi(base64.b64decode(entry["secret"]), True).decode()
                    if os.name != "nt" and entry["storage"] == "file-0600":
                        return entry["secret"]
                    raise ValueError()
                except RouterError:
                    raise
                except Exception:
                    raise RouterError("KEY_STORAGE_ERROR", "本机密钥配置损坏，请重新保存。") from None
            return os.environ.get("DEEPSEEK_API_KEY", os.environ.get("ROUTER_API_KEY", "")).strip()

    def revision(self):
        return hashlib.sha256(self.key().encode()).hexdigest()

    def status(self):
        return {"ok": True, "configured": bool(self.key()), "api_base": API_BASE,
                "source": "local" if self.path.exists() else "environment",
                "storage": "Windows 用户加密" if os.name == "nt" else "本地文件（权限 0600）"}

    def save(self, payload):
        if not isinstance(payload, dict) or set(payload) != {"api_key"}:
            raise RouterError("INVALID_SETTINGS", "只接受 api_key 字段。")
        key = payload["api_key"]
        if not isinstance(key, str) or not re.fullmatch(r"sk-[A-Za-z0-9_-]{16,200}", key.strip()):
            raise RouterError("INVALID_KEY", "请输入有效的 DeepSeek API Key。")
        key = key.strip()
        entry = {"storage": "windows-dpapi" if os.name == "nt" else "file-0600",
                 "secret": base64.b64encode(_dpapi(key.encode())).decode() if os.name == "nt" else key}
        with self.lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            fd, name = tempfile.mkstemp(dir=self.path.parent, prefix=".settings-")
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as out:
                    json.dump(entry, out)
                os.chmod(name, 0o600)
                os.replace(name, self.path)
            finally:
                if os.path.exists(name): os.unlink(name)
        return self.status()

    def clear(self):
        with self.lock:
            self.path.unlink(missing_ok=True)
        return self.status()

    def check(self):
        key = self.key()
        if not key:
            raise RouterError("API_KEY_MISSING", "请先在 API 配置中保存密钥。")
        request = Request(API_BASE + "/models", headers={"Authorization": "Bearer " + key})
        try:
            with build_opener(NoRedirect()).open(request, timeout=20) as response:
                data = json.load(response)
            models = sorted(m["id"] for m in data["data"] if isinstance(m.get("id"), str))
            missing = sorted({"deepseek-flash", "deepseek-v4-pro"} - set(models))
            return {"ok": True, "connected": True, "models": models, "missing_required_models": missing,
                    "note": "连接测试只读取模型列表，不发起文本生成。"}
        except Exception as exc:
            code = getattr(exc, "code", None)
            raise RouterError("AUTH_FAILED" if code == 401 else "CONNECTION_FAILED",
                              "连接失败，请检查密钥、网络与账户权限；服务原始错误已隐藏。") from None
