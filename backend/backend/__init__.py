from __future__ import annotations

from pathlib import Path

# Allow `backend.*` imports to keep working when Railway deploys with
# Root Directory set to `/backend`, where modules live directly under `/app`.
_package_dir = Path(__file__).resolve().parent
_project_backend_root = _package_dir.parent

if str(_project_backend_root) not in __path__:
    __path__.append(str(_project_backend_root))
