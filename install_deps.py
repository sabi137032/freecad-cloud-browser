"""
install_deps.py — Auto-installer for FreeCAD Cloud Browser dependencies.

Called at plugin startup (InitGui.py). Checks for missing packages and installs
them using FreeCAD's own Python/pip — no user intervention required.
"""

import sys
import subprocess
import importlib.util

import FreeCAD

# ---------------------------------------------------------------------------
# Package map: import_name -> pip_package_name
# ---------------------------------------------------------------------------

# Core: always required
_CORE = {
    "requests": "requests>=2.31.0,<3.0",
}

# Per-provider: only checked/installed when available
_PROVIDER = {
    "googleapiclient":  "google-api-python-client>=2.100.0,<3.0",
    "google_auth_httplib2": "google-auth-httplib2>=0.1.1,<1.0",
    "google_auth_oauthlib": "google-auth-oauthlib>=1.1.0,<2.0",
    "dropbox":          "dropbox>=11.36.0,<13.0",
    "msal":             "msal>=1.24.0,<2.0",
    "boto3":            "boto3>=1.28.0,<2.0",
    "paramiko":         "paramiko>=3.3.0,<4.0",
    "webdav3":          "webdavclient3>=3.14.6,<4.0",
}

# Security: strongly recommended
_SECURITY = {
    "keyring":          "keyring>=24.0.0,<26.0",
    "cryptography":     "cryptography>=41.0.0,<44.0",
}

# All packages to install upfront
ALL_PACKAGES = {**_CORE, **_PROVIDER, **_SECURITY}


def _is_installed(import_name: str) -> bool:
    return importlib.util.find_spec(import_name) is not None


def _pip_install(packages: list[str]) -> tuple[bool, str]:
    """Run pip install for a list of package specs. Returns (success, output)."""
    cmd = [sys.executable, "-m", "pip", "install", "--quiet", "--no-warn-script-location"] + packages
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
        )
        return result.returncode == 0, result.stdout + result.stderr
    except Exception as e:
        return False, str(e)


def ensure_dependencies() -> bool:
    """
    Check and auto-install all missing dependencies.
    Returns True if all dependencies are available after the check.
    """
    missing = {
        name: spec
        for name, spec in ALL_PACKAGES.items()
        if not _is_installed(name)
    }

    if not missing:
        return True

    pkg_list = ", ".join(missing.keys())
    FreeCAD.Console.PrintMessage(
        f"[Cloud Browser] Installing missing dependencies: {pkg_list} ...\n"
    )

    # Try to show a status message in the FreeCAD status bar
    try:
        import FreeCADGui
        mw = FreeCADGui.getMainWindow()
        if mw:
            mw.statusBar().showMessage(
                f"Cloud Browser: installing {len(missing)} dependencies, please wait...", 0
            )
    except Exception:
        pass

    success, output = _pip_install(list(missing.values()))

    # Clear status bar
    try:
        import FreeCADGui
        mw = FreeCADGui.getMainWindow()
        if mw:
            mw.statusBar().clearMessage()
    except Exception:
        pass

    if success:
        FreeCAD.Console.PrintMessage(
            "[Cloud Browser] Dependencies installed successfully.\n"
        )
        return True
    else:
        FreeCAD.Console.PrintError(
            f"[Cloud Browser] Failed to install some dependencies.\n"
            f"Details:\n{output}\n"
            f"You can install manually: pip install {' '.join(missing.values())}\n"
        )
        return False
