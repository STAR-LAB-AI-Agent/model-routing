"""Use installed nanobot SkillsLoader + ExecTool, with real DeepSeek generation.

This is a real runtime tool-execution smoke test, not a claim of LLM planning.
Only fixed public course examples are passed to the shell.
"""
import asyncio
import json
import os
from pathlib import Path
import shlex
import sys
from importlib.metadata import version

ROOT = Path(__file__).resolve().parents[1]


async def verify():
    from nanobot.agent.skills import SkillsLoader
    from nanobot.agent.tools.shell import ExecTool
    skill = SkillsLoader(ROOT)
    found = [s for s in skill.list_skills() if s["name"] == "ai-model-router"]
    if not found or "--json-stdin" not in (skill.load_skill("ai-model-router") or ""):
        raise RuntimeError("Skill was not discovered by nanobot")
    tool = ExecTool(timeout=90, working_dir=str(ROOT), restrict_to_workspace=True)
    exe = str(Path(sys.executable).resolve())
    if not Path(exe).is_relative_to(ROOT):
        raise RuntimeError("Run this check using the project .venv Python inside the workspace.")
    if os.name == "nt":
        # Only fixed trusted paths and example IDs enter this command.
        quoted = "'" + exe.replace("'", "''") + "'"
        command = "$env:PYTHONUTF8='1'; $OutputEncoding=[System.Text.UTF8Encoding]::new(); Get-Content -Raw -Encoding utf8 examples/qa.json | & " + quoted + " skills/ai-model-router/scripts/router.py run --json-stdin"
    else:
        command = shlex.quote(exe) + " skills/ai-model-router/scripts/router.py run --json-stdin < examples/qa.json"
    output = str(await tool.execute(command=command, timeout=90, max_output_chars=12000))
    left, right = output.find("{"), output.rfind("}")
    if left == -1:
        raise RuntimeError("nanobot ExecTool returned no JSON: " + output)
    result = json.loads(output[left:right+1])
    if not result.get("ok") or result["route"]["tier"] != "eco":
        raise RuntimeError("nanobot execution failed: " + output)
    report = {"ok":True, "nanobot_version":version("nanobot-ai"), "skill_discovered":True,
              "execution_tool":"nanobot.agent.tools.shell.ExecTool", "workspace_restricted":True,
              "mode":"live", "router_result":result,
              "scope":"Real SkillsLoader + ExecTool invocation. Real DeepSeek generation through the script. No orchestration LLM planning is claimed."}
    out = ROOT / "artifacts/nanobot-verification.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(report,ensure_ascii=False,indent=2))


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"): sys.stdout.reconfigure(encoding="utf-8")
    asyncio.run(verify())
