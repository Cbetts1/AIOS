"""Comprehensive knowledge base for the AURA OS AI assistant.

Provides structured documentation about:
  - AURA OS terminal commands and their usage
  - Common Linux commands organised by category
  - AURA OS codebase architecture and key functions

The knowledge is consumed by both the LLM system-prompt builder
(:func:`build_system_prompt`) and the rule-based fallback engine
(:func:`lookup`).
"""

from typing import Dict, List, Optional

# ──────────────────────────────────────────────────────────────────────────────
# 1. AURA OS Terminal Commands
# ──────────────────────────────────────────────────────────────────────────────

AURA_COMMANDS: Dict[str, Dict] = {
    "run": {
        "syntax": "aura run <file> [-- args...]",
        "description": "Execute a script file using the appropriate runtime.",
        "details": (
            "Automatically detects the runtime from the file extension and "
            "runs the script.  Supported extensions: .py (python3), .js (node), "
            ".sh (bash), .rb (ruby), .pl (perl), .php (php), .lua (lua), "
            ".r/.R (Rscript), .ts (ts-node), .go (go run).  "
            "If the extension is unknown but the file is executable, it runs "
            "directly (shebang support)."
        ),
        "examples": [
            "aura run hello.py",
            "aura run build.sh",
            "aura run app.js -- --port 3000",
        ],
    },
    "ai": {
        "syntax": 'aura ai "<prompt>" [--model NAME] [--max-tokens N]',
        "description": "Query a local AI model with a text prompt.",
        "details": (
            "Sends the prompt to the best available local AI runtime.  "
            "Priority: ollama → llama-cli (llama.cpp) → instructional fallback.  "
            "Use --model to override the default model.  "
            "Use --max-tokens to control response length (default 512)."
        ),
        "examples": [
            'aura ai "Explain Python decorators"',
            'aura ai "Write a bash loop" --max-tokens 256',
            'aura ai "Summarise this code" --model mistral',
        ],
    },
    "env": {
        "syntax": "aura env [--json]",
        "description": "Display environment information.",
        "details": (
            "Shows detected platform, available binaries, storage paths, "
            "permissions, and system information.  Use --json for "
            "machine-readable output."
        ),
        "examples": ["aura env", "aura env --json"],
    },
    "pkg": {
        "syntax": "aura pkg <sub-command> [args]",
        "description": "Package management (install, remove, list, search, info).",
        "details": (
            "Manages local AURA packages.  Sub-commands:\n"
            "  install <name|path>  — install a package from name or manifest\n"
            "  remove  <name>       — remove an installed package\n"
            "  list                 — list all installed packages\n"
            "  search <query>       — search the registry\n"
            "  info   <name>        — show package details"
        ),
        "examples": [
            "aura pkg install my-tool",
            "aura pkg remove my-tool",
            "aura pkg list",
            "aura pkg search editor",
            "aura pkg info my-tool",
        ],
    },
    "sys": {
        "syntax": "aura sys [--watch]",
        "description": "Show system status (CPU, memory, platform).",
        "details": (
            "Displays a snapshot of the current system status.  "
            "Use --watch to refresh every 2 seconds."
        ),
        "examples": ["aura sys", "aura sys --watch"],
    },
    "shell": {
        "syntax": "aura shell",
        "description": "Launch the AURA interactive REPL shell.",
        "details": (
            "Opens an interactive prompt (aura> ) where you can type any "
            "AURA command without the 'aura' prefix.  Supports readline "
            "history saved to ~/.aura/data/.history.  Type 'exit' or "
            "press Ctrl-D to quit."
        ),
        "examples": ["aura shell"],
    },
}


# ──────────────────────────────────────────────────────────────────────────────
# 2. Linux Commands Reference
# ──────────────────────────────────────────────────────────────────────────────

