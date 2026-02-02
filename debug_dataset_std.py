from datasets import load_dataset
try:
    print("Loading dataset princeton-nlp/SWE-bench_Lite...")
    ds = load_dataset("princeton-nlp/SWE-bench_Lite", split="test")
    print("Dataset loaded successfully.")
    print(ds.features)
except Exception as e:
    import traceback
    traceback.print_exc()
