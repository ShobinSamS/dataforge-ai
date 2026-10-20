"""Print a client config with this checkout's absolute paths; writes no client settings."""
import argparse
import json
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--transport", choices=["stdio", "http"], default="stdio")
    parser.add_argument("--port", type=int, default=8001)
    parser.add_argument("--api-url", default="http://127.0.0.1:8000")
    args = parser.parse_args()
    if not 1 <= args.port <= 65535: parser.error("port must be 1–65535")
    root = Path(__file__).resolve().parents[1]
    server = {"command": sys.executable, "args": ["-X", "utf8", str(root/"scripts/run_mcp.py"),"--api-url",args.api_url]} if args.transport == "stdio" else {"url": f"http://127.0.0.1:{args.port}/mcp"}
    print(json.dumps({"mcpServers": {"dataforge": server}}, indent=2))


if __name__ == "__main__":
    main()
