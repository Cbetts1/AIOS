#!/usr/bin/env bash
# ============================================================
#  AURA OS — Master Installation Script
#  Adaptive User-space Runtime Architecture
#
#  Supported environments:
#    • Termux on Android
#    • Debian/Ubuntu Linux
#    • Fedora / RHEL / CentOS
#    • Arch Linux
#    • macOS (Homebrew)
#    • Any POSIX system with Python 3
#
#  Usage:
#    bash install.sh [--prefix /path/to/install]
#
#  After installation:
#    aura help
# ============================================================

set -euo pipefail

# ── Colours ──────────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

log()  { echo -e "${CYAN}[aura]${NC} $*"; }
ok()   { echo -e "${GREEN}[ok]${NC} $*"; }
warn() { echo -e "${YELLOW}[warn]${NC} $*"; }
fail() { echo -e "${RED}[fail]${NC} $*"; exit 1; }

# ── Defaults ─────────────────────────────────────────────────────────────────
AURA_REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AURA_HOME="${AURA_HOME:-$HOME/.aura}"
INSTALL_PREFIX="${1:-}"
if [[ "$INSTALL_PREFIX" == "--prefix" && -n "${2:-}" ]]; then
    AURA_HOME="$2"
fi

# ── Detect Environment ────────────────────────────────────────────────────────
detect_env() {
    IS_TERMUX=false
    IS_LINUX=false
    IS_MACOS=false
    PKG_MANAGER=""

    if [[ -d "/data/data/com.termux" ]] || [[ "${PREFIX:-}" == *termux* ]]; then
        IS_TERMUX=true
        IS_LINUX=true
        if command -v pkg &>/dev/null; then PKG_MANAGER="pkg"; fi
    elif [[ "$(uname -s)" == "Linux" ]]; then
        IS_LINUX=true
        if command -v apt-get &>/dev/null; then PKG_MANAGER="apt-get"
        elif command -v dnf &>/dev/null; then  PKG_MANAGER="dnf"
        elif command -v yum &>/dev/null; then  PKG_MANAGER="yum"
        elif command -v pacman &>/dev/null; then PKG_MANAGER="pacman"
        elif command -v zypper &>/dev/null; then PKG_MANAGER="zypper"
        fi
    elif [[ "$(uname -s)" == "Darwin" ]]; then
        IS_MACOS=true
        if command -v brew &>/dev/null; then PKG_MANAGER="brew"; fi
    fi

    log "Detected environment: $(uname -s) | Termux=$IS_TERMUX | PM=$PKG_MANAGER"
}

# ── Python detection ─────────────────────────────────────────────────────────
find_python() {
    for py in python3 python; do
        if command -v "$py" &>/dev/null; then
            PYTHON="$py"
            PY_VER="$($py --version 2>&1)"
            ok "Found Python: $PYTHON ($PY_VER)"
            return 0
        fi
    done
    return 1
}

# ── Install system packages ───────────────────────────────────────────────────
install_system_packages() {
    if $IS_TERMUX; then
        log "Installing Termux packages …"
        pkg install -y python git curl wget 2>/dev/null || warn "Some packages may have failed"
    elif [[ -n "$PKG_MANAGER" ]]; then
        log "Installing system packages via $PKG_MANAGER …"
        case "$PKG_MANAGER" in
            apt-get|apt)
                sudo apt-get update -qq 2>/dev/null || true
                sudo apt-get install -y python3 python3-pip git curl 2>/dev/null || warn "apt install had warnings"
                ;;
            dnf|yum)
                sudo "$PKG_MANAGER" install -y python3 python3-pip git curl 2>/dev/null || warn "dnf/yum install had warnings"
                ;;
            pacman)
                sudo pacman -Sy --noconfirm python python-pip git curl 2>/dev/null || warn "pacman install had warnings"
                ;;
            brew)
                brew install python git curl 2>/dev/null || warn "brew install had warnings"
                ;;
        esac
    else
        warn "No supported package manager found. Skipping system package installation."
    fi
}

# ── Install Python packages ───────────────────────────────────────────────────
install_python_packages() {
    log "Installing Python packages …"
    local pip_cmd=""
    for p in pip3 pip "$PYTHON -m pip"; do
        if command -v ${p%% *} &>/dev/null || $PYTHON -m pip --version &>/dev/null 2>&1; then
            pip_cmd="$PYTHON -m pip"
            break
        fi
    done

    if [[ -z "$pip_cmd" ]]; then
        warn "pip not found — skipping Python package installation"
        return
    fi

    $pip_cmd install --upgrade pip --quiet 2>/dev/null || true

    # Core requirements — flask is optional (used for web UI)
    local packages="flask"
    for pkg in $packages; do
        if $pip_cmd install "$pkg" --quiet 2>/dev/null; then
            ok "  + $pkg"
        else
            warn "  Could not install $pkg (non-fatal — fallback will be used)"
        fi
    done
}

# ── Create directory structure ────────────────────────────────────────────────
create_dirs() {
    log "Creating AURA directory structure at $AURA_HOME …"
    local dirs=(
        "$AURA_HOME/configs"
        "$AURA_HOME/logs"
        "$AURA_HOME/models"
        "$AURA_HOME/tasks"
        "$AURA_HOME/repos"
        "$AURA_HOME/ui/templates"
        "$AURA_HOME/data"
        "$AURA_HOME/boot"
    )
    for d in "${dirs[@]}"; do
        mkdir -p "$d"
    done
    ok "Directories created."
}

