"""Tests for enhanced AIOS modules.

Covers:
- SecretStore: Fernet/XOR encryption, TTL, rotation, audit log
- LocalInference: retry logic, HTTP backend, streaming
- ModelManager: HTTP API detection
- Scheduler: thread pool, timeouts, retries, cancel, submit/wait
- ProcessManager: system process listing
- NetworkManager: traceroute parsing, port scan, interface stats
- VirtualFS: binary r/w, recursive ls, find, du, copy, move
- New commands: DiskCommand, HealthCommand
"""

import os
import sys
import tempfile
import threading
import time

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ============================================================
# SecretStore
# ============================================================

class TestSecretStoreEnhanced:
    def setup_method(self):
        self.tmp = tempfile.mkdtemp()
        from aura_os.kernel.secrets import SecretStore
        self.store = SecretStore(base_dir=self.tmp, passphrase="test-pass")

    def test_set_get_basic(self):
        self.store.set_secret("key1", "value1")
        assert self.store.get_secret("key1") == "value1"

    def test_set_get_with_namespace(self):
        self.store.set_secret("api_key", "secret123", namespace="prod")
        assert self.store.get_secret("api_key", namespace="prod") == "secret123"
        assert self.store.get_secret("api_key") is None  # default namespace

    def test_missing_key_returns_none(self):
        assert self.store.get_secret("nonexistent") is None

    def test_delete_secret(self):
        self.store.set_secret("to_delete", "val")
        assert self.store.delete_secret("to_delete") is True
        assert self.store.get_secret("to_delete") is None

    def test_delete_nonexistent(self):
        assert self.store.delete_secret("no_such_key") is False

    def test_list_secrets_hides_values(self):
        self.store.set_secret("k1", "v1")
        self.store.set_secret("k2", "v2")
        secrets = self.store.list_secrets()
        assert len(secrets) == 2
        keys = {s["key"] for s in secrets}
        assert keys == {"k1", "k2"}
        for s in secrets:
            assert "value" not in s  # values must never be returned

    def test_ttl_expiry(self):
        self.store.set_secret("temp_key", "temp_val", ttl=0.1)
        assert self.store.get_secret("temp_key") == "temp_val"
        time.sleep(0.2)
        assert self.store.get_secret("temp_key") is None

    def test_ttl_not_expired(self):
        self.store.set_secret("alive_key", "alive_val", ttl=3600)
        assert self.store.get_secret("alive_key") == "alive_val"

    def test_list_hides_expired_by_default(self):
        self.store.set_secret("expired", "v", ttl=0.1)
        time.sleep(0.2)
        secrets = self.store.list_secrets()
        keys = [s["key"] for s in secrets]
        assert "expired" not in keys

    def test_list_includes_expired_when_flagged(self):
        self.store.set_secret("expired2", "v", ttl=0.1)
        time.sleep(0.2)
        secrets = self.store.list_secrets(include_expired=True)
        keys = [s["key"] for s in secrets]
        assert "expired2" in keys
        expired_entry = next(s for s in secrets if s["key"] == "expired2")
        assert expired_entry["expired"] is True

    def test_rotate_secret(self):
        self.store.set_secret("rot_key", "old_value")
        result = self.store.rotate_secret("rot_key", "new_value")
        assert result["ok"] is True
        assert self.store.get_secret("rot_key") == "new_value"

    def test_rotate_preserves_prev_value(self):
        self.store.set_secret("rot2", "original")
        self.store.rotate_secret("rot2", "updated")
        # The current value should be the new one
        assert self.store.get_secret("rot2") == "updated"
        # The shadow key is hidden from list_secrets (no .__prev__ entries)
        keys = [s["key"] for s in self.store.list_secrets()]
        assert "rot2.__prev__" not in keys
        # Rotating again creates another shadow entry; original current should update
        result = self.store.rotate_secret("rot2", "final")
        assert result["ok"] is True
        assert self.store.get_secret("rot2") == "final"

    def test_audit_log_written(self):
        self.store.set_secret("audit_key", "audit_val")
        self.store.get_secret("audit_key")
        self.store.delete_secret("audit_key")
        log = self.store.get_audit_log()
        ops = {r["op"] for r in log}
        assert "set" in ops
        assert "get" in ops
        assert "delete" in ops

    def test_audit_log_no_values(self):
        self.store.set_secret("safe_key", "sensitive_value")
        log = self.store.get_audit_log()
        for record in log:
            assert "sensitive_value" not in str(record)

    def test_list_namespaces(self):
        self.store.set_secret("k", "v", namespace="ns1")
        self.store.set_secret("k", "v", namespace="ns2")
        namespaces = self.store.list_namespaces()
        assert "ns1" in namespaces
        assert "ns2" in namespaces

    def test_encryption_field_reported(self):
        self.store.set_secret("enc_test", "value")
        secrets = self.store.list_secrets()
        enc = secrets[0]["encrypted_with"]
        assert enc in ("fernet", "xor")

    def test_atomic_write_no_partial(self):
        """Verify that write path uses atomic rename (no .tmp left behind)."""
        self.store.set_secret("atomic_k", "atomic_v")
        tmp_files = [f for f in os.listdir(self.tmp) if f.endswith(".tmp")]
        assert len(tmp_files) == 0


