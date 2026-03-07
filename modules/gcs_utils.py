"""
Shared GCS utilities and project-level constants.

All modules import from here to avoid duplicating
GCS setup, project paths, and bucket path constants.
"""

import os
import subprocess

from pathlib import Path


# ---------------------------------------------------------------------------
# Project-level paths
# ---------------------------------------------------------------------------
PROJECT_DIR = Path(__file__).resolve().parent.parent
KEY_DIR = PROJECT_DIR / 'keys'
OUTPUT_DIR = PROJECT_DIR / 'output'

# ---------------------------------------------------------------------------
# GCS bucket paths
# ---------------------------------------------------------------------------
CSDATA_DIR = Path("data_ecair_paaral")
CSDATA_PUBLIC_DIR = CSDATA_DIR / "public"
CSDATA_PRIVATE_DIR = CSDATA_DIR / "private"
CSDATA_RAW_DIR = CSDATA_DIR / "raw"
CSDATA_MODIFIED_DIR = CSDATA_DIR / "modified"

# ---------------------------------------------------------------------------
# GCS filesystem — initialized lazily via get_fs()
# ---------------------------------------------------------------------------
_fs = None


def get_fs():
    """Return a cached GCSFileSystem instance, installing gcsfs if needed."""
    global _fs
    if _fs is not None:
        return _fs

    try:
        import gcsfs
    except ImportError:
        print("Installing gcsfs library...")
        subprocess.run(["pip", "install", "-qq", "gcsfs"], check=True)
        print("gcsfs library installed.")
        import gcsfs

    path_tkn = KEY_DIR / "ecair-paaral-project-6178d521167f.json"
    if not path_tkn.exists():
        raise FileNotFoundError(
            f"GCS service token not found at {path_tkn}. "
            "Ensure you have the service account key for PAARAL."
        )

    _fs = gcsfs.GCSFileSystem(token=str(path_tkn))
    return _fs
