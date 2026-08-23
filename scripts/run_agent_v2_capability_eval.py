from __future__ import annotations

import argparse
import asyncio
from collections import Counter, defaultdict
from datetime import datetime
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.config import settings  # noqa: E402
from app.schemas.evaluation import EvaluationCase, EvaluationRunRequest  # noqa: E402
from app.services.evaluation_service import EvaluationService  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the fixed Agent V2 capability evaluation dataset.")
    parser.add_argument(
        "--dataset",
        type=Path,
        default=ROOT / "data" / "evaluation" / "agent_v2_capability_eval_v1.json",
    )
    parser.add_argument("--output", type=Path)
    parser.add_argument("--repeat-count", type=int, default=1, choices=[1, 2, 3])
    parser.add_argument("--case-timeout", type=float, default=60.0)
    return parser.parse_args()


async def run(args: argparse.Namespace) -> Path:
    payload = json.loads(args.dataset.read_text(encoding="utf-8"))
    settings.agent_runtime_version = "v2"
    output_suites: list[dict] = []
    all_results: list[dict] = []
    started = datetime.now()

    for index, suite in enumerate(payload["suites"], start=1):
        cases = [EvaluationCase.model_validate(case) for case in suite["cases"]]
        request = EvaluationRunRequest(
            cases=cases,
            repeat_count=args.repeat_count,
            case_timeout_seconds=args.case_timeout,
            model_version=settings.openai_model,
            prompt_version="turn-understanding-v2-meal-aware",
            dataset_version=payload["dataset_version"],
            strategy_version="lynn-agent-v2",
            code_version="keykii-agent-v2",
        )
        report = await EvaluationService().run(request)
        serialized = report.model_dump(mode="json")
        output_suites.append({
            "name": suite["name"],
            "label": suite["label"],
            **serialized,
        })
        all_results.extend(serialized["results"])
        print(
            f"[{index}/{len(payload['suites'])}] {suite['label']}: "
            f"{serialized['summary']['passed']}/{serialized['summary']['total']} passed, "
            f"score={serialized['summary']['average_score']}",
            flush=True,
        )

    issue_counts = Counter(code for result in all_results for code in result["failure_codes"])
    issue_cases: dict[str, list[str]] = defaultdict(list)
    for result in all_results:
        for code in result["failure_codes"]:
            issue_cases[code].append(result["name"])
    passed = sum(bool(result["passed"]) for result in all_results)
    stable_passed = sum(bool(result["stable_pass"]) for result in all_results)
    duration_ms = round((datetime.now() - started).total_seconds() * 1000)
    final = {
        "dataset_version": payload["dataset_version"],
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "runtime": "v2",
        "summary": {
            "total": len(all_results),
            "passed": passed,
            "failed": len(all_results) - passed,
            "pass_rate": round(passed / len(all_results), 4) if all_results else 0,
            "stable_passed": stable_passed,
            "stable_pass_rate": round(stable_passed / len(all_results), 4) if all_results else 0,
            "average_score": round(sum(result["score"] for result in all_results) / len(all_results), 1) if all_results else 0,
            "duration_ms": duration_ms,
            "issues": [
                {"code": code, "count": count, "case_names": issue_cases[code]}
                for code, count in issue_counts.most_common()
            ],
        },
        "suites": output_suites,
    }
    output = args.output or (
        ROOT / "data" / "evaluation" / "results"
        / f"agent_v2_capability_eval_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(final, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved report: {output}", flush=True)
    return output


if __name__ == "__main__":
    asyncio.run(run(parse_args()))
