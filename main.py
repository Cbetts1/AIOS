"""
Capability Forge OS — CLI prompt loop (v1 prototype).

Usage:
    python3 main.py

Type an intent to route/execute a capability.
Type 'quit' or 'exit' to stop.
"""

import sys
import os

# Allow running from the repo root without installing the package
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.executor import CapabilityExecutor
from core.generator import CapabilityGenerator
from core.logger import CapabilityLogger
from core.registry import CapabilityRegistry
from core.router import CapabilityRouter


def _banner(registry: CapabilityRegistry) -> None:
    print("=" * 60)
    print("  Capability Forge OS  —  v1 prototype")
    print("=" * 60)
    print(f"  Loaded {registry.count()} capabilities.")
    print("  Type an intent, or 'quit' / 'exit' to stop.")
    print("=" * 60)


def run_loop() -> None:
    registry = CapabilityRegistry()
    registry.load()

    router = CapabilityRouter()
    executor = CapabilityExecutor()
    generator = CapabilityGenerator()
    logger = CapabilityLogger()

    _banner(registry)

    while True:
        try:
            intent = input("\n> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting.")
            break

        if not intent:
            continue

        if intent.lower() in {"quit", "exit"}:
            print("Goodbye.")
            break

        # Route intent
        capability, needs_generation = router.route(intent, registry.all())

        if needs_generation:
            print(f"  No matching capability found. Generating stub for: '{intent}' …")
            capability = generator.generate(intent, existing_ids=set(registry.ids()))
            registry.add(capability)
            logger.log_generated(intent, capability.id)
            print(f"  Generated capability '{capability.id}'")
            print(f"  Stub: {capability.entrypoint}")
        else:
            logger.log_matched(intent, capability.id)

        # Execute
        result = executor.execute(capability, intent)
        print()
        print(str(result))


if __name__ == "__main__":
    run_loop()