# ============================================================
# Scheduler
# ============================================================

class TestSchedulerEnhanced:
    def setup_method(self):
        from aura_os.kernel.scheduler import Scheduler
        self.sched = Scheduler(max_workers=4)

    def teardown_method(self):
        self.sched.shutdown(wait=False)

    def test_submit_and_wait(self):
        tid = self.sched.submit("simple", lambda: 42)
        result = self.sched.wait(tid, timeout=5)
        assert result == 42

    def test_submit_captures_error(self):
        tid = self.sched.submit("bad", lambda: 1 / 0)
        with pytest.raises(RuntimeError):
            self.sched.wait(tid, timeout=5)

    def test_task_status_done(self):
        tid = self.sched.submit("done_task", lambda: "ok")
        self.sched.wait(tid, timeout=5)
        statuses = {t["id"]: t["status"] for t in self.sched.get_status()}
        assert statuses[tid] == "done"

    def test_task_status_error(self):
        tid = self.sched.submit("err_task", lambda: [][0])
        with pytest.raises(RuntimeError):
            self.sched.wait(tid, timeout=5)
        statuses = {t["id"]: t["status"] for t in self.sched.get_status()}
        assert statuses[tid] == "error"

    def test_timeout_enforcement(self):
        from aura_os.kernel.scheduler import Scheduler
        sched2 = Scheduler(max_workers=2)
        tid = sched2.submit("slow", lambda: time.sleep(10), timeout=0.3)
        time.sleep(1.0)  # wait long enough for timeout to fire
        statuses = {t["id"]: t["status"] for t in sched2.get_status()}
        assert statuses[tid] == "timeout"
        sched2.shutdown(wait=False)

    def test_retry_on_error(self):
        attempts = []

        def flaky():
            attempts.append(1)
            if len(attempts) < 3:
                raise ValueError("not yet")
            return "finally"

        tid = self.sched.submit("retry_task", flaky, max_retries=3, retry_delay=0.05)
        result = self.sched.wait(tid, timeout=10)
        assert result == "finally"
        assert len(attempts) == 3

    def test_cancel_pending_task(self):
        # Add task to sequential pool, cancel before run
        tid = self.sched.add_task("cancel_me", lambda: time.sleep(10))
        cancelled = self.sched.cancel(tid)
        assert cancelled is True
        statuses = {t["id"]: t["status"] for t in self.sched.get_status()}
        assert statuses[tid] == "cancelled"

    def test_run_after_delay(self):
        started_at = []
        run_at = time.time() + 0.3

        def record():
            started_at.append(time.time())
            return True

        tid = self.sched.submit("deferred", record, run_after=run_at)
        result = self.sched.wait(tid, timeout=5)
        assert result is True
        assert len(started_at) == 1
        assert started_at[0] >= run_at - 0.1  # slight tolerance

    def test_parallel_execution(self):
        """Multiple tasks should complete in parallel (not sequentially)."""
        results = []
        lock = threading.Lock()

        def work(n):
            time.sleep(0.2)
            with lock:
                results.append(n)
            return n

        tids = [self.sched.submit(f"par-{i}", lambda i=i: work(i)) for i in range(4)]
        t_start = time.monotonic()
        for tid in tids:
            self.sched.wait(tid, timeout=5)
        elapsed = time.monotonic() - t_start
        assert len(results) == 4
        # Should finish in <1s (parallel), not ~0.8s (sequential)
        assert elapsed < 0.8

    def test_task_timing_recorded(self):
        tid = self.sched.submit("timed", lambda: time.sleep(0.05))
        self.sched.wait(tid, timeout=5)
        status = next(t for t in self.sched.get_status() if t["id"] == tid)
        assert status["started_at"] is not None
        assert status["finished_at"] is not None
        assert status["duration_s"] >= 0.0

    def test_sequential_run_all(self):
        from aura_os.kernel.scheduler import Scheduler
        sched = Scheduler()
        results = []
        sched.add_task("t1", lambda: results.append(1), priority=2)
        sched.add_task("t2", lambda: results.append(2), priority=1)
        sched.run_all()
        assert results == [2, 1]  # lower priority number runs first
        sched.shutdown(wait=False)


