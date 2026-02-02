import argparse
import json
import sys
from typing import Any


def build_predictions(
    output_jsonl: str, include_model_name: bool
) -> tuple[dict[str, dict[str, Any]], dict[str, int]]:
    predictions: dict[str, dict[str, Any]] = {}
    total = 0
    skipped = 0
    duplicates = 0

    with open(output_jsonl, "r", encoding="utf-8") as handle:
        for line_num, line in enumerate(handle, 1):
            line = line.strip()
            if not line:
                continue
            total += 1
            try:
                output = json.loads(line)
            except json.JSONDecodeError as exc:
                print(
                    f"Skipping line {line_num}: invalid JSON ({exc})",
                    file=sys.stderr,
                )
                skipped += 1
                continue

            instance_id = output.get("instance_id")
            test_result = output.get("test_result", {})
            git_patch = test_result.get("git_patch")

            if not instance_id or git_patch is None:
                print(
                    f"Skipping line {line_num}: missing instance_id or git_patch",
                    file=sys.stderr,
                )
                skipped += 1
                continue

            entry: dict[str, Any] = {"model_patch": git_patch}
            if include_model_name:
                model_name = (
                    output.get("metadata", {})
                    .get("llm_config", {})
                    .get("model")
                )
                if model_name:
                    entry["model_name_or_path"] = model_name

            if instance_id in predictions:
                duplicates += 1
            predictions[instance_id] = entry

    stats = {
        "total": total,
        "skipped": skipped,
        "duplicates": duplicates,
        "written": len(predictions),
    }
    return predictions, stats


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Convert OpenHands output.jsonl to SWE-bench-Live eval JSON."
    )
    parser.add_argument(
        "--output_jsonl",
        required=True,
        help="Path to OpenHands output.jsonl",
    )
    parser.add_argument(
        "--output_json",
        default="-",
        help="Path to write JSON predictions ('-' for stdout)",
    )
    parser.add_argument(
        "--include_model_name",
        action="store_true",
        help="Include model_name_or_path for traceability",
    )
    args = parser.parse_args()

    predictions, stats = build_predictions(
        args.output_jsonl, args.include_model_name
    )

    if args.output_json == "-":
        json.dump(predictions, sys.stdout)
        sys.stdout.write("\n")
    else:
        with open(args.output_json, "w", encoding="utf-8") as handle:
            json.dump(predictions, handle)

    print(
        "Converted {total} lines (written={written}, skipped={skipped}, duplicates={duplicates}).".format(
            **stats
        ),
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
