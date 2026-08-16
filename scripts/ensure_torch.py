"""Install CPU PyTorch for local .venv / setup.bat.

CUDA builds are no longer supported - they were large and unstable for this app.
"""

from __future__ import annotations

import subprocess
import sys

TORCH_VER = "2.11.0"
VISION_VER = "0.26.0"


def _run(cmd: list[str]) -> subprocess.CompletedProcess:
    print("+", " ".join(cmd))
    return subprocess.run(cmd, check=False)


def torch_status() -> tuple[str, bool]:
    """Return (version_string, cuda_available) from a fresh interpreter."""
    script = (
        "import torch;"
        "print(torch.__version__);"
        "print('1' if torch.cuda.is_available() else '0')"
    )
    r = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        check=False,
    )
    if r.returncode != 0:
        return "", False
    lines = [ln.strip() for ln in r.stdout.splitlines() if ln.strip()]
    if len(lines) < 2:
        return "", False
    return lines[0], lines[1] == "1"


def _uninstall_torch() -> None:
    _run(
        [
            sys.executable,
            "-m",
            "pip",
            "uninstall",
            "-y",
            "torch",
            "torchvision",
            "torchaudio",
        ]
    )


def install_cpu_torch() -> int:
    print(f"Installing CPU torch {TORCH_VER} from PyPI ...")
    _uninstall_torch()
    r = _run(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            f"torch=={TORCH_VER}",
            f"torchvision=={VISION_VER}",
        ]
    )
    return r.returncode


def main() -> int:
    version, cuda_ok = torch_status()
    print(f"torch: {version or '(not installed)'}  cuda_available={cuda_ok}")

    if version and "+cpu" in version.lower():
        print(f"Already on CPU torch {version}")
        return 0
    if version and not cuda_ok and "+cu" not in version.lower():
        # Plain PyPI wheel without +cpu tag
        print(f"Using torch {version}")
        return 0

    code = install_cpu_torch()
    version, cuda_ok = torch_status()
    print(f"CPU torch: {version or '(missing)'} cuda_available={cuda_ok}")
    return 0 if version else (code or 1)


if __name__ == "__main__":
    raise SystemExit(main())
