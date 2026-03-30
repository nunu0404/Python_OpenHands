#!/usr/bin/env python3

import argparse
import json
from pathlib import Path

import pandas as pd


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Convert an Excel benchmark sheet to JSONL."
    )
    parser.add_argument("input_xlsx", help="Path to the input .xlsx file")
    parser.add_argument("output_jsonl", help="Path to the output .jsonl file")
    args = parser.parse_args()

    input_path = Path(args.input_xlsx)
    output_path = Path(args.output_jsonl)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    dataframe = pd.read_excel(input_path)
    with output_path.open("w", encoding="utf-8") as handle:
        for _, row in dataframe.iterrows():
            record = {
                key: (None if pd.isna(value) else value)
                for key, value in row.to_dict().items()
            }
            json.dump(record, handle, ensure_ascii=False, default=str)
            handle.write("\n")

    print(f"Wrote {len(dataframe)} rows to {output_path}")


if __name__ == "__main__":
    main()