LINUX_COMMANDS: Dict[str, Dict[str, List[Dict]]] = {
    "File Management": {
        "description": "Commands for creating, viewing, copying, and managing files and directories.",
        "commands": [
            {"name": "ls", "syntax": "ls [options] [path]", "description": "List directory contents.", "examples": ["ls -la", "ls -lh /var/log"]},
            {"name": "cd", "syntax": "cd <directory>", "description": "Change the current working directory.", "examples": ["cd /home/user", "cd ..", "cd ~"]},
            {"name": "pwd", "syntax": "pwd", "description": "Print the current working directory path.", "examples": ["pwd"]},
            {"name": "mkdir", "syntax": "mkdir [options] <dir>", "description": "Create directories.", "examples": ["mkdir mydir", "mkdir -p a/b/c"]},
            {"name": "rmdir", "syntax": "rmdir <dir>", "description": "Remove empty directories.", "examples": ["rmdir emptydir"]},
            {"name": "rm", "syntax": "rm [options] <file>", "description": "Remove files or directories.", "examples": ["rm file.txt", "rm -rf old_dir"]},
            {"name": "cp", "syntax": "cp [options] <src> <dst>", "description": "Copy files and directories.", "examples": ["cp file.txt backup.txt", "cp -r src/ dst/"]},
            {"name": "mv", "syntax": "mv <src> <dst>", "description": "Move or rename files and directories.", "examples": ["mv old.txt new.txt", "mv file.txt /tmp/"]},
            {"name": "touch", "syntax": "touch <file>", "description": "Create an empty file or update timestamps.", "examples": ["touch newfile.txt"]},
            {"name": "find", "syntax": "find <path> [expressions]", "description": "Search for files in a directory hierarchy.", "examples": ["find / -name '*.py'", "find . -type f -mtime -7"]},
            {"name": "locate", "syntax": "locate <pattern>", "description": "Find files by name using a pre-built index.", "examples": ["locate myfile.conf"]},
            {"name": "ln", "syntax": "ln [options] <target> <link>", "description": "Create hard or symbolic links.", "examples": ["ln -s /path/to/file link_name"]},
            {"name": "stat", "syntax": "stat <file>", "description": "Display detailed file status.", "examples": ["stat myfile.txt"]},
            {"name": "file", "syntax": "file <file>", "description": "Determine file type.", "examples": ["file image.png"]},
        ],
    },
    "File Viewing & Editing": {
        "description": "Commands for reading and editing file contents.",
        "commands": [
            {"name": "cat", "syntax": "cat [files]", "description": "Concatenate and display file contents.", "examples": ["cat file.txt", "cat file1 file2 > combined"]},
            {"name": "less", "syntax": "less <file>", "description": "View file contents with paging.", "examples": ["less /var/log/syslog"]},
            {"name": "more", "syntax": "more <file>", "description": "View file contents page by page.", "examples": ["more largefile.txt"]},
            {"name": "head", "syntax": "head [-n N] <file>", "description": "Display the first N lines (default 10).", "examples": ["head -n 20 file.txt"]},
            {"name": "tail", "syntax": "tail [-n N] [-f] <file>", "description": "Display the last N lines; -f follows new output.", "examples": ["tail -n 50 app.log", "tail -f /var/log/syslog"]},
            {"name": "nano", "syntax": "nano <file>", "description": "Simple terminal text editor.", "examples": ["nano config.yaml"]},
            {"name": "vi/vim", "syntax": "vim <file>", "description": "Powerful modal text editor.", "examples": ["vim script.py"]},
            {"name": "wc", "syntax": "wc [options] <file>", "description": "Count lines, words, and characters.", "examples": ["wc -l file.txt"]},
            {"name": "diff", "syntax": "diff <file1> <file2>", "description": "Compare files line by line.", "examples": ["diff old.txt new.txt"]},
            {"name": "sort", "syntax": "sort [options] <file>", "description": "Sort lines of text.", "examples": ["sort names.txt", "sort -n numbers.txt"]},
            {"name": "uniq", "syntax": "uniq [options] <file>", "description": "Report or omit repeated lines.", "examples": ["sort data | uniq -c"]},
            {"name": "cut", "syntax": "cut [options] <file>", "description": "Remove sections from each line.", "examples": ["cut -d',' -f1,3 data.csv"]},
            {"name": "awk", "syntax": "awk '<program>' [file]", "description": "Pattern scanning and processing language.", "examples": ["awk '{print $1}' file.txt", "awk -F: '{print $1}' /etc/passwd"]},
            {"name": "sed", "syntax": "sed '<script>' [file]", "description": "Stream editor for transforming text.", "examples": ["sed 's/old/new/g' file.txt", "sed -i '5d' file.txt"]},
        ],
    },
    "Text Search": {
        "description": "Commands for searching text patterns within files.",
        "commands": [
            {"name": "grep", "syntax": "grep [options] <pattern> [files]", "description": "Search for patterns in files.", "examples": ["grep -r 'TODO' src/", "grep -i 'error' log.txt", "grep -n 'def ' *.py"]},
            {"name": "egrep", "syntax": "egrep <pattern> [files]", "description": "Extended regex grep (same as grep -E).", "examples": ["egrep '(error|warn)' app.log"]},
            {"name": "fgrep", "syntax": "fgrep <string> [files]", "description": "Fixed-string grep (same as grep -F).", "examples": ["fgrep 'exact text' file.txt"]},
        ],
    },
    "File Permissions & Ownership": {
        "description": "Commands for managing file permissions and ownership.",
        "commands": [
            {"name": "chmod", "syntax": "chmod <mode> <file>", "description": "Change file permissions.", "examples": ["chmod 755 script.sh", "chmod +x run.sh", "chmod u+rw,go-w file"]},
            {"name": "chown", "syntax": "chown <user[:group]> <file>", "description": "Change file owner and group.", "examples": ["chown root:root /etc/config", "chown -R user:group dir/"]},
            {"name": "chgrp", "syntax": "chgrp <group> <file>", "description": "Change group ownership.", "examples": ["chgrp developers project/"]},
            {"name": "umask", "syntax": "umask [mask]", "description": "Set default file creation permissions.", "examples": ["umask 022"]},
        ],
    },
    "Process Management": {
        "description": "Commands for managing running processes.",
        "commands": [
            {"name": "ps", "syntax": "ps [options]", "description": "Display current processes.", "examples": ["ps aux", "ps -ef", "ps aux | grep python"]},
            {"name": "top", "syntax": "top", "description": "Interactive process viewer (real-time).", "examples": ["top"]},
            {"name": "htop", "syntax": "htop", "description": "Enhanced interactive process viewer.", "examples": ["htop"]},
            {"name": "kill", "syntax": "kill [-signal] <PID>", "description": "Send a signal to a process.", "examples": ["kill 1234", "kill -9 1234", "kill -SIGTERM 1234"]},
            {"name": "killall", "syntax": "killall <name>", "description": "Kill processes by name.", "examples": ["killall firefox"]},
            {"name": "bg", "syntax": "bg [job]", "description": "Resume a suspended job in the background.", "examples": ["bg %1"]},
            {"name": "fg", "syntax": "fg [job]", "description": "Bring a background job to the foreground.", "examples": ["fg %1"]},
            {"name": "jobs", "syntax": "jobs", "description": "List active jobs.", "examples": ["jobs"]},
            {"name": "nohup", "syntax": "nohup <command> &", "description": "Run a command immune to hangups.", "examples": ["nohup python server.py &"]},
            {"name": "nice", "syntax": "nice [-n N] <command>", "description": "Run a command with modified scheduling priority.", "examples": ["nice -n 10 make -j4"]},
            {"name": "renice", "syntax": "renice <priority> -p <PID>", "description": "Alter priority of running processes.", "examples": ["renice 5 -p 1234"]},
        ],
    },
    "System Information": {
        "description": "Commands for viewing system and hardware information.",
        "commands": [
            {"name": "uname", "syntax": "uname [options]", "description": "Print system information.", "examples": ["uname -a", "uname -r"]},
            {"name": "hostname", "syntax": "hostname", "description": "Show or set the system hostname.", "examples": ["hostname"]},
            {"name": "uptime", "syntax": "uptime", "description": "Show how long the system has been running.", "examples": ["uptime"]},
            {"name": "whoami", "syntax": "whoami", "description": "Print the current user name.", "examples": ["whoami"]},
            {"name": "id", "syntax": "id [user]", "description": "Print user and group IDs.", "examples": ["id", "id root"]},
            {"name": "df", "syntax": "df [options]", "description": "Report file system disk space usage.", "examples": ["df -h", "df -i"]},
            {"name": "du", "syntax": "du [options] [path]", "description": "Estimate file and directory space usage.", "examples": ["du -sh *", "du -h --max-depth=1"]},
            {"name": "free", "syntax": "free [options]", "description": "Display memory usage.", "examples": ["free -h", "free -m"]},
            {"name": "lscpu", "syntax": "lscpu", "description": "Display CPU architecture information.", "examples": ["lscpu"]},
            {"name": "lsblk", "syntax": "lsblk", "description": "List block devices.", "examples": ["lsblk"]},
            {"name": "dmesg", "syntax": "dmesg [options]", "description": "Print kernel ring buffer messages.", "examples": ["dmesg | tail", "dmesg -T"]},
        ],
    },
    "Networking": {
        "description": "Commands for network configuration, diagnostics, and data transfer.",
        "commands": [
            {"name": "ping", "syntax": "ping [options] <host>", "description": "Send ICMP echo requests to test connectivity.", "examples": ["ping google.com", "ping -c 4 192.168.1.1"]},
            {"name": "curl", "syntax": "curl [options] <URL>", "description": "Transfer data from or to a server.", "examples": ["curl https://api.example.com", "curl -o file.zip https://example.com/file.zip", "curl -X POST -d 'data' URL"]},
            {"name": "wget", "syntax": "wget [options] <URL>", "description": "Non-interactive network downloader.", "examples": ["wget https://example.com/file.tar.gz", "wget -r https://site.com"]},
            {"name": "ssh", "syntax": "ssh [user@]<host>", "description": "Secure shell remote login.", "examples": ["ssh user@server.com", "ssh -p 2222 user@host"]},
            {"name": "scp", "syntax": "scp <src> <user@host:dst>", "description": "Secure copy over SSH.", "examples": ["scp file.txt user@server:/tmp/", "scp -r dir/ user@server:~/"]},
            {"name": "rsync", "syntax": "rsync [options] <src> <dst>", "description": "Fast, versatile file copying tool.", "examples": ["rsync -avz src/ user@host:dst/"]},
            {"name": "ifconfig", "syntax": "ifconfig [interface]", "description": "Configure network interfaces (legacy).", "examples": ["ifconfig", "ifconfig eth0"]},
            {"name": "ip", "syntax": "ip <object> <command>", "description": "Modern network configuration tool.", "examples": ["ip addr show", "ip route show", "ip link set eth0 up"]},
            {"name": "netstat", "syntax": "netstat [options]", "description": "Network statistics.", "examples": ["netstat -tulnp", "netstat -an"]},
            {"name": "ss", "syntax": "ss [options]", "description": "Socket statistics (modern netstat).", "examples": ["ss -tulnp"]},
            {"name": "nslookup", "syntax": "nslookup <domain>", "description": "Query DNS records.", "examples": ["nslookup google.com"]},
            {"name": "dig", "syntax": "dig <domain>", "description": "DNS lookup utility.", "examples": ["dig example.com", "dig +short example.com"]},
            {"name": "traceroute", "syntax": "traceroute <host>", "description": "Print the route packets take to a host.", "examples": ["traceroute google.com"]},
        ],
    },
    "Compression & Archives": {
        "description": "Commands for compressing, decompressing, and archiving files.",
        "commands": [
            {"name": "tar", "syntax": "tar [options] <archive> [files]", "description": "Archive utility.", "examples": ["tar -czf archive.tar.gz dir/", "tar -xzf archive.tar.gz", "tar -tf archive.tar.gz"]},
            {"name": "gzip", "syntax": "gzip [file]", "description": "Compress files with gzip.", "examples": ["gzip file.txt", "gzip -d file.txt.gz"]},
            {"name": "gunzip", "syntax": "gunzip <file.gz>", "description": "Decompress gzip files.", "examples": ["gunzip file.txt.gz"]},
            {"name": "zip", "syntax": "zip <archive.zip> <files>", "description": "Package and compress files.", "examples": ["zip -r archive.zip dir/"]},
            {"name": "unzip", "syntax": "unzip <archive.zip>", "description": "Extract files from a ZIP archive.", "examples": ["unzip archive.zip", "unzip -l archive.zip"]},
            {"name": "xz", "syntax": "xz [file]", "description": "Compress files with LZMA.", "examples": ["xz file.txt", "xz -d file.txt.xz"]},
        ],
    },
    "User & Group Management": {
        "description": "Commands for managing users and groups.",
        "commands": [
            {"name": "useradd", "syntax": "useradd [options] <user>", "description": "Create a new user.", "examples": ["useradd -m newuser"]},
            {"name": "usermod", "syntax": "usermod [options] <user>", "description": "Modify a user account.", "examples": ["usermod -aG sudo user"]},
            {"name": "userdel", "syntax": "userdel [options] <user>", "description": "Delete a user account.", "examples": ["userdel -r olduser"]},
            {"name": "passwd", "syntax": "passwd [user]", "description": "Change user password.", "examples": ["passwd", "passwd otheruser"]},
            {"name": "groupadd", "syntax": "groupadd <group>", "description": "Create a new group.", "examples": ["groupadd developers"]},
            {"name": "groups", "syntax": "groups [user]", "description": "Show group memberships.", "examples": ["groups", "groups admin"]},
            {"name": "su", "syntax": "su [-] [user]", "description": "Switch to another user.", "examples": ["su -", "su - admin"]},
            {"name": "sudo", "syntax": "sudo <command>", "description": "Execute a command as another user (default root).", "examples": ["sudo apt update", "sudo -u postgres psql"]},
        ],
    },
    "Package Management": {
        "description": "Commands for installing and managing software packages.",
        "commands": [
            {"name": "apt", "syntax": "apt <command> [pkg]", "description": "Debian/Ubuntu package manager.", "examples": ["sudo apt update", "sudo apt install python3", "apt search nginx", "sudo apt remove pkg"]},
            {"name": "dnf", "syntax": "dnf <command> [pkg]", "description": "Fedora/RHEL package manager.", "examples": ["sudo dnf install gcc"]},
            {"name": "pacman", "syntax": "pacman <options> [pkg]", "description": "Arch Linux package manager.", "examples": ["sudo pacman -S vim", "pacman -Ss python"]},
            {"name": "pip", "syntax": "pip install <pkg>", "description": "Python package installer.", "examples": ["pip install requests", "pip install -r requirements.txt"]},
            {"name": "npm", "syntax": "npm <command> [pkg]", "description": "Node.js package manager.", "examples": ["npm install express", "npm init -y"]},
            {"name": "snap", "syntax": "snap <command> [pkg]", "description": "Universal Linux package manager.", "examples": ["sudo snap install code --classic"]},
        ],
    },
    "Disk & Storage": {
        "description": "Commands for managing disks, partitions, and storage.",
        "commands": [
            {"name": "mount", "syntax": "mount [device] [mountpoint]", "description": "Mount a file system.", "examples": ["mount /dev/sdb1 /mnt/usb"]},
            {"name": "umount", "syntax": "umount <mountpoint>", "description": "Unmount a file system.", "examples": ["umount /mnt/usb"]},
            {"name": "fdisk", "syntax": "fdisk <device>", "description": "Partition table manipulator.", "examples": ["sudo fdisk -l", "sudo fdisk /dev/sdb"]},
            {"name": "mkfs", "syntax": "mkfs.<type> <device>", "description": "Build a file system on a device.", "examples": ["mkfs.ext4 /dev/sdb1"]},
        ],
    },
    "Service & Systemd": {
        "description": "Commands for managing system services.",
        "commands": [
            {"name": "systemctl", "syntax": "systemctl <action> <service>", "description": "Control systemd services.", "examples": ["systemctl status nginx", "systemctl start nginx", "systemctl enable nginx", "systemctl restart sshd"]},
            {"name": "journalctl", "syntax": "journalctl [options]", "description": "Query the systemd journal.", "examples": ["journalctl -u nginx", "journalctl -f", "journalctl --since '1 hour ago'"]},
            {"name": "service", "syntax": "service <name> <action>", "description": "Run a SysV init script (legacy).", "examples": ["service nginx restart"]},
        ],
    },
    "Shell & Scripting": {
        "description": "Commands and concepts for shell scripting.",
        "commands": [
            {"name": "echo", "syntax": "echo [options] <text>", "description": "Display a line of text.", "examples": ["echo 'Hello'", "echo -n 'no newline'", "echo $HOME"]},
            {"name": "printf", "syntax": "printf <format> [args]", "description": "Formatted output.", "examples": ["printf '%s: %d\\n' name 42"]},
            {"name": "export", "syntax": "export VAR=value", "description": "Set an environment variable.", "examples": ["export PATH=$PATH:/opt/bin"]},
            {"name": "source", "syntax": "source <file>", "description": "Execute commands from a file in the current shell.", "examples": ["source ~/.bashrc", "source .env"]},
            {"name": "alias", "syntax": "alias <name>='<command>'", "description": "Create a shortcut for a command.", "examples": ["alias ll='ls -la'"]},
            {"name": "xargs", "syntax": "xargs [options] <command>", "description": "Build and execute commands from stdin.", "examples": ["find . -name '*.log' | xargs rm"]},
            {"name": "tee", "syntax": "tee [options] <file>", "description": "Read stdin and write to stdout and files.", "examples": ["echo 'data' | tee output.txt"]},
            {"name": "cron/crontab", "syntax": "crontab -e", "description": "Schedule recurring tasks.", "examples": ["crontab -e", "crontab -l"]},
            {"name": "env", "syntax": "env", "description": "Print or modify the environment.", "examples": ["env", "env VAR=val command"]},
            {"name": "set", "syntax": "set [options]", "description": "Set or unset shell options.", "examples": ["set -e", "set -x"]},
            {"name": "test / [ ]", "syntax": "test <expr> / [ <expr> ]", "description": "Evaluate conditional expressions.", "examples": ["test -f file && echo exists", "[ -d dir ] && echo dir"]},
        ],
    },
    "Git Version Control": {
        "description": "Commands for Git version control.",
        "commands": [
            {"name": "git init", "syntax": "git init", "description": "Initialise a new Git repository.", "examples": ["git init"]},
            {"name": "git clone", "syntax": "git clone <url>", "description": "Clone a remote repository.", "examples": ["git clone https://github.com/user/repo.git"]},
            {"name": "git status", "syntax": "git status", "description": "Show the working tree status.", "examples": ["git status"]},
            {"name": "git add", "syntax": "git add <files>", "description": "Stage changes for commit.", "examples": ["git add .", "git add file.py"]},
            {"name": "git commit", "syntax": "git commit -m '<msg>'", "description": "Record staged changes.", "examples": ["git commit -m 'Fix bug'"]},
            {"name": "git push", "syntax": "git push [remote] [branch]", "description": "Upload local commits to a remote.", "examples": ["git push origin main"]},
            {"name": "git pull", "syntax": "git pull [remote] [branch]", "description": "Fetch and merge remote changes.", "examples": ["git pull origin main"]},
            {"name": "git branch", "syntax": "git branch [name]", "description": "List or create branches.", "examples": ["git branch", "git branch feature-x"]},
            {"name": "git checkout", "syntax": "git checkout <branch|file>", "description": "Switch branches or restore files.", "examples": ["git checkout main", "git checkout -b new-branch"]},
            {"name": "git merge", "syntax": "git merge <branch>", "description": "Merge another branch into the current one.", "examples": ["git merge feature-x"]},
            {"name": "git log", "syntax": "git log [options]", "description": "Show commit history.", "examples": ["git log --oneline", "git log --graph --all"]},
            {"name": "git diff", "syntax": "git diff [files]", "description": "Show changes between commits or working tree.", "examples": ["git diff", "git diff HEAD~1"]},
            {"name": "git stash", "syntax": "git stash [pop|list|drop]", "description": "Temporarily shelve changes.", "examples": ["git stash", "git stash pop"]},
            {"name": "git remote", "syntax": "git remote [add|remove] <name> <url>", "description": "Manage remote repositories.", "examples": ["git remote -v", "git remote add origin URL"]},
            {"name": "git rebase", "syntax": "git rebase <branch>", "description": "Reapply commits on top of another base.", "examples": ["git rebase main"]},
            {"name": "git tag", "syntax": "git tag <name>", "description": "Create a tag for a specific commit.", "examples": ["git tag v1.0.0"]},
        ],
    },
}


