"""Create/refresh persistent CPU and CUDA build venvs for setup.bat (option 3).

Keeps torch wheels separate so release builds do not uninstall/reinstall
between CPU and CUDA PyInstaller runs.

Usage:
  python scripts/bootstrap_build_venvs.py           # both
  python scripts/bootstrap_build_venvs.py --cpu
  python scripts/bootstrap_build_venvs.py --cuda
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import venv
from pathlib import Path

# Keep versions in sync with scripts/ensure_torch.py and requirements.txt
TORCH_VER = "2.11.0"
VISION_VER = "0.26.0"
CUDA_CANDIDATES = (
    ("cu128", "https://download.pytorch.org/whl/cu128"),
    ("cu126", "https://download.pytorch.org/whl/cu126"),
    ("cu124", "https://download.pytorch.org/whl/cu124"),
)

ROOT = Path(__file__).resolve().parent.parent
REQS = ROOT / "requirements.txt"
CPU_VENV = ROOT / ".venv-build-cpu"
CUDA_VENV = ROOT / ".venv-build-cuda"


def _run(cmd: list[str]) -> int:
    print("+", " ".join(cmd))
    return subprocess.run(cmd, check=False).returncode


def _venv_python(venv_dir: Path) -> Path:
    return venv_dir / "Scripts" / "python.exe"


def _ensure_venv(venv_dir: Path) -> Path:
    py = _venv_python(venv_dir)
    if py.is_file():
        return py
    print(f"Creating {venv_dir.name} …")
    venv.create(venv_dir, with_pip=True)
    if not py.is_file():
        raise SystemExit(f"[ERROR] Failed to create {venv_dir}")
    return py


def _pip(py: Path, *args: str) -> int:
    return _run([str(py), "-m", "pip", "install", *args])


def _torch_status(py: Path) -> tuple[str, bool]:
    script = (
        "import torch;"
        "print(torch.__version__);"
        "print('1' if torch.cuda.is_available() else '0')"
    )
    r = subprocess.run(
        [str(py), "-c", script],
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


def _version_matches(version: str) -> bool:
    return bool(version) and version.startswith(TORCH_VER)


def _is_cpu_torch(version: str, cuda_ok: bool) -> bool:
    if not _version_matches(version):
        return False
    if "+cpu" in version.lower():
        return True
    # Plain PyPI builds report no CUDA
    return not cuda_ok


def _is_cuda_torch(version: str, cuda_ok: bool) -> bool:
    return (
        _version_matches(version)
        and cuda_ok
        and "+cpu" not in version.lower()
    )


def _install_requirements(py: Path) -> None:
    if not REQS.is_file():
        raise SystemExit(f"[ERROR] Missing {REQS}")
    code = _pip(py, "--upgrade", "pip")
    if code != 0:
        raise SystemExit("[ERROR] pip upgrade failed")
    code = _pip(py, "-r", str(REQS))
    if code != 0:
        raise SystemExit("[ERROR] requirements install failed")


def _uninstall_torch(py: Path) -> None:
    _run(
        [
            str(py),
            "-m",
            "pip",
            "uninstall",
            "-y",
            "torch",
            "torchvision",
            "torchaudio",
        ]
    )


def _force_cpu_torch(py: Path) -> None:
    _uninstall_torch(py)
    code = _pip(py, f"torch=={TORCH_VER}", f"torchvision=={VISION_VER}")
    if code != 0:
        raise SystemExit("[ERROR] CPU torch install failed")


def _force_cuda_torch(py: Path) -> None:
    _uninstall_torch(py)
    last_code = 1
    for tag, index in CUDA_CANDIDATES:
        print(f"Trying CUDA index {tag} …")
        last_code = _pip(
            py,
            f"torch=={TORCH_VER}",
            f"torchvision=={VISION_VER}",
            "--index-url",
            index,
        )
        version, cuda_ok = _torch_status(py)
        if last_code == 0 and _version_matches(version) and "+cpu" not in version.lower():
            print(f"Installed torch {version} from {tag} (cuda_available={cuda_ok})")
            if not cuda_ok:
                raise SystemExit(
                    "[ERROR] CUDA torch installed but torch.cuda.is_available() is False. "
                    "Update NVIDIA drivers and retry."
                )
            return
        print(f"{tag} failed (exit {last_code}), trying next…")
    raise SystemExit("[ERROR] CUDA torch install failed for all candidate indexes")


def ensure_cpu_env(*, force: bool = False) -> Path:
    py = _ensure_venv(CPU_VENV)
    version, cuda_ok = _torch_status(py)
    if not force and _is_cpu_torch(version, cuda_ok):
        print(f"{CPU_VENV.name}: OK (torch {version})")
        _install_requirements(py)
        version, cuda_ok = _torch_status(py)
        if not _is_cpu_torch(version, cuda_ok):
            print("Re-pinning CPU torch after requirements refresh …")
            _force_cpu_torch(py)
    else:
        print(f"=== Bootstrapping {CPU_VENV.name} (CPU torch) ===")
        _install_requirements(py)
        _force_cpu_torch(py)

    version, cuda_ok = _torch_status(py)
    if not _is_cpu_torch(version, cuda_ok):
        raise SystemExit(
            f"[ERROR] CPU build venv torch not ready: version={version!r} cuda={cuda_ok}"
        )
    print(f"CPU build python: {py}")
    return py


def ensure_cuda_env(*, force: bool = False) -> Path:
    py = _ensure_venv(CUDA_VENV)
    version, cuda_ok = _torch_status(py)
    if not force and _is_cuda_torch(version, cuda_ok):
        print(f"{CUDA_VENV.name}: OK (torch {version}, CUDA ready)")
        _install_requirements(py)
        version, cuda_ok = _torch_status(py)
        if not _is_cuda_torch(version, cuda_ok):
            print("Re-pinning CUDA torch after requirements refresh …")
            _force_cuda_torch(py)
    else:
        print(f"=== Bootstrapping {CUDA_VENV.name} (CUDA torch) ===")
        _install_requirements(py)
        _force_cuda_torch(py)

    version, cuda_ok = _torch_status(py)
    if not _is_cuda_torch(version, cuda_ok):
        raise SystemExit(
            f"[ERROR] CUDA build venv torch not ready: version={version!r} cuda={cuda_ok}"
        )
    print(f"CUDA build python: {py}")
    return py


def main() -> int:
    parser = argparse.ArgumentParser(description="Bootstrap CPU/CUDA build venvs")
    parser.add_argument("--cpu", action="store_true", help="Ensure .venv-build-cpu")
    parser.add_argument("--cuda", action="store_true", help="Ensure .venv-build-cuda")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Reinstall torch even if versions look correct",
    )
    args = parser.parse_args()
    if args.cpu or args.cuda:
        do_cpu, do_cuda = args.cpu, args.cuda
    else:
        do_cpu = do_cuda = True

    if do_cpu:
        ensure_cpu_env(force=args.force)
    if do_cuda:
        ensure_cuda_env(force=args.force)
    print("Build venv bootstrap done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
