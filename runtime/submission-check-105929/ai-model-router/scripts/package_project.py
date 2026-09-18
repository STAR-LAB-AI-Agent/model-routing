"""Build a GitHub-ready zip using Git's ignore rules, plus SHA256 manifest."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from zipfile import ZipFile, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parents[1]


def package():
    proc = subprocess.run(["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"], cwd=ROOT, check=True, capture_output=True)
    names = sorted(set(n for n in proc.stdout.decode("utf-8").split("\0") if n))
    manifest_name = "artifacts/submission-manifest.json"
    names = [n for n in names if n != manifest_name and (ROOT/n).is_file()]
    sys.path.insert(0, str(ROOT / "skills/ai-model-router/scripts"))
    from routerlib.settings import SettingsStore
    local_key = SettingsStore().key().encode()
    required = {"README.md", "deliverables/demo.mp4", "deliverables/实验报告.pdf", "tests/test_router.py", "requirements.txt", "skills/ai-model-router/SKILL.md"}
    if not required.issubset(names):
        raise RuntimeError("Missing submission files: " + str(required-set(names)))
    for name in names:
        if local_key and local_key in (ROOT/name).read_bytes():
            raise RuntimeError("Credential found in submission file: " + name)
        parts = Path(name).parts
        if any(p in (".venv", ".git", "runtime", "__pycache__", "node_modules") for p in parts) or name.startswith("artifacts/raw/") or Path(name).name in (".env", "models.live.json", "nanobot.local.json"):
            raise RuntimeError("Local-only file in Git index: " + name)
        if (ROOT/name).resolve().is_relative_to(ROOT) is False:
            raise RuntimeError("Path outside workspace: " + name)
    manifest={"project":"RouteLab course project 25", "files":[{"path":n,"bytes":(ROOT/n).stat().st_size,"sha256":hashlib.sha256((ROOT/n).read_bytes()).hexdigest()} for n in names]}
    (ROOT/manifest_name).write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding="utf-8")
    dest=ROOT.parent/"AI模型智能路由_第25题_完整提交包.zip"
    with ZipFile(dest,"w",ZIP_DEFLATED) as archive:
        for name in names+[manifest_name]:
            archive.write(ROOT/name,"ai-model-router/"+name)
    with ZipFile(dest) as archive:
        assert archive.testzip() is None
        for entry in manifest["files"]:
            assert hashlib.sha256(archive.read("ai-model-router/"+entry["path"])).hexdigest()==entry["sha256"]
    print(json.dumps({"archive":str(dest),"files":len(names)+1,"bytes":dest.stat().st_size,"sha256":hashlib.sha256(dest.read_bytes()).hexdigest()},ensure_ascii=False,indent=2))


if __name__=="__main__":
    package()
