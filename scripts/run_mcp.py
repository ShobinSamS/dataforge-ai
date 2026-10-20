"""Absolute-path entry point for stdio clients, independent of their working directory."""
import os
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
os.chdir(root)
sys.path.insert(0, str(root))

if __name__ == "__main__":
    try:
        from backend.mcp_server import main
    except ModuleNotFoundError as exc:
        if exc.name == "mcp":
            sys.stderr.write("Install MCP support first: python -m pip install -r requirements-mcp.txt\n")
            raise SystemExit(1) from exc
        raise
    main()
