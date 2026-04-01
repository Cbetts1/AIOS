#!/usr/bin/env bash
# install.sh — AURA OS master installation script
#
# Idempotent: safe to run multiple times.
# Supports: Linux, macOS, Android/Termux

set -e

##############################################################################
# Helpers
##############################################################################

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'   # no colour

info()    { printf "${CYAN}[aura]${NC}  %s\n" "$*"; }
success() { printf "${GREEN}[aura]${NC}  %s\n" "$*"; }
warn()    { printf "${YELLOW}[aura]${NC}  %s\n" "$*" >&2; }
error()   { printf "${RED}[aura]${NC}  ERROR: %s\n" "$*" >&2; exit 1; }

##############################################################################
# Environment detection
##############################################################################

detect_platform() {
    if [ -n "${TERMUX_VERSION}" ] || [ -d "/data/data/com.termux" ]; then
        echo "termux"
    elif [ -f "/system/build.prop" ]; then
        echo "android"
    elif [ "$(uname -s)" = "Darwin" ]; then
        echo "macos"
    elif grep -qi microsoft /proc/version 2>/dev/null; then
        echo "wsl"
    else
        echo "linux"
    fi
}

PLATFORM="$(detect_platform)"
info "Detected platform: ${PLATFORM}"

##############################################################################
# Python check (>= 3.8)
##############################################################################

PYTHON=""
for candidate in python3 python; do
    if command -v "$candidate" >/dev/null 2>&1; then
        ver=$("$candidate" -c "import sys; print('%d%02d' % sys.version_info[:2])" 2>/dev/null || echo "0")
        if [ "$ver" -ge 308 ] 2>/dev/null; then
            PYTHON="$candidate"
            break
        fi
    fi
done

if [ -z "$PYTHON" ]; then
    error "Python 3.8+ is required but was not found.
  Linux  : sudo apt install python3  (or dnf/pacman)
  Termux : pkg install python
  macOS  : brew install python3"
fi

PYTHON_VERSION=$("$PYTHON" -c "import sys; print('.'.join(map(str,sys.version_info[:3])))")
info "Using Python ${PYTHON_VERSION} at $(command -v "$PYTHON")"

##############################################################################
# Paths
##############################################################################

AURA_HOME="${AURA_HOME:-${HOME}/.aura}"
AURA_BIN="${AURA_HOME}/bin"
AURA_LIB="${AURA_HOME}/lib"
AURA_DATA="${AURA_HOME}/data"
AURA_LOGS="${AURA_HOME}/logs"
AURA_PKG="${AURA_HOME}/pkg"
AURA_MODELS="${AURA_HOME}/models"
AURA_CONFIG="${AURA_HOME}/config"
AURA_IPC="${AURA_HOME}/ipc"

# Script's own directory (works even when sourced or run from another dir)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"

##############################################################################
# Create directory structure
##############################################################################

info "Creating ~/.aura directory structure…"
for dir in "$AURA_BIN" "$AURA_LIB" "$AURA_DATA" "$AURA_LOGS" \
           "$AURA_PKG/installed" "$AURA_MODELS" "$AURA_CONFIG" "$AURA_IPC"; do
    mkdir -p "$dir"
done
success "Directories created."

##############################################################################
# Copy library
##############################################################################

if [ -d "${SCRIPT_DIR}/aura_os" ]; then
    info "Installing aura_os library to ${AURA_LIB}/aura_os…"
    rm -rf "${AURA_LIB}/aura_os"
    cp -r "${SCRIPT_DIR}/aura_os" "${AURA_LIB}/aura_os"
    success "Library installed."
else
    warn "aura_os/ source directory not found next to install.sh — skipping library copy."
fi

##############################################################################
# Install entry script
##############################################################################

ENTRY_SCRIPT="${SCRIPT_DIR}/aura"
if [ -f "$ENTRY_SCRIPT" ]; then
    chmod +x "$ENTRY_SCRIPT"
    WRAPPER="${AURA_BIN}/aura"

    # Create a small wrapper that points to the canonical entry script
    cat > "$WRAPPER" <<WRAPPER_EOF
#!/usr/bin/env bash
export AURA_HOME="${AURA_HOME}"
export PYTHONPATH="${AURA_LIB}:\${PYTHONPATH:-}"
exec "${PYTHON}" -m aura_os.main "\$@"
WRAPPER_EOF
    chmod +x "$WRAPPER"
    success "Entry script installed at ${WRAPPER}."
else
    warn "'aura' entry script not found — skipping."
fi

##############################################################################
# Default config
##############################################################################

CONFIG_FILE="${AURA_CONFIG}/settings.json"
if [ ! -f "$CONFIG_FILE" ]; then
    info "Writing default config to ${CONFIG_FILE}…"
    cat > "$CONFIG_FILE" <<'CONFIG_EOF'
{
  "version": "0.1.0",
  "log_level": "INFO",
  "ai": {
    "default_model": "auto",
    "max_tokens": 512,
    "runtime": "auto"
  },
  "shell": {
    "prompt": "aura> ",
    "history_file": "~/.aura/data/.history"
  },
  "pkg": {
    "registry_url": null,
    "install_dir": "~/.aura/pkg/installed"
  },
  "fs": {
    "data_dir": "~/.aura/data",
    "max_vfs_size_mb": 1024
  }
}
CONFIG_EOF
    success "Default config written."
else
    info "Config already exists at ${CONFIG_FILE} — skipping."
fi

##############################################################################
# PATH configuration
##############################################################################

add_to_path() {
    local profile_file="$1"
    local path_line='export PATH="${HOME}/.aura/bin:${PATH}"'

    if [ -f "$profile_file" ] && grep -q 'aura/bin' "$profile_file" 2>/dev/null; then
        info "PATH entry already present in ${profile_file}."
        return
    fi

    {
        echo ""
        echo "# AURA OS"
        echo "${path_line}"
    } >> "$profile_file"
    success "Added ~/.aura/bin to PATH in ${profile_file}."
}

# Pick the right shell profile
if [ "${PLATFORM}" = "termux" ]; then
    PROFILE="${HOME}/.bashrc"
elif [ "${PLATFORM}" = "macos" ] && [ -f "${HOME}/.zshrc" ]; then
    PROFILE="${HOME}/.zshrc"
elif [ -f "${HOME}/.bashrc" ]; then
    PROFILE="${HOME}/.bashrc"
elif [ -f "${HOME}/.bash_profile" ]; then
    PROFILE="${HOME}/.bash_profile"
elif [ -f "${HOME}/.zshrc" ]; then
    PROFILE="${HOME}/.zshrc"
else
    PROFILE="${HOME}/.profile"
fi

add_to_path "$PROFILE"

##############################################################################
# Done
##############################################################################

echo ""
success "AURA OS installation complete!"
echo ""
info "To start using aura right now, run:"
printf "    ${CYAN}export PATH=\"\${HOME}/.aura/bin:\${PATH}\"${NC}\n"
printf "    ${CYAN}aura --help${NC}\n"
echo ""
info "Or install with pip for system-wide access:"
printf "    ${CYAN}pip install .${NC}\n"
echo ""
info "Or start a new shell session for PATH changes to take effect."
echo ""
