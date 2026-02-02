import os
import glob
import subprocess

# Define paths
input_dir = "temp_dataset_downloaded/java"
output_file = "evaluation/benchmarks/multi_swe_bench/processed_java_dataset.jsonl"
script_path = "evaluation/benchmarks/multi_swe_bench/scripts/data/data_change.py"

# Ensure output directory exists
os.makedirs(os.path.dirname(output_file), exist_ok=True)

# Function to run the conversion script
def process_file(input_path, output_path):
    cmd = ["python3", script_path, "--input", input_path, "--output", output_path]
    print(f"Processing {input_path} -> {output_path}")
    subprocess.check_call(cmd)

# Get all jsonl files
jsonl_files = glob.glob(os.path.join(input_dir, "*_dataset.jsonl"))

# Process each file to a temp output
temp_outputs = []
for i, f in enumerate(jsonl_files):
    temp_out = f"{output_file}.part{i}"
    process_file(f, temp_out)
    temp_outputs.append(temp_out)

# Concatenate all parts
with open(output_file, 'w') as outfile:
    for fname in temp_outputs:
        with open(fname, 'r') as infile:
            for line in infile:
                outfile.write(line)
        # Clean up temp file
        os.remove(fname)

print(f"Merged {len(temp_outputs)} files into {output_file}")
