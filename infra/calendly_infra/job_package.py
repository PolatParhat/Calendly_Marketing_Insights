"""Build the files EMR Serverless needs: our package as a zip + the entry-point script.

Runs during `cdk synth`, so the uploaded code always matches the code in the repo.
"""

import shutil
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PACKAGE_DIR = REPO_ROOT / "src" / "calendly_insights"
ENTRY_POINT = REPO_ROOT / "jobs" / "run_pipeline.py"


def build_job_package(out_dir: Path) -> Path:
    """Write out_dir/calendly_insights.zip and out_dir/run_pipeline.py; return out_dir."""
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)
    with zipfile.ZipFile(out_dir / "calendly_insights.zip", "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(PACKAGE_DIR.glob("*.py")):
            # Fixed timestamp: the same code gives the same zip, so CDK only re-uploads on change.
            info = zipfile.ZipInfo(f"calendly_insights/{path.name}", date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            zf.writestr(info, path.read_bytes())
    shutil.copy(ENTRY_POINT, out_dir / "run_pipeline.py")
    return out_dir
