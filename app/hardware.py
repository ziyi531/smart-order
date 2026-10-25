import subprocess
from typing import Optional


def detect_gpu() -> Optional[str]:
    """Return e.g. 'NVIDIA GeForce RTX 4060 Laptop GPU (8188 MiB)', or None without an NVIDIA driver."""
    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader"],
            capture_output=True, text=True, timeout=3, check=True,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return None
    if not out:
        return None
    name, _, memory = out.splitlines()[0].partition(",")
    return f"{name.strip()} ({memory.strip()})" if memory else name.strip()