# ──────────────────────────────────────────────────────────────────────────────
# 3. AURA OS Codebase Architecture
# ──────────────────────────────────────────────────────────────────────────────

CODEBASE_ARCHITECTURE: Dict[str, Dict] = {
    "aura_os/main.py": {
        "purpose": "Entry point for AURA OS.  Bootstraps the environment, builds the CLI parser, registers all command handlers, and starts either single-command mode or the interactive REPL shell.",
        "key_functions": [
            "main(argv) — Primary CLI entry point; initialises EAL and dispatches commands.",
            "_run_shell(eal) — Launches the interactive REPL with readline history.",
            "_bootstrap() — Sets AURA_HOME environment variable.",
        ],
    },
    "aura_os/eal/ (Environment Abstraction Layer)": {
        "purpose": "Provides a unified API for file operations, process execution, and system queries across Linux, Android/Termux, macOS, and fallback platforms.",
        "key_functions": [
            "EAL() — Main class; auto-detects platform and selects the correct adapter.",
            "EAL.run_command(cmd) — Execute a shell command via the platform adapter.",
            "EAL.get_env_info() — Return a dict of platform, binaries, paths, permissions, and system info.",
            "detector.get_platform() — Return normalised platform string.",
            "detector.get_available_binaries() — Map binary names to paths.",
            "detector.get_storage_paths() — Return home, temp, and aura_home paths.",
            "detector.get_permissions() — Return read/write flags for key paths.",
        ],
    },
    "aura_os/engine/ (Command Engine)": {
        "purpose": "Handles CLI parsing (argparse) and dispatching commands to registered handlers.",
        "key_functions": [
            "cli.build_parser() — Build the argparse parser with all subcommands.",
            "CommandRouter.register(name, handler_class) — Register a command handler.",
            "CommandRouter.dispatch(parsed_args, eal) — Route to the correct handler.",
        ],
    },
    "aura_os/ai/ (AI Subsystem)": {
        "purpose": "Offline AI inference using local LLMs (Ollama, llama.cpp) with a knowledge-enhanced system prompt.",
        "key_functions": [
            "LocalInference.query(prompt, model, max_tokens) — Run a prompt through the best available runtime.",
            "ModelManager.detect_runtimes() — Discover installed AI runtimes.",
            "ModelManager.list_models() — List available model files in ~/.aura/models/.",
            "knowledge.build_system_prompt() — Generate a comprehensive system prompt with AURA and Linux knowledge.",
            "knowledge.lookup(query) — Search the knowledge base for relevant information.",
        ],
    },
    "aura_os/engine/commands/": {
        "purpose": "Individual command handler classes, each with an execute(args, eal) method.",
        "key_functions": [
            "RunCommand.execute(args, eal) — Run scripts (.py, .sh, .js, etc.) via runtime detection.",
            "AiCommand.execute(args, eal) — Forward prompts to LocalInference.",
            "EnvCommand.execute(args, eal) — Display environment information.",
            "PkgCommand.execute(args, eal) — Package install/remove/list/search/info.",
            "SysCommand.execute(args, eal) — Show system status with optional --watch.",
        ],
    },
    "aura_os/pkg/ (Package Management)": {
        "purpose": "Local package registry (JSON-backed) and package manager for install/remove operations.",
        "key_functions": [
            "LocalRegistry — JSON-backed registry at ~/.aura/pkg/registry.json.",
            "PackageManager.install(name_or_path) — Install a package.",
            "PackageManager.remove(name) — Remove an installed package.",
        ],
    },
    "aura_os/fs/ (File System)": {
        "purpose": "Sandboxed virtual filesystem and a persistent JSON key-value store.",
        "key_functions": [
            "VirtualFS — Sandboxed filesystem rooted at ~/.aura/data/ with path-traversal protection.",
            "KVStore — Thread-safe JSON-backed key-value store at ~/.aura/data/store.json.",
        ],
    },
    "aura_os/kernel/ (Kernel Services)": {
        "purpose": "Core OS-like services: cooperative task scheduler, memory tracking, and IPC.",
        "key_functions": [
            "Scheduler — Cooperative task scheduler with priority support.",
            "MemoryTracker — Tracks memory usage across components.",
            "IPCChannel — File-based JSON-lines message queues for inter-process communication.",
        ],
    },
    "aura_os/config/ (Configuration)": {
        "purpose": "Manages application settings with defaults and user overrides.",
        "key_functions": [
            "Settings (singleton) — Thread-safe settings with dot-notation access (e.g. settings.get('ai.default_model')).",
            "DEFAULT_CONFIG — Default configuration dictionary in defaults.py.",
        ],
    },
    "core/ (Legacy Core)": {
        "purpose": "Original implementation with CommandRegistry, CommandEngine, and FileSystemManager.",
        "key_functions": [
            "CommandRegistry — Maps command names to handler functions with descriptions.",
            "CommandEngine — Loads environment, registers built-in commands, and dispatches input.",
            "FileSystemManager — File operations (ls, cat, find, mkdir, rm, edit).",
        ],
    },
    "modules/ (Optional Modules)": {
        "purpose": "Pluggable feature modules for AI, automation, git repos, and web UI.",
        "key_functions": [
            "AIModule — Rule-based fallback AI assistant with regex pattern matching.",
            "AutomationModule — JSON-based task workflow runner (run, log, sleep, write steps).",
            "RepoModule — Git repository management (init, commit, status, clone).",
            "BrowserModule — Flask-based web dashboard on port 7070.",
        ],
    },
}