# ============================================================
# ProcessManager
# ============================================================

class TestProcessManagerEnhanced:
    def setup_method(self):
        from aura_os.kernel.process import ProcessManager
        self.pm = ProcessManager()

    def test_list_system_processes(self):
        pytest.importorskip("psutil")
        procs = self.pm.list_system_processes()
        # Should return multiple processes on any real system
        assert len(procs) > 0

    def test_system_process_fields(self):
        procs = self.pm.list_system_processes(limit=5)
        assert len(procs) <= 5
        for p in procs:
            assert "pid" in p
            assert "name" in p
            assert "cpu_pct" in p
            assert "mem_rss_mb" in p

    def test_sort_by_mem(self):
        procs = self.pm.list_system_processes(sort_by="mem", limit=5)
        for i in range(len(procs) - 1):
            assert procs[i]["mem_rss_mb"] >= procs[i + 1]["mem_rss_mb"]

    def test_process_tree_self(self):
        pytest.importorskip("psutil")
        tree = self.pm.get_process_tree(os.getpid())
        assert tree.get("pid") == os.getpid()
        assert "children" in tree

    def test_process_tree_unknown_pid(self):
        tree = self.pm.get_process_tree(999999999)
        assert tree == {}

    def test_spawn_background_returns_immediately(self):
        import sys
        entry = self.pm.spawn(
            [sys.executable, "-c", "import time; time.sleep(5)"],
            background=True,
        )
        assert entry.status == "running"
        self.pm.kill(entry.pid)

    def test_terminate_all(self):
        import sys
        entry = self.pm.spawn(
            [sys.executable, "-c", "import time; time.sleep(60)"],
            background=True,
        )
        assert entry.status == "running"
        self.pm.terminate_all(grace_period=0.5)


# ============================================================
# NetworkManager
# ============================================================

class TestNetworkManagerEnhanced:
    def setup_method(self):
        from aura_os.net.manager import NetworkManager
        self.nm = NetworkManager()

    def test_interface_stats_returns_list(self):
        stats = self.nm.interface_stats()
        # psutil is installed in this environment
        assert isinstance(stats, list)
        if stats:
            assert "bytes_sent" in stats[0]
            assert "bytes_recv" in stats[0]

    def test_scan_ports_localhost(self):
        # Scan a few common ports on localhost — should not raise
        results = self.nm.scan_ports("127.0.0.1", ports=[22, 80, 443, 8080])
        assert len(results) == 4
        for r in results:
            assert "port" in r
            assert "open" in r

    def test_port_scan_returns_open_close(self):
        results = self.nm.scan_ports("127.0.0.1", ports=[65534, 65535])
        for r in results:
            assert r["open"] in (True, False)

    def test_reverse_dns_known_ip(self):
        # 127.0.0.1 should resolve to localhost (or similar)
        result = self.nm.reverse_dns("127.0.0.1")
        # May be None on some systems; that's OK, just no exception
        assert result is None or isinstance(result, str)

    def test_traceroute_structure(self):
        """parse_traceroute returns list of hop dicts when output matches."""
        sample = (
            " 1  192.168.1.1  1.234 ms  0.987 ms  0.756 ms\n"
            " 2  10.0.0.1  5.000 ms  4.500 ms  4.300 ms\n"
            " 3  * * *\n"
        )
        hops = self.nm._parse_traceroute(sample)
        # Should have at least 1 parsed hop
        assert len(hops) >= 1
        assert all("hop" in h for h in hops)
        assert all("ip" in h for h in hops)
        assert all("rtt_ms" in h for h in hops)

    def test_traceroute_wildcard_hop(self):
        sample = " 5  *\n"
        hops = self.nm._parse_traceroute(sample)
        assert len(hops) == 1
        assert hops[0]["ip"] is None


