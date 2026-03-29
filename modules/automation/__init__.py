"""
Automation Module — Task Runner and Workflow Engine
Manages named tasks stored as JSON workflow definitions.
"""

import json
import time
from pathlib import Path
from datetime import datetime


TASK_SCHEMA = {
    "name": "example",
    "description": "An example task",
    "steps": [
        {"type": "run", "cmd": "echo 'Hello from AURA automation'"},
        {"type": "log", "message": "Task complete."},
    ],
}


class AutomationModule:
    """
    Manages and executes workflow tasks defined as JSON files.
    Each task is stored in <aura_home>/tasks/<name>.json
    """

    def __init__(self, env_map: dict, adapter):
        self.env = env_map
        self.adapter = adapter
        self._tasks_dir = Path(env_map.get("storage_root", Path.home() / ".aura")) / "tasks"
        self._tasks_dir.mkdir(parents=True, exist_ok=True)
        self._log_dir = Path(env_map.get("storage_root", Path.home() / ".aura")) / "logs"
        self._log_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------ #
    # Public operations
    # ------------------------------------------------------------------ #

    def list_tasks(self):
        """List all available tasks."""
        tasks = sorted(self._tasks_dir.glob("*.json"))
        if not tasks:
            print("[auto] No tasks found. Create one with: aura auto create <name>")
            return

        print(f"\n  Tasks in {self._tasks_dir}:")
        print("  " + "─" * 40)
        for t in tasks:
            try:
                data = json.loads(t.read_text())
                desc = data.get("description", "")
                steps = len(data.get("steps", []))
                print(f"  {t.stem:<20} {desc} ({steps} steps)")
            except Exception:
                print(f"  {t.stem:<20} (invalid JSON)")
        print()

    def run_task(self, name: str):
        """Execute the task named *name*."""
        if not name:
            print("[auto] Usage: aura auto run <task-name>")
            return

        task_file = self._tasks_dir / f"{name}.json"
        if not task_file.exists():
            print(f"[auto] Task '{name}' not found. Use 'aura auto list' to see available tasks.")
            return

        try:
            data = json.loads(task_file.read_text())
        except json.JSONDecodeError as e:
            print(f"[auto] Invalid task JSON: {e}")
            return

        steps = data.get("steps", [])
        log_file = self._log_dir / f"auto_{name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        log_lines = [f"AURA Automation — Task: {name}", f"Started: {datetime.now().isoformat()}", ""]

        print(f"\n  Running task: {name}")
        print("  " + "─" * 40)

        for i, step in enumerate(steps):
            step_type = step.get("type", "").lower()
            print(f"  Step {i+1}/{len(steps)}: {step_type} …", end=" ", flush=True)

            if step_type == "run":
                cmd = step.get("cmd", "")
                if not cmd:
                    print("SKIP (no cmd)")
                    log_lines.append(f"[step {i+1}] SKIP: no cmd")
                    continue
                rc, out, err = self.adapter.run(cmd, capture=True, timeout=120)
                status = "OK" if rc == 0 else f"FAIL (code {rc})"
                print(status)
                log_lines.append(f"[step {i+1}] run: {cmd}")
                log_lines.append(f"           status: {status}")
                if out:
                    log_lines.append(f"           stdout: {out.strip()}")
                if err:
                    log_lines.append(f"           stderr: {err.strip()}")

            elif step_type == "log":
                msg = step.get("message", "")
                print("OK")
                log_lines.append(f"[step {i+1}] log: {msg}")
                print(f"         {msg}")

            elif step_type == "sleep":
                secs = float(step.get("seconds", 1))
                time.sleep(secs)
                print(f"OK ({secs}s)")
                log_lines.append(f"[step {i+1}] sleep: {secs}s")

            elif step_type == "write":
                path = step.get("path", "")
                content = step.get("content", "")
                if path:
                    self.adapter.write_file(path, content)
                    print("OK")
                    log_lines.append(f"[step {i+1}] write: {path}")
                else:
                    print("SKIP (no path)")

            else:
                print(f"UNKNOWN step type '{step_type}'")
                log_lines.append(f"[step {i+1}] unknown: {step_type}")

        log_lines.append("")
        log_lines.append(f"Finished: {datetime.now().isoformat()}")
        try:
            log_file.write_text("\n".join(log_lines))
            print(f"\n  Log: {log_file}\n")
        except Exception:
            print()

    def create_task(self, name: str):
        """Create a new task template."""
        task_file = self._tasks_dir / f"{name}.json"
        if task_file.exists():
            print(f"[auto] Task '{name}' already exists: {task_file}")
            return

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