# ──────────────────────────────────────────────────────────────────────────────
# 4. Public API — used by inference.py and modules/ai/__init__.py
# ──────────────────────────────────────────────────────────────────────────────

def build_system_prompt() -> str:
    """Build a comprehensive system prompt for LLM queries.

    The prompt tells the model about AURA OS capabilities, available
    terminal commands, common Linux commands, and codebase architecture
    so it can provide informed, context-aware answers.
    """
    sections: List[str] = []

    # Identity
    sections.append(
        "You are the AURA OS AI assistant — an intelligent, offline-first "
        "helper embedded in the AURA adaptive operating-system layer.  "
        "You have deep knowledge of AURA terminal commands, Linux/Unix "
        "commands, and the AURA codebase."
    )

    # AURA commands
    sections.append("\n## AURA OS Terminal Commands\n")
    for name, info in AURA_COMMANDS.items():
        sections.append(
            f"### {name}\n"
            f"Syntax: `{info['syntax']}`\n"
            f"{info['description']}\n"
            f"{info['details']}\n"
            f"Examples: {', '.join(f'`{e}`' for e in info['examples'])}\n"
        )

    # Linux commands (condensed for prompt)
    sections.append("\n## Common Linux Commands\n")
    for category, data in LINUX_COMMANDS.items():
        cmds = ", ".join(
            f"`{c['name']}` ({c['description']})" for c in data["commands"]
        )
        sections.append(f"**{category}**: {cmds}\n")

    # Codebase overview (condensed)
    sections.append("\n## AURA OS Codebase Architecture\n")
    for module, info in CODEBASE_ARCHITECTURE.items():
        sections.append(f"**{module}**: {info['purpose']}\n")

    return "\n".join(sections)


