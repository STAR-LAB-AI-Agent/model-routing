"""Route cases always run locally; --live explicitly performs three paid requests."""
import argparse
import json
from pathlib import Path
import sys
import tempfile
from datetime import datetime, timezone
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"skills/ai-model-router/scripts"))
from routerlib.service import RouterService
from routerlib.config import RouterError


def evaluate(live=False):
    cases=json.loads((ROOT/"examples/test-cases.json").read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory() as storage:
        service=RouterService(storage); rows=[]
        for case in cases:
            req={k:v for k,v in case.items() if k not in ("id","category","expected_tier","expected_error")}
            try: actual=service.preview(req)["route"]["tier"]
            except RouterError as exc: actual=exc.code
            expected=case.get("expected_tier",case.get("expected_error"))
            rows.append({"id":case["id"],"category":case["category"],"expected":expected,"actual":actual,"pass":expected==actual})
        result={"generated_at":datetime.now(timezone.utc).isoformat(),"cases":rows,"passed":sum(r["pass"] for r in rows),"total":len(rows)}
        if live:
            import litellm
            inputs=[json.loads((ROOT/f"examples/{name}.json").read_text(encoding="utf-8")) for name in ("qa","summary","code")]
            first=[service.run(r) for r in inputs]
            if any(not r["ok"] or r.get("incomplete") for r in first):
                raise RuntimeError("Real API verification incomplete; no success evidence written.")
            repeat=[service.run(r) for r in inputs]
            assert all(r["cache_hit"] for r in repeat)
            result["real_api"]={"first":first,"repeat":repeat,
                "actual_requests":6,"actual_provider_calls":3,
                "input_tokens":sum(r["input_tokens"] for r in first),
                "output_tokens":sum(r["output_tokens"] for r in first),
                "estimated_cost_usd":round(sum(r["cost"] for r in first),8),
                "note":"Three real requests followed by three in-process cache hits. Repeated requests made zero new API calls. No uncached baseline run or model quality benchmark is claimed."}
        out=ROOT/("artifacts/evaluation.json" if live else "artifacts/routing-cases.json")
        out.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
        print(json.dumps(result,ensure_ascii=False,indent=2))
        return result


if __name__=="__main__":
    if hasattr(sys.stdout,"reconfigure"):sys.stdout.reconfigure(encoding="utf-8")
    p=argparse.ArgumentParser();p.add_argument("--live",action="store_true",help="Authorize three real paid calls")
    args=p.parse_args();r=evaluate(args.live)
    raise SystemExit(0 if r["passed"]==r["total"] else 1)