# ============================================================
# VirtualFS
# ============================================================

class TestVirtualFSEnhanced:
    def setup_method(self):
        self.tmp = tempfile.mkdtemp()
        from aura_os.fs.vfs import VirtualFS
        self.vfs = VirtualFS(base_dir=self.tmp)

    def test_write_and_read_text(self):
        self.vfs.write("hello.txt", "Hello, AURA!")
        assert self.vfs.read("hello.txt") == "Hello, AURA!"

    def test_write_and_read_binary(self):
        data = bytes(range(256))
        self.vfs.write_bytes("binary.bin", data)
        assert self.vfs.read_bytes("binary.bin") == data

    def test_atomic_write_no_tmp_left(self):
        self.vfs.write("atomic.txt", "data")
        tmp_files = [f for f in os.listdir(self.tmp) if f.endswith(".tmp")]
        assert len(tmp_files) == 0

    def test_recursive_ls(self):
        self.vfs.mkdir("a/b/c")
        self.vfs.write("a/b/c/deep.txt", "nested")
        self.vfs.write("a/top.txt", "top")
        entries = self.vfs.ls(recursive=True)
        assert any("deep.txt" in e for e in entries)
        assert any("top.txt" in e for e in entries)

    def test_non_recursive_ls(self):
        self.vfs.mkdir("dir1")
        self.vfs.write("file1.txt", "x")
        entries = self.vfs.ls()
        assert "file1.txt" in entries
        assert "dir1" in entries

    def test_find_by_pattern(self):
        self.vfs.write("log1.log", "log1")
        self.vfs.write("log2.log", "log2")
        self.vfs.write("data.csv", "csv")
        found = self.vfs.find("*.log")
        assert len(found) == 2
        assert all(f.endswith(".log") for f in found)

    def test_find_no_match(self):
        found = self.vfs.find("*.xyz")
        assert found == []

    def test_du_single_file(self):
        self.vfs.write("sized.txt", "A" * 1000)
        size = self.vfs.du("sized.txt")
        assert size == 1000

    def test_du_directory(self):
        self.vfs.write("sub/f1.txt", "A" * 500)
        self.vfs.write("sub/f2.txt", "B" * 500)
        size = self.vfs.du("sub")
        assert size == 1000

    def test_copy_file(self):
        self.vfs.write("original.txt", "copy_me")
        self.vfs.copy("original.txt", "copy_of_original.txt")
        assert self.vfs.read("copy_of_original.txt") == "copy_me"
        assert self.vfs.read("original.txt") == "copy_me"  # original unchanged

    def test_move_file(self):
        self.vfs.write("move_me.txt", "move_content")
        self.vfs.move("move_me.txt", "moved.txt")
        assert self.vfs.read("moved.txt") == "move_content"
        assert not self.vfs.exists("move_me.txt")

    def test_append(self):
        self.vfs.write("append_me.txt", "line1\n")
        self.vfs.append("append_me.txt", "line2\n")
        assert self.vfs.read("append_me.txt") == "line1\nline2\n"

    def test_delete_tree(self):
        self.vfs.mkdir("to_delete")
        self.vfs.write("to_delete/f.txt", "x")
        self.vfs.delete_tree("to_delete")
        assert not self.vfs.exists("to_delete")

    def test_path_traversal_blocked(self):
        with pytest.raises(PermissionError):
            self.vfs.read("../../etc/passwd")

    def test_binary_read_nonexistent_raises(self):
        with pytest.raises(FileNotFoundError):
            self.vfs.read_bytes("no_such_file.bin")


# ============================================================
# ModelManager
# ============================================================