def _flatten_linux_commands() -> Dict[str, Dict]:
    """Return a flat dict mapping command name → info dict."""
    flat: Dict[str, Dict] = {}
    for _cat, data in LINUX_COMMANDS.items():
        for cmd in data["commands"]:
            flat[cmd["name"].lower()] = cmd
    return flat


_FLAT_LINUX = _flatten_linux_commands()


def lookup(query: str) -> Optional[str]:
    """Search the knowledge base for information matching *query*.

    Returns a formatted answer string, or ``None`` if nothing relevant
    is found.  Checks AURA commands, Linux commands, and codebase modules
    in order.
    """
    q = query.lower().strip()

    # 1. Check for explicit "list" or "all" requests
    if _matches_any(q, ["list all commands", "all aura commands",
                        "what commands", "available commands",
                        "show commands", "list commands"]):
        return _format_all_aura_commands()

    if _matches_any(q, ["list linux commands", "linux commands",
                        "all linux commands", "show linux commands",
                        "terminal commands"]):
        return _format_linux_overview()

    if _matches_any(q, ["codebase", "architecture", "how does aura work",
                        "source code", "code structure", "modules",
                        "how is aura built", "project structure"]):
        return _format_codebase_overview()

    # 2. Look for specific AURA command
    for name, info in AURA_COMMANDS.items():
        if name in q or (name == "ai" and "aura ai" in q):
            return _format_aura_command(name, info)

    # 3. Look for specific Linux command
    for cmd_name, cmd_info in _FLAT_LINUX.items():
        # Handle composite names like "vi/vim", "test / [ ]", "cron/crontab"
        for variant in cmd_name.split("/"):
            variant = variant.strip()
            if variant in q.split() or f" {variant} " in f" {q} ":
                return _format_linux_command(cmd_info)

    # 4. Look for Linux category match
    for category, data in LINUX_COMMANDS.items():
        cat_words = category.lower().split()
        if any(w in q for w in cat_words):
            return _format_linux_category(category, data)

    # 5. Look for codebase module match
    for module_key, mod_info in CODEBASE_ARCHITECTURE.items():
        module_words = module_key.lower().replace("/", " ").replace("(", "").replace(")", "").split()
        if any(w in q for w in module_words if len(w) > 2):
            return _format_codebase_module(module_key, mod_info)

    return None


