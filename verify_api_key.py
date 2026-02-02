
import os
import toml
from litellm import completion

def test_key():
    try:
        config = toml.load("config.toml")
        api_key = config["llm"]["eval"]["api_key"]
        model = config["llm"]["eval"]["model"]
        base_url = config["llm"]["eval"].get("base_url")
        print(f"Testing model: {model}")
        print(f"Using key: {api_key[:5]}...{api_key[-4:]}")
        if base_url:
            print(f"Using base_url: {base_url}")
        
        response = completion(
            model=model,
            messages=[{"role": "user", "content": "Hello, are you working?"}],
            api_key=api_key,
            base_url=base_url
        )
        print("Success! Response:", response.choices[0].message.content)
    except Exception as e:
        print("Error:", e)

if __name__ == "__main__":
    test_key()
