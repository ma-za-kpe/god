#!/usr/bin/env python3
"""
Generate a private IPFS swarm key.
This key isolates your local IPFS nodes from the public network.
Keep it secret. Never commit it to git.
"""
import os
import secrets
import sys

output_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "swarm.key")

if os.path.exists(output_path):
    print(f"swarm.key already exists at {output_path}")
    print("Delete it first if you want to regenerate.")
    sys.exit(1)

key = secrets.token_hex(32)
content = f"/key/swarm/psk/1.0.0/\n/base16/\n{key}\n"

with open(output_path, "w") as f:
    f.write(content)

print(f"✓ swarm.key written to {output_path}")
print("  This key is gitignored. Keep it safe.")
print("  All IPFS nodes in your local stack use this key.")
