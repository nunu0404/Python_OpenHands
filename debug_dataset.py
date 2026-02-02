from datasets import load_dataset
try:
    print("Loading dataset bytedance-research/Multi-SWE-Bench...")
    ds = load_dataset("bytedance-research/Multi-SWE-Bench", split="java")
    print("Dataset loaded successfully.")
    print(ds.features)
except Exception as e:
    import traceback
    traceback.print_exc()
