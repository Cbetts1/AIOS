"""
Core Command Engine
Parses CLI input, resolves commands via the registry, and dispatches them.
All commands are routed through the Environment Abstraction Layer.

.. deprecated::
    This legacy ``core/`` package is superseded by ``aura_os/engine/``.
    The canonical implementation is at ``aura_os.engine``.
    New code should import from ``aura_os.engine`` instead.
"""

import sys
import json
from pathlib import Path

from core.registry import CommandRegistry
from eal import load_env_map, get_adapter


class CommandEngine:
    """
    Central dispatcher for all AURA commands.

    Usage:
        engine = CommandEngine()
        engine.run(["sys", "info"])
    """

    def __init__(self):
        self.env_map = load_env_map()
        self.adapter = get_adapter(self.env_map)
        self.registry = CommandRegistry()
        self._register_builtin_commands()

    # ------------------------------------------------------------------ #
    # Public interface
    # ------------------------------------------------------------------ #

    def run(self, argv: list):
        """
        Parse *argv* and dispatch to the appropriate handler.
        argv should NOT include the program name (sys.argv[0]).
        """
        if not argv:
            self._cmd_help([], {})
            return

        # Build context dict passed to every handler
        ctx = {
            "env": self.env_map,
            "adapter": self.adapter,
            "engine": self,
        }

        # Top-level command is first token; sub-command may follow
        command = argv[0].lower()
        args = argv[1:]

        # Compound command: "sys info" → try "sys info" then "sys"
        compound = f"{command} {args[0]}" if args else command
        entry = self.registry.get(compound) or self.registry.get(command)

        if entry is None:
            print(f"[aura] Unknown command: '{command}'. Run 'aura help' for usage.")
            return

        try:
            entry["handler"](args, ctx)
        except KeyboardInterrupt:
            print("\n[aura] Interrupted.")
        except Exception as exc:
            print(f"[aura] Error: {exc}")

    # ------------------------------------------------------------------ #
    # Built-in command registration
    # ------------------------------------------------------------------ #

    def _register_builtin_commands(self):
        r = self.registry

        r.register("help", self._cmd_help, "Show this help message", "aura help")
        r.register("sys", self._cmd_sys, "System commands", "aura sys <info|caps>")
        r.register("run", self._cmd_run, "Run a file or script", "aura run <file>")
        r.register("ai", self._cmd_ai, "Query the offline AI assistant", 'aura ai "<prompt>"')
        r.register("repo", self._cmd_repo, "Repository management", "aura repo <create|list|status> [name]")
        r.register("fs", self._cmd_fs, "File system operations", "aura fs <ls|cat|edit|find> [path]")
        r.register("auto", self._cmd_auto, "Automation engine", "aura auto <run|list> [task]")
        r.register("ui", self._cmd_ui, "Launch web or terminal UI", "aura ui [web|term]")
        r.register("env", self._cmd_env, "Show detected environment", "aura env")
        r.register("reload", self._cmd_reload, "Reload environment detection", "aura reload")
        r.register("pkg", self._cmd_pkg, "Package management", "aura pkg <install|remove|list|search|catalog|info> [name]")
        r.register("ps", self._cmd_ps, "List running processes", "aura ps")
        r.register("kill", self._cmd_kill, "Terminate a process by PID", "aura kill <pid>")
        r.register("top", self._cmd_top, "Top resource-consuming processes", "aura top")
        r.register("jobs", self._cmd_jobs, "List AURA background jobs", "aura jobs")
        r.register("shell", self._cmd_shell, "Start interactive AURA shell", "aura shell")

    # ------------------------------------------------------------------ #
    # Built-in handlers
    # ------------------------------------------------------------------ #

    def _cmd_help(self, args, ctx):
        print("\n  AURA OS — Adaptive User-space Runtime Architecture")
        print("  " + "─" * 50)
        for name, entry in sorted(self.registry.all_commands().items()):
            pad = 20
            print(f"  {entry['usage']:<{pad}}  {entry['description']}")
        print()

    def _cmd_sys(self, args, ctx):
        sub = args[0].lower() if args else "info"

        if sub == "info":
            env = ctx["env"]
            adapter = ctx["adapter"]
            print("\n  AURA OS — System Information")
            print("  " + "─" * 40)
            print(f"  Environment : {env['env_type']}")
            print(f"  Termux      : {env['is_termux']}")
            print(f"  RAM         : {env['ram_mb']} MB" if env["ram_mb"] else "  RAM         : unknown")
            print(f"  Storage root: {env['storage_root']}")
            print(f"  Network     : {'yes' if env['has_network'] else 'no'}")
            try:
                si = adapter.storage_info()
                print(f"  Disk free   : {si['free_mb']} MB / {si['total_mb']} MB")
            except Exception:
                pass
            print(f"  Python      : {env['python']}")
            print()

        elif sub == "caps":
            env = ctx["env"]
            print("\n  Capabilities:")
            for cap in sorted(env.get("capabilities", [])):
                print(f"    ✓ {cap}")
            print()

        else:
            print(f"[aura sys] Unknown sub-command '{sub}'. Use: info, caps")

    def _cmd_run(self, args, ctx):
        if not args:
            print("[aura run] Usage: aura run <file>")
            return

        target = Path(args[0])
        if not target.exists():
            print(f"[aura run] File not found: {target}")
            return

        adapter = ctx["adapter"]
        suffix = target.suffix.lower()
        py = ctx["env"].get("python", "python3")

        if suffix == ".py":
            cmd = [py, str(target)] + args[1:]
        elif suffix in (".sh", ".bash"):
            cmd = ["bash", str(target)] + args[1:]
        elif suffix == ".js":
            node = adapter.which("node")
            if not node:
                print("[aura run] Node.js not found.")
                return
            cmd = [node, str(target)] + args[1:]
        else:
            # Try executing directly
            cmd = [str(target)] + args[1:]

        rc, out, err = adapter.run(cmd, capture=False)
        if rc != 0 and err:
            print(f"[aura run] Process exited with code {rc}")

    def _cmd_ai(self, args, ctx):
        if not args:
            print('[aura ai] Usage: aura ai "<prompt>"')
            return

        prompt = " ".join(args)

        try:
            from modules.ai import AIModule
            ai = AIModule(ctx["env"], ctx["adapter"])
            response = ai.query(prompt)
            print(f"\n  AI > {response}\n")
        except Exception as e:
            print(f"[aura ai] Error: {e}")

    def _cmd_repo(self, args, ctx):
        if not args:
            print("[aura repo] Usage: aura repo <create|list|status|clone> [name]")
            return

        sub = args[0].lower()
        rest = args[1:]

        try:
            from modules.repo import RepoModule
            repo = RepoModule(ctx["env"], ctx["adapter"])
            if sub == "create":
                name = rest[0] if rest else "my-repo"
                repo.create(name)
            elif sub == "list":
                repo.list_repos()
            elif sub == "status":
                path = rest[0] if rest else "."
                repo.status(path)
            elif sub == "clone":
                url = rest[0] if rest else None
                if not url:
                    print("[aura repo] Usage: aura repo clone <url>")
                    return
                repo.clone(url, rest[1] if len(rest) > 1 else None)
            else:
                print(f"[aura repo] Unknown sub-command '{sub}'")
        except Exception as e:
            print(f"[aura repo] Error: {e}")

    def _cmd_fs(self, args, ctx):
        if not args:
            print("[aura fs] Usage: aura fs <ls|cat|edit|find|mkdir|rm> [path]")
            return

        sub = args[0].lower()
        path = args[1] if len(args) > 1 else "."

        try:
            from core.filesystem import FileSystemManager
            fsm = FileSystemManager(ctx["adapter"])
            if sub == "ls":
                fsm.ls(path)
            elif sub == "cat":
                fsm.cat(path)
            elif sub == "find":
                fsm.find(path, args[2] if len(args) > 2 else "")
            elif sub == "mkdir":
                fsm.mkdir(path)
            elif sub == "rm":
                fsm.rm(path)
            elif sub == "edit":
                fsm.edit(path)
            else:
                print(f"[aura fs] Unknown sub-command '{sub}'")
        except Exception as e:
            print(f"[aura fs] Error: {e}")

    def _cmd_auto(self, args, ctx):
        if not args:
            print("[aura auto] Usage: aura auto <run|list|create> [task]")
            return

        sub = args[0].lower()
        rest = args[1:]

        try:
            from modules.automation import AutomationModule
            auto = AutomationModule(ctx["env"], ctx["adapter"])
            if sub == "run":
                task = rest[0] if rest else None
                auto.run_task(task)
            elif sub == "list":
                auto.list_tasks()
            elif sub == "create":
                name = rest[0] if rest else "my-task"
                auto.create_task(name)
            else:
                print(f"[aura auto] Unknown sub-command '{sub}'")
        except Exception as e:
            print(f"[aura auto] Error: {e}")

    def _cmd_ui(self, args, ctx):
        mode = args[0].lower() if args else None
        caps = ctx["env"].get("capabilities", [])

        use_web = (mode == "web") or (mode is None and "web_ui" in caps and "flask" in caps)

        if use_web:
            try:
                from modules.browser import BrowserModule
                bm = BrowserModule(ctx["env"], ctx["adapter"])
                bm.start_web()
                return
            except Exception as e:
                print(f"[aura ui] Web UI failed ({e}), falling back to terminal UI")

        # Terminal dashboard
        try:
            from modules.browser import BrowserModule
            bm = BrowserModule(ctx["env"], ctx["adapter"])
            bm.start_terminal()
        except Exception as e:
            print(f"[aura ui] Error: {e}")

    def _cmd_env(self, args, ctx):
        print(json.dumps(ctx["env"], indent=2))

    def _cmd_reload(self, args, ctx):
        self.env_map = load_env_map()
        self.adapter = get_adapter(self.env_map)
        print("[aura] Environment reloaded.")

    # ------------------------------------------------------------------ #
    # Package management
    # ------------------------------------------------------------------ #

    def _cmd_pkg(self, args, ctx):
        if not args:
            print("[aura pkg] Usage: aura pkg <install|remove|list|search|catalog|info> [name]")
            return

        sub = args[0].lower()
        rest = args[1:]

        try:
            from modules.pkg import PkgModule
            pkg = PkgModule(ctx["env"], ctx["adapter"])
            if sub == "install":
                if not rest:
                    print("[aura pkg] Usage: aura pkg install <package>")
                    return
                pkg.install(rest[0])
            elif sub == "remove":
                if not rest:
                    print("[aura pkg] Usage: aura pkg remove <package>")
                    return
                pkg.remove(rest[0])
            elif sub == "list":
                pkg.list_installed()
            elif sub == "search":
                query = rest[0] if rest else ""
                pkg.search(query)
            elif sub == "catalog":
                pkg.catalog()
            elif sub == "info":
                if not rest:
                    print("[aura pkg] Usage: aura pkg info <package>")
                    return
                pkg.info(rest[0])
            else:
                print(f"[aura pkg] Unknown sub-command '{sub}'")
        except Exception as e:
            print(f"[aura pkg] Error: {e}")

    # ------------------------------------------------------------------ #
    # Process management
    # ------------------------------------------------------------------ #

    def _cmd_ps(self, args, ctx):
        try:
            from modules.process import ProcessModule
            pm = ProcessModule(ctx["env"], ctx["adapter"])
            pm.ps()
        except Exception as e:
            print(f"[aura ps] Error: {e}")

    def _cmd_kill(self, args, ctx):
        if not args:
            print("[aura kill] Usage: aura kill <pid> [signal]")
            return
        try:
            pid = int(args[0])
            sig = int(args[1]) if len(args) > 1 else 15
            from modules.process import ProcessModule
            pm = ProcessModule(ctx["env"], ctx["adapter"])
            pm.kill(pid, sig)
        except ValueError:
            print("[aura kill] PID must be an integer.")
        except Exception as e:
            print(f"[aura kill] Error: {e}")

    def _cmd_top(self, args, ctx):
        try:
            from modules.process import ProcessModule
            pm = ProcessModule(ctx["env"], ctx["adapter"])
            pm.top()
        except Exception as e:
            print(f"[aura top] Error: {e}")

    def _cmd_jobs(self, args, ctx):
        try:
            from modules.process import ProcessModule
            pm = ProcessModule(ctx["env"], ctx["adapter"])
            pm.jobs()
        except Exception as e:
            print(f"[aura jobs] Error: {e}")

    # ------------------------------------------------------------------ #
    # Interactive shell
    # ------------------------------------------------------------------ #

    def _cmd_shell(self, args, ctx):
        try:
            from modules.shell import ShellModule
            sh = ShellModule(ctx["env"], ctx["adapter"])
            sh.start()
        except Exception as e:
            print(f"[aura shell] Error: {e}")
