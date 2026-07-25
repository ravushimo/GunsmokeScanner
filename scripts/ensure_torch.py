"""Install CPU or CUDA PyTorch based on whether an NVIDIA GPU is present.

Runtime OCR already auto-selects GPU when `torch.cuda.is_available()`.
This script only picks the right *wheel* at install time - card model does
not matter (RTX 3060 / 4070 / etc. all use the same CUDA torch build).

If the CUDA install fails, CPU torch is restored so the app can still start.

IMPORTANT: Never import torch in this process and then reinstall - the old
module stays cached in sys.modules. Always probe via a fresh subprocess.
"""

from __future__ import annotations

import subprocess
import sys

TORCH_VER = "2.11.0"
VISION_VER = "0.26.0"
# Prefer cu128 (needed for Blackwell / RTX 50-series). Fallbacks tried if missing.
CUDA_CANDIDATES = (
    ("cu128", "https://download.pytorch.org/whl/cu128"),
    ("cu126", "https://download.pytorch.org/whl/cu126"),
    ("cu124", "https://download.pytorch.org/whl/cu124"),
)


def _run(cmd: list[str]) -> subprocess.CompletedProcess:
    print("+", " ".join(cmd))
    return subprocess.run(cmd, check=False)


def has_nvidia_gpu() -> bool:
    try:
        r = subprocess.run(
            ["nvidia-smi"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        return r.returncode == 0 and bool(r.stdout.strip())
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return False


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


def _is_cuda_wheel(version: str) -> bool:
    v = version.lower()
    return bool(version) and "+cpu" not in v and (
        "+cu" in v or "cuda" in v
    )


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


def install_cuda_torch() -> int:
    print(f"NVIDIA GPU detected - installing torch {TORCH_VER} (CUDA) ...")
    _uninstall_torch()
    last_code = 1
    for tag, index in CUDA_CANDIDATES:
        print(f"Trying {tag} ...")
        r = _run(
            [
                sys.executable,
                "-m",
                "pip",
                "install",
                f"torch=={TORCH_VER}",
                f"torchvision=={VISION_VER}",
                "--index-url",
                index,
            ]
        )
        last_code = r.returncode
        version, cuda_ok = torch_status()
        if r.returncode == 0 and _is_cuda_wheel(version):
            print(
                f"Installed torch {version} from {tag} "
                f"(cuda_available={cuda_ok})"
            )
            return 0
        print(
            f"{tag} not usable "
            f"(exit={r.returncode}, version={version or '(missing)'}, "
            f"cuda={cuda_ok}), trying next..."
        )
    return last_code


def main() -> int:
    nvidia = has_nvidia_gpu()
    version, cuda_ok = torch_status()
    print(f"nvidia-smi: {'yes' if nvidia else 'no'}")
    print(f"torch: {version or '(not installed)'}  cuda_available={cuda_ok}")

    if not nvidia:
        print("No NVIDIA GPU - ensuring CPU torch.")
        if version and "+cpu" in version.lower():
            return 0
        if cuda_ok:
            return 0
        return install_cpu_torch()

    if cuda_ok and _is_cuda_wheel(version):
        name = ""
        r = subprocess.run(
            [
                sys.executable,
                "-c",
                "import torch; print(torch.cuda.get_device_name(0))",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if r.returncode == 0:
            name = r.stdout.strip()
        print(f"CUDA ready: {name or 'GPU visible'}")
        return 0

    code = install_cuda_torch()
    version, cuda_ok = torch_status()
    print(
        f"After CUDA install: torch={version or '(missing)'} "
        f"cuda_available={cuda_ok}"
    )

    if _is_cuda_wheel(version):
        if cuda_ok:
            r = subprocess.run(
                [
                    sys.executable,
                    "-c",
                    "import torch; print(torch.cuda.get_device_name(0))",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            print(f"Using GPU: {r.stdout.strip() or '(unknown)'}")
        else:
            print(
                "CUDA wheel is installed but torch.cuda.is_available() is "
                "False (driver/toolkit mismatch?). Keeping the CUDA wheel."
            )
        return 0

    print(
        "CUDA wheel install failed - restoring CPU torch "
        "so the app can still start."
    )
    cpu_code = install_cpu_torch()
    version, _ = torch_status()
    print(f"CPU fallback: torch={version or '(missing)'}")
    if not version:
        return cpu_code or code or 1
    print(
        "App will run on CPU. Update NVIDIA drivers and re-run "
        "python scripts/ensure_torch.py to retry CUDA."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
