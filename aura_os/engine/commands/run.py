"""``aura run <file>`` command handler."""

import os
import shutil
import subprocess
from typing import Optional

from aura_os.shell.colors import cyan, dim, green, red, yellow


# Maps file extension → (runtime_binary, extra_flags)
_RUNTIME_MAP = {
    ".py":   ("python3", []),
    ".js":   ("node",    []),
    ".sh":   ("bash",    []),
    ".rb":   ("ruby",    []),
    ".pl":   ("perl",    []),
    ".php":  ("php",     []),
    ".lua":  ("lua",     []),
    ".r":    ("Rscript", []),
    ".R":    ("Rscript", []),
    ".ts":   ("ts-node", []),
    ".go":   ("go",      ["run"]),
}


class RunCommand:
    """Execute a script file using the appropriate runtime.

    The runtime is determined by the file extension.  The EAL is queried to
    confirm the runtime binary is available before execution.
    """

    def execute(self, args, eal) -> int:
        """Run *args.file* with optional trailing *args.args*.

        Returns the exit code of the child process.
        """
        filepath = os.path.expanduser(args.file)

        if not os.path.isfile(filepath):
            print(f"  {red('[run]')} File not found: {filepath}")
            return 1

        ext = os.path.splitext(filepath)[1].lower()
        entry = _RUNTIME_MAP.get(ext)

        if entry is None:
            # Try executing directly (shebang / executable)
            if os.access(filepath, os.X_OK):
                return self._run([filepath] + list(args.args or []))
            print(
                f"  {red('[run]')} No runtime found for extension '{ext}'.\n"
                f"        {dim('Make the file executable or add a shebang line.')}"
            )
            return 1

        runtime_bin, extra_flags = entry
        if not shutil.which(runtime_bin):
            print(f"  {red('[run]')} Runtime '{yellow(runtime_bin)}' not found in PATH.")
            return 1

        cmd = [runtime_bin] + extra_flags + [filepath] + list(args.args or [])
        return self._run(cmd)

    @staticmethod
    def _run(cmd: list) -> int:
        """Execute *cmd* with inherited stdio, return exit code."""
        try:
            result = subprocess.run(cmd)
            return result.returncode
        except KeyboardInterrupt:
            return 130
        except OSError as exc:
            print(f"  {red('[run]')} Error: {exc}")
            return 1
