"""Launch nanobot with the saved key injected into a child environment, never argv."""
import argparse
import hashlib
import os
from pathlib import Path
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"skills/ai-model-router/scripts"))
from routerlib.settings import SettingsStore
from routerlib.config import RouterError

if __name__=="__main__":
    p=argparse.ArgumentParser(description="Start real nanobot orchestration; uses paid DeepSeek API")
    p.add_argument("--message",required=True)
    args=p.parse_args()
    try:
        key=SettingsStore().key()
        if not key:raise RouterError("API_KEY_MISSING","请先在网页 API 配置保存密钥。")
        env={**os.environ,"NANOBOT_PROVIDERS__CUSTOM__API_KEY":key,"PYTHONUTF8":"1"}
        binary=Path(sys.executable).parent/("nanobot.exe" if os.name=="nt" else "nanobot")
        if not binary.exists():raise RouterError("NANOBOT_MISSING","先安装 requirements-nanobot.txt。")
        # nanobot 0.3.5 requires session storage outside its agent workspace.
        state=Path(os.environ.get("LOCALAPPDATA", str(Path.home()/".local/share")))/"RouteLab"/("nanobot-"+hashlib.sha256(str(ROOT).encode()).hexdigest()[:12])
        state.mkdir(parents=True,exist_ok=True)
        config=state/"config.json"
        config.write_text((ROOT/"examples/nanobot.config.example.json").read_text(encoding="utf-8"),encoding="utf-8")
        result=subprocess.run([str(binary),"agent","--workspace",str(ROOT),"--config",str(config),
            "--classic","--no-markdown","--no-logs","--message",args.message],cwd=ROOT,env=env)
        raise SystemExit(result.returncode)
    except RouterError as exc:
        print(exc.code+": "+exc.message)
        raise SystemExit(1)
