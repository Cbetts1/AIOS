"""``aura cron`` command handler — periodic task scheduling."""


class CronCommand:
    """Cron job management: add, remove, list, enable, disable."""

    def execute(self, args, eal) -> int:
        from aura_os.kernel.cron import CronScheduler

        cron = CronScheduler()
        sub = getattr(args, "cron_command", None)

        if sub == "add":
            name = getattr(args, "name", "")
            schedule = getattr(args, "schedule", "")
            command = getattr(args, "cmd", "")
            job = cron.add_job(name, schedule, command)
            print(f"  ✓ Created job {job.id}: {job.name}")
            print(f"    Schedule: {job.schedule}")
            print(f"    Command : {job.command}")
            return 0

        if sub == "remove":
            jid = getattr(args, "id", "")
            if cron.remove_job(jid):
                print(f"  ✓ Removed job {jid}")
            else:
                print(f"  ✗ Job {jid} not found")
            return 0

        if sub == "enable":
            jid = getattr(args, "id", "")
            if cron.enable_job(jid):
                print(f"  ✓ Enabled job {jid}")
            else:
                print(f"  ✗ Job {jid} not found")
            return 0

        if sub == "disable":
            jid = getattr(args, "id", "")
            if cron.disable_job(jid):
                print(f"  ✓ Disabled job {jid}")
            else:
                print(f"  ✗ Job {jid} not found")
            return 0

        if sub == "list" or sub is None:
            jobs = cron.list_jobs()
            if not jobs:
                print("  No cron jobs defined")
                return 0
            for j in jobs:
                status = "✓" if j["enabled"] else "✗"
                print(f"  {status} {j['id']:<12} {j['name']:<20} "
                      f"{j['schedule']:<16} runs={j['run_count']}")
                if j["last_error"]:
                    print(f"    last error: {j['last_error']}")
            return 0

        return 0
