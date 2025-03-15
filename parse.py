import sys
import json

d = {}
for line in sys.stdin.readlines():
    _, version, server, client, _ = line.split("|")
    if server.strip().lower() == "not found":
        continue
    d[version.strip()] = server.strip()
print(json.dumps(d, indent=4))
