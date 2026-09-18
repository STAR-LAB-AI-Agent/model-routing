import argparse
import json
import sys
from pathlib import Path
from .config import RouterError
from .service import RouterService


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stdin.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(description="AI 模型智能路由 · Skill + Script JSON 接口")
    p.add_argument("action", choices=("plan", "run", "stats", "doctor"))
    p.add_argument("--prompt", help="直接传入自然语言；复杂文本建议使用 stdin JSON")
    p.add_argument("--mode", choices=("live",), default="live")
    p.add_argument("--preference", choices=("balanced", "cost", "quality"), default="balanced")
    p.add_argument("--max-tokens", type=int, default=2048)
    p.add_argument("--json-stdin", action="store_true", help="从标准输入读取单个 JSON 对象")
    p.add_argument("--confirm-live", action="store_true")
    p.add_argument("--no-cache", action="store_true")
    args = p.parse_args()
    try:
        svc = RouterService()
        if args.action == "doctor":
            from importlib.metadata import version
            result = {"ok": True, "python": sys.version.split()[0], "litellm": version("litellm"),
                      "storage_writable": svc.db.exists(), "default_mode": "live"}
            from .settings import SettingsStore
            result["settings"] = SettingsStore().status()
        elif args.action == "stats":
            result = svc.stats(args.mode)
        else:
            if args.json_stdin:
                raw = sys.stdin.read(120001)
                if len(raw) > 120000:
                    raise RouterError("INPUT_TOO_LONG", "JSON 输入过长。")
                req = json.loads(raw)
            else:
                req = {"prompt": args.prompt, "mode": args.mode, "preference": args.preference,
                       "max_tokens": args.max_tokens, "confirm_live": args.confirm_live, "use_cache": not args.no_cache}
            result = svc.preview(req) if args.action == "plan" else svc.run(req)
    except RouterError as exc:
        result = {"ok": False, "error": {"code": exc.code, "message": exc.message}}
    except (json.JSONDecodeError, UnicodeError):
        result = {"ok": False, "error": {"code": "INVALID_JSON", "message": "请输入 UTF-8 编码的有效 JSON 对象。"}}
    except Exception:
        result = {"ok": False, "error": {"code": "INTERNAL_ERROR", "message": "运行失败，请运行 doctor 并检查依赖及目录写入权限。"}}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1
