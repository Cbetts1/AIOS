"""
Capability Forge OS — Fallback capability stub generator.

When the router finds no matching capability it calls the generator, which:
  1. Builds a new Capability from the intent string.
  2. Writes a Python stub to  capabilities/generated/<id>/generated.py
  3. Writes metadata to        capabilities/generated/<id>/meta.json
  4. Returns the new Capability so the registry can add it in memory.
"""

import json
import os
import re
from datetime import datetime, timezone
from typing import Optional

from core.models import Capability

_GENERATED_BASE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "capabilities",
    "generated",
)

_STUB_TEMPLATE = '''\
"""
Auto-generated capability stub.

ID          : {cap_id}
Name        : {cap_name}
Description : {description}
Generated   : {timestamp}
"""


def run(inputs: dict) -> dict:
    """Execute this capability with the provided inputs."""
    # TODO: implement capability logic for: {description}
    return {{"status": "stub", "capability": "{cap_id}", "inputs": inputs}}
'''


def _slug(text: str) -> str:
    """Convert *text* to a safe lowercase identifier."""
    slug = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
    return slug or "capability"


class CapabilityGenerator:
    """Generates and persists new capability stubs from an intent string."""

    def __init__(self, generated_base: str = _GENERATED_BASE) -> None:
        self.generated_base = generated_base

    def generate(self, intent: str, existing_ids: Optional[set] = None) -> Capability:
        """
        Create a new Capability from *intent*, write files to disk, and
        return the Capability object.
        """
        base_id = _slug(intent)
        cap_id = self._unique_id(base_id, existing_ids or set())

        cap = Capability(
            id=cap_id,
            name=cap_id,
            repo="Cbetts1/AIOS",
            description=f"Auto-generated capability for: {intent}",
            type="generated",
            inputs=["intent"],
            outputs=["result"],
            runtime="python",
            dependencies=[],
            ai_routable=True,
            generatable=True,
            status="active",
            entrypoint=f"capabilities/generated/{cap_id}/generated.py",
            version="0.1.0",
        )

        self._write_files(cap, intent)
        return cap

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _unique_id(self, base: str, existing: set) -> str:
        if base not in existing:
            return base
        counter = 1
        while f"{base}_{counter}" in existing:
            counter += 1
        return f"{base}_{counter}"

    def _write_files(self, cap: Capability, intent: str) -> None:
        cap_dir = os.path.join(self.generated_base, cap.id)
        os.makedirs(cap_dir, exist_ok=True)

        timestamp = datetime.now(timezone.utc).isoformat()

        # Python stub
        stub_path = os.path.join(cap_dir, "generated.py")
        stub_content = _STUB_TEMPLATE.format(
            cap_id=cap.id,
            cap_name=cap.name,
            description=cap.description,
            timestamp=timestamp,
        )
        with open(stub_path, "w", encoding="utf-8") as fh:
            fh.write(stub_content)

        # Metadata JSON
        meta_path = os.path.join(cap_dir, "meta.json")
        meta = cap.to_dict()
        meta["generated_at"] = timestamp
        meta["original_intent"] = intent
        with open(meta_path, "w", encoding="utf-8") as fh:
            json.dump(meta, fh, indent=2)
