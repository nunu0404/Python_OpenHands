import json
import pandas as pd
import argparse

def main():
    parser = argparse.ArgumentParser(description="Convert OpenHands output JSONL to SWE-bench-Live JSON format")
    parser.add_argument("input_file", help="Path to the input swebench.jsonl file")
    parser.add_argument("output_file", help="Path to the output swebench-live.json file")
    args = parser.parse_args()

    df = pd.read_json(args.input_file, lines=True)
    preds = {}
    for _, row in df.iterrows():
        preds[row['instance_id']] = {'model_patch': row.get('model_patch', '')}

    with open(args.output_file, 'w') as f:
        json.dump(preds, f, indent=4)

    print(f"Successfully converted {args.input_file} to {args.output_file}")

if __name__ == "__main__":
    main()