# ──────────────────────────────────────────────────────────────────────────────
# Formatting helpers
# ──────────────────────────────────────────────────────────────────────────────

def _matches_any(text: str, patterns: List[str]) -> bool:
    return any(p in text for p in patterns)


def _format_all_aura_commands() -> str:
    lines = ["AURA OS Terminal Commands:\n"]
    for name, info in AURA_COMMANDS.items():
        lines.append(f"  {info['syntax']}")
        lines.append(f"    {info['description']}\n")
    lines.append("Type 'aura <command> --help' for detailed usage.")
    return "\n".join(lines)


def _format_aura_command(name: str, info: Dict) -> str:
    lines = [
        f"Command: {name}",
        f"Syntax:  {info['syntax']}",
        f"\n{info['description']}",
        f"\n{info['details']}",
        "\nExamples:",
    ]
    for ex in info["examples"]:
        lines.append(f"  {ex}")
    return "\n".join(lines)


def _format_linux_command(cmd: Dict) -> str:
    lines = [
        f"Command: {cmd['name']}",
        f"Syntax:  {cmd['syntax']}",
        f"\n{cmd['description']}",
        "\nExamples:",
    ]
    for ex in cmd["examples"]:
        lines.append(f"  {ex}")
    return "\n".join(lines)


def _format_linux_category(category: str, data: Dict) -> str:
    lines = [f"{category} — {data['description']}\n"]
    for cmd in data["commands"]:
        lines.append(f"  {cmd['name']:12s} {cmd['description']}")
    return "\n".join(lines)


def _format_linux_overview() -> str:
    lines = ["Linux Commands by Category:\n"]
    for category, data in LINUX_COMMANDS.items():
        cmd_names = ", ".join(c["name"] for c in data["commands"])
        lines.append(f"  {category}: {cmd_names}")
    lines.append("\nAsk about a specific command or category for details.")
    return "\n".join(lines)


def _format_codebase_overview() -> str:
    lines = ["AURA OS Codebase Architecture:\n"]
    for module, info in CODEBASE_ARCHITECTURE.items():
        lines.append(f"  {module}")
        lines.append(f"    {info['purpose']}\n")
    return "\n".join(lines)


def _format_codebase_module(module_key: str, info: Dict) -> str:
    lines = [
        f"Module: {module_key}",
        f"\n{info['purpose']}",
        "\nKey functions / classes:",
    ]
    for fn in info["key_functions"]:
        lines.append(f"  • {fn}")
    return "\n".join(lines)
