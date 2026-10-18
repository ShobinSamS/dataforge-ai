"""Serialize CPU-heavy inference/rendering in the single-process POC."""
import threading

CPU_LOCK = threading.Lock()
