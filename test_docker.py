import docker
try:
    client = docker.from_env()
    print(client.version())
    print("Docker access successful")
except Exception as e:
    print(f"Docker access failed: {e}")
