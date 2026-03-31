"""``aura auto`` command handler — task automation."""

import json
import time
from datetime import datetime
from pathlib import Path
import os


class AutoCommand:
    """Automation task management: list, create, run.

    Tasks are JSON workflow files stored in ``~/.aura/tasks/``.
    """

    def execute(self, args, eal) -> int:
        sub = getattr(args, "auto_command", None)

        if sub == "list":
            return self._list()
        if sub == "create":
            return self._create(args.name)
        if sub == "run":
            return self._run(args.name, eal)

        print("[auto] Unknown sub-command. Run 'aura auto --help'.")
        return 1

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _tasks_dir() -> Path:
        aura_home = os.environ.get("AURA_HOME", os.path.expanduser("~/.aura"))
        d = Path(aura_home) / "tasks"
        d.mkdir(parents=True, exist_ok=True)
        return d

    @staticmethod
    def _logs_dir() -> Path:
        aura_home = os.environ.get("AURA_HOME", os.path.expanduser("~/.aura"))
        d = Path(aura_home) / "logs"
        d.mkdir(parents=True, exist_ok=True)
        return d

    # ------------------------------------------------------------------
    # sub-commands
    # ------------------------------------------------------------------

    def _list(self) -> int:
        tasks = sorted(self._tasks_dir().glob("*.json"))
        if not tasks:
            print("[auto] No tasks found. Create one with: aura auto create <name>")
            return 0

        print(f"\n  Tasks in {self._tasks_dir()}:")
        print("  " + "─" * 40)
        for t in tasks:
            try:
                data = json.loads(t.read_text())
                desc = data.get("description", "")
                steps = len(data.get("steps", []))
                print(f"  {t.stem:<20} {desc} ({steps} steps)")
            except (json.JSONDecodeError, OSError):
                print(f"  {t.stem:<20} (invalid JSON)")
        print()
        return 0

    def _create(self, name: str) -> int:
        task_file = self._tasks_dir() / f"{name}.json"
        if task_file.exists():
            print(f"[auto] Task '{name}' already exists: {task_file}")
            return 1

        template = {
            "name": name,
            "description": f"Task: {name}",
            "steps": [
                {"type": "log", "message": f"Starting task {name}"},
                {"type": "run", "cmd": "echo 'Hello from AURA'"},
                {"type": "log", "message": "Done."},
            ],
        }
        task_file.write_text(json.dumps(template, indent=2))
        print(f"[auto] Created task template: {task_file}")
        print(f"       Edit it and run with: aura auto run {name}")
        return 0

    def _run(self, name: str, eal) -> int:
        task_file = self._tasks_dir() / f"{name}.json"
        if not task_file.exists():
            print(f"[auto] Task '{name}' not found. Use 'aura auto list'.")
            return 1

        try:
            data = json.loads(task_file.read_text())
        except json.JSONDecodeError as exc:
            print(f"[auto] Invalid task JSON: {exc}")
            return 1

        steps = data.get("steps", [])
        log_lines = [
            f"AURA Automation — Task: {name}",
            f"Started: {datetime.now().isoformat()}",
            "",
        ]

        print(f"\n  Running task: {name}")
        print("  " + "─" * 40)

        for i, step in enumerate(steps):
            step_type = step.get("type", "").lower()
            print(f"  Step {i + 1}/{len(steps)}: {step_type} …", end=" ", flush=True)

            if step_type == "run":
                cmd = step.get("cmd", "")
                if not cmd:
                    print("SKIP (no cmd)")
                    continue
                rc, out, err = eal.run_command(cmd if isinstance(cmd, list) else cmd.split())
                status = "OK" if rc == 0 else f"FAIL (code {rc})"
                print(status)
                log_lines.append(f"[step {i + 1}] run: {cmd}  -> {status}")

            elif step_type == "log":
                msg = step.get("message", "")
                print("OK")
                print(f"         {msg}")
                log_lines.append(f"[step {i + 1}] log: {msg}")

            elif step_type == "sleep":
                secs = float(step.get("seconds", 1))
                time.sleep(secs)
                print(f"OK ({secs}s)")
                log_lines.append(f"[step {i + 1}] sleep: {secs}s")

            elif step_type == "write":
                path = step.get("path", "")
                content = step.get("content", "")
                if path:
                    eal.write_file(path, content)
                    print("OK")
                    log_lines.append(f"[step {i + 1}] write: {path}")
                else:
                    print("SKIP (no path)")

            else:
                print(f"UNKNOWN step type '{step_type}'")

        log_lines.append("")
        log_lines.append(f"Finished: {datetime.now().isoformat()}")

        log_file = self._logs_dir() / f"auto_{name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        try:
            log_file.write_text("\n".join(log_lines))
            print(f"\n  Log: {log_file}\n")
        except OSError:
            pass

        return 0
