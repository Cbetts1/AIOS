"""System maintenance, diagnostics, and repair tooling for AURA OS.

Provides real system repair and diagnostic capabilities:
- System diagnostics (hardware, OS, Python environment)
- Log rotation and cleanup
- Directory repair (recreate missing AURA structure)
- Service health checking
- Integrity verification
- System information reporting

Usage::

    from aura_os.maintenance import Diagnostics, Repair
    d = Diagnostics()
    d.run_all()
    r = Repair()
    r.repair_dirs()
"""

from .diagnostics import Diagnostics
from .repair import Repair

__all__ = ["Diagnostics", "Repair"]
