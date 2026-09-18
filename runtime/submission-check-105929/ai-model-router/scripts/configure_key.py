"""Interactive secret entry; never accept a key as a command-line argument."""
import getpass
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills/ai-model-router/scripts"))
from routerlib.settings import SettingsStore
from routerlib.config import RouterError
if __name__ == "__main__":
    try:
        store = SettingsStore()
        store.save({"api_key": getpass.getpass("DeepSeek API key (hidden): ")})
        print(json.dumps(store.check(), ensure_ascii=False, indent=2))
    except RouterError as exc:
        print(exc.code + ": " + exc.message)
        raise SystemExit(1)