# ── Write default config ──────────────────────────────────────────────────────
write_config() {
    local cfg="$AURA_HOME/configs/system.json"
    if [[ ! -f "$cfg" ]]; then
        cat > "$cfg" <<EOF
{
  "version": "1.0.0",
  "env_type": "auto",
  "storage_root": "$AURA_HOME",
  "web_ui_port": 7070,
  "web_ui_host": "127.0.0.1",
  "ai_backend": "auto",
  "log_level": "info"
}
EOF
        ok "Config written: $cfg"
    else
        ok "Config already exists: $cfg"
    fi
}

# ── Set up environment variables ──────────────────────────────────────────────
setup_env_vars() {
    log "Setting up environment variables …"

    local profile_file=""
    if [[ -f "$HOME/.bashrc" ]]; then
        profile_file="$HOME/.bashrc"
    elif [[ -f "$HOME/.bash_profile" ]]; then
        profile_file="$HOME/.bash_profile"
    elif [[ -f "$HOME/.zshrc" ]]; then
        profile_file="$HOME/.zshrc"
    elif [[ -f "$HOME/.profile" ]]; then
        profile_file="$HOME/.profile"
    fi

    local export_line="export AURA_HOME=\"$AURA_HOME\""
    local path_line="export PATH=\"$AURA_REPO_DIR:\$PATH\""

    if [[ -n "$profile_file" ]]; then
        # Only add if not already present
        if ! grep -q "AURA_HOME" "$profile_file" 2>/dev/null; then
            echo "" >> "$profile_file"
            echo "# AURA OS" >> "$profile_file"
            echo "$export_line" >> "$profile_file"
            echo "$path_line" >> "$profile_file"
            ok "Environment variables added to $profile_file"
        else
            ok "Environment variables already in $profile_file"
        fi
    else
        warn "Could not find shell profile file. Add these manually:"
        echo "  $export_line"
        echo "  $path_line"
    fi

    # Export for current session
    export AURA_HOME="$AURA_HOME"
    export PATH="$AURA_REPO_DIR:$PATH"
}

# ── Make scripts executable ───────────────────────────────────────────────────
set_permissions() {
    log "Setting file permissions …"
    chmod +x "$AURA_REPO_DIR/aura" 2>/dev/null || true
    find "$AURA_REPO_DIR/scripts" -name "*.sh" -exec chmod +x {} \; 2>/dev/null || true
    ok "Permissions set."
}

# ── Optional: Termux:Boot setup ───────────────────────────────────────────────
setup_termux_boot() {
    if $IS_TERMUX; then
        log "Setting up Termux:Boot …"
        local boot_dir="$HOME/.termux/boot"
        mkdir -p "$boot_dir"
        cat > "$boot_dir/aura_start.sh" <<EOF
#!/data/data/com.termux/files/usr/bin/bash
export AURA_HOME="$AURA_HOME"
export PATH="$AURA_REPO_DIR:\$PATH"
# Uncomment below to auto-start web UI on boot:
# aura ui web &
EOF
        chmod +x "$boot_dir/aura_start.sh"
        ok "Termux:Boot script installed: $boot_dir/aura_start.sh"
    fi
}

# ── Run bootstrap ─────────────────────────────────────────────────────────────
run_bootstrap() {
    log "Running AURA bootstrap …"
    AURA_HOME="$AURA_HOME" "$PYTHON" "$AURA_REPO_DIR/boot/startup.py" || \
        warn "Bootstrap completed with warnings."
}

# ── Final summary ─────────────────────────────────────────────────────────────
print_summary() {
    echo ""
    echo -e "${BOLD}${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BOLD}  AURA OS — Installation Complete${NC}"
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
    echo "  Installation directory : $AURA_REPO_DIR"
    echo "  AURA home              : $AURA_HOME"
    echo ""
    echo "  To start AURA in a new terminal:"
    echo ""
    echo -e "    ${CYAN}source ~/.bashrc${NC}          (reload shell)"
    echo -e "    ${CYAN}aura help${NC}                 (show commands)"
    echo -e "    ${CYAN}aura sys info${NC}             (system info)"
    echo -e "    ${CYAN}aura ui${NC}                   (launch dashboard)"
    echo ""
    echo -e "  Or run directly (current session):"
    echo ""
    echo -e "    ${CYAN}$AURA_REPO_DIR/aura help${NC}"
    echo ""
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
}

# ── Main ──────────────────────────────────────────────────────────────────────
main() {
    echo ""
    echo -e "${BOLD}${CYAN}  ⬡ AURA OS — Adaptive User-space Runtime Architecture${NC}"
    echo -e "${CYAN}  Installation starting …${NC}"
    echo ""

    detect_env

    # Python is required
    if ! find_python; then
        install_system_packages
        if ! find_python; then
            fail "Python 3 not found and could not be installed. Please install Python 3 manually."
        fi
    else
        install_system_packages
    fi

    install_python_packages
    create_dirs
    write_config
    setup_env_vars
    set_permissions
    setup_termux_boot
    run_bootstrap
    print_summary
}

main "$@"
