"""Create/refresh the persistent CPU build venv for setup.bat (option 3).

Usage:
  python scripts/bootstrap_build_venvs.py
  python scripts/bootstrap_build_venvs.py --force
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

ROOT = Path(__file__).resolve().parent.parent
REQS = ROOT / "requirements.txt"
CPU_VENV = ROOT / ".venv-build-cpu"


def _run(cmd: list[str]) -> int:
    print("+", " ".join(cmd))
    return subprocess.run(cmd, check=False).returncode


def _venv_python(venv_dir: Path) -> Path:
    return venv_dir / "Scripts" / "python.exe"


def _ensure_venv(venv_dir: Path) -> Path:
    py = _venv_python(venv_dir)
    if py.is_file():
        return py
    print(f"Creating {venv_dir.name} ...")
    venv.create(venv_dir, with_pip=True)
    if not py.is_file():
        raise SystemExit(f"[ERROR] Failed to create {venv_dir}")
    return py


def _pip(py: Path, *args: str) -> int:
    return _run([str(py), "-m", "pip", "install", *args])


def _torch_version(py: Path) -> str:
    script = "import torch; print(torch.__version__)"
    r = subprocess.run(
        [str(py), "-c", script],
        capture_output=True,
        text=True,
        check=False,
    )
    if r.returncode != 0:
        return ""
    lines = [ln.strip() for ln in r.stdout.splitlines() if ln.strip()]
    return lines[0] if lines else ""


def _version_matches(version: str) -> bool:
    return bool(version) and version.startswith(TORCH_VER)


def _is_cpu_torch(version: str) -> bool:
    if not _version_matches(version):
        return False
    v = version.lower()
    if "+cu" in v:
        return False
    return True


def _install_requirements(py: Path) -> None:
    if not REQS.is_file():
        raise SystemExit(f"[ERROR] Missing {REQS}")
    code = _pip(py, "--upgrade", "pip")
    if code != 0:
        raise SystemExit("[ERROR] pip upgrade failed")
    code = _pip(py, "-r", str(REQS))
    if code != 0:
        raise SystemExit("[ERROR] requirements install failed")


def _force_cpu_torch(py: Path) -> None:
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
    code = _pip(py, f"torch=={TORCH_VER}", f"torchvision=={VISION_VER}")
    if code != 0:
        raise SystemExit("[ERROR] CPU torch install failed")


def ensure_cpu_env(*, force: bool = False) -> Path:
    py = _ensure_venv(CPU_VENV)
    version = _torch_version(py)
    if not force and _is_cpu_torch(version):
        print(f"{CPU_VENV.name}: OK (torch {version})")
        _install_requirements(py)
        version = _torch_version(py)
        if not _is_cpu_torch(version):
            print("Re-pinning CPU torch after requirements refresh ...")
            _force_cpu_torch(py)
    else:
        print(f"=== Bootstrapping {CPU_VENV.name} (CPU torch) ===")
        _install_requirements(py)
        _force_cpu_torch(py)

    version = _torch_version(py)
    if not _is_cpu_torch(version):
        raise SystemExit(
            f"[ERROR] CPU build venv torch not ready: version={version!r}"
        )
    print(f"CPU build python: {py}")
    return py


def main() -> int:
    parser = argparse.ArgumentParser(description="Bootstrap CPU build venv")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Reinstall torch even if versions look correct",
    )
    # Accept legacy flags so old scripts/docs do not hard-fail.
    parser.add_argument("--cpu", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--cuda", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.cuda:
        print(
            "[WARN] CUDA build venvs were removed. Bootstrapping CPU only."
        )
    ensure_cpu_env(force=args.force)
    print("Build venv bootstrap done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