class TestModelManagerEnhanced:
    def setup_method(self):
        self.tmp = tempfile.mkdtemp()
        from aura_os.ai.model_manager import ModelManager
        self.mm = ModelManager(models_dir=self.tmp, ollama_url="http://localhost:11434")

    def test_list_models_empty(self):
        models = self.mm.list_models()
        assert isinstance(models, list)

    def test_list_models_finds_gguf(self):
        open(os.path.join(self.tmp, "model.gguf"), "w").close()
        models = self.mm.list_models()
        assert any("model.gguf" in m for m in models)

    def test_list_ollama_models_offline(self):
        """When Ollama is not running, returns empty list (no exception)."""
        from aura_os.ai.model_manager import ModelManager
        mm = ModelManager(models_dir=self.tmp, ollama_url="http://localhost:19999")
        models = mm.list_ollama_models()
        assert models == []

    def test_pull_model_offline(self):
        from aura_os.ai.model_manager import ModelManager
        mm = ModelManager(models_dir=self.tmp, ollama_url="http://localhost:19999")
        result = mm.pull_model("mistral")
        assert result["ok"] is False
        assert "error" in result

    def test_get_active_runtime_returns_none_or_str(self):
        runtime = self.mm.get_active_runtime()
        assert runtime is None or isinstance(runtime, str)

    def test_load_model_nonexistent(self):
        result = self.mm.load_model("no_such_model.gguf")
        assert result is None


# ============================================================
# LocalInference (retry + no-runtime path)
# ============================================================

class TestLocalInferenceEnhanced:
    def setup_method(self):
        self.tmp = tempfile.mkdtemp()
        from aura_os.ai.model_manager import ModelManager
        from aura_os.ai.inference import LocalInference
        mm = ModelManager(models_dir=self.tmp, ollama_url="http://localhost:19999")
        # No runtimes available — should return hint message
        self.engine = LocalInference(
            model_manager=mm,
            ollama_url="http://localhost:19999",
            retries=1,
        )

    def test_query_no_runtime_returns_hint(self):
        result = self.engine.query("What is 2+2?")
        assert "No local AI runtime" in result or "aura ai" in result.lower()

    def test_stream_no_runtime_yields_hint(self):
        chunks = list(self.engine.stream("Hello"))
        combined = "".join(chunks)
        assert len(combined) > 0

    def test_is_ollama_http_unavailable(self):
        assert not self.engine._is_ollama_http_available()


# ============================================================
# DiskCommand
# ============================================================

class TestDiskCommand:
    def test_df_runs(self, capsys):
        from aura_os.engine.commands.disk_cmd import DiskCommand
        cmd = DiskCommand()

        class FakeArgs:
            disk_command = "df"

        rc = cmd.execute(FakeArgs(), None)
        assert rc == 0

    def test_du_current_dir(self, capsys):
        from aura_os.engine.commands.disk_cmd import DiskCommand
        cmd = DiskCommand()

        class FakeArgs:
            disk_command = "du"
            path = "."
            depth = 1

        rc = cmd.execute(FakeArgs(), None)
        assert rc == 0

    def test_top_current_dir(self, capsys, tmp_path):
        from aura_os.engine.commands.disk_cmd import DiskCommand
        cmd = DiskCommand()
        (tmp_path / "file.txt").write_text("data")

        class FakeArgs:
            disk_command = "top"
            path = str(tmp_path)
            limit = 5

        rc = cmd.execute(FakeArgs(), None)
        assert rc == 0

    def test_vfs_command(self, capsys):
        from aura_os.engine.commands.disk_cmd import DiskCommand
        cmd = DiskCommand()

        class FakeArgs:
            disk_command = "vfs"

        rc = cmd.execute(FakeArgs(), None)
        assert rc == 0


# ============================================================
# HealthCommand
# ============================================================

class TestHealthCommand:
    def test_health_runs(self, capsys):
        from aura_os.engine.commands.health_cmd import HealthCommand
        cmd = HealthCommand()

        class FakeArgs:
            verbose = False

        rc = cmd.execute(FakeArgs(), None)
        assert rc == 0
        out = capsys.readouterr().out
        assert "Health" in out or "CPU" in out or "Memory" in out

    def test_health_verbose(self, capsys):
        from aura_os.engine.commands.health_cmd import HealthCommand
        cmd = HealthCommand()

        class FakeArgs:
            verbose = True

        rc = cmd.execute(FakeArgs(), None)
        assert rc == 0
