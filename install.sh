#!/usr/bin/env bash
# ══════════════════════════════════════════════════════════════
#  WebSpy v2.0 — Automated Setup Script
#  Author  : Silentium Noctis
#  Target  : Kali Linux / Debian-based systems
#  Usage   : chmod +x install.sh && sudo ./install.sh
# ══════════════════════════════════════════════════════════════

# ── Colors ────────────────────────────────────────────────────
R="\033[0;31m";  BR="\033[1;31m"; G="\033[0;32m";  BG="\033[1;32m"
Y="\033[0;33m";  BY="\033[1;33m"; C="\033[0;36m";  BC="\033[1;36m"
W="\033[1;37m";  NC="\033[0m";    B="\033[0;34m";  BB="\033[1;34m"

# ── Banner ────────────────────────────────────────────────────
clear
echo -e "${C}
 ██╗    ██╗███████╗██████╗ ███████╗██████╗ ██╗   ██╗
 ██║    ██║██╔════╝██╔══██╗██╔════╝██╔══██╗╚██╗ ██╔╝
 ██║ █╗ ██║█████╗  ██████╔╝███████╗██████╔╝ ╚████╔╝
 ██║███╗██║██╔══╝  ██╔══██╗╚════██║██╔═══╝   ╚██╔╝
 ╚███╔███╔╝███████╗██████╔╝███████║██║        ██║
  ╚══╝╚══╝ ╚══════╝╚═════╝ ╚══════╝╚═╝        ╚═╝
${NC}${BY} Advanced Penetration Testing Framework  v2.0${NC}
${BG}               Installation Script — by Silentium Noctis${NC}
${R} [!] For authorized penetration testing and bug bounty only${NC}
"
sleep 1

# ── Root check ────────────────────────────────────────────────
if [[ $EUID -ne 0 ]]; then
    echo -e "${BR}[✗] This script must be run as root.${NC}"
    echo -e "${Y}    Run: sudo ./install.sh${NC}"
    exit 1
fi

TOOL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WEBSPY="$TOOL_DIR/webspy.py"

ok()   { echo -e "${BG}[✓]${NC} ${W}$1${NC}"; }
info() { echo -e "${C}[*]${NC} $1"; }
warn() { echo -e "${BY}[!]${NC} $1"; }
err()  { echo -e "${BR}[✗]${NC} $1"; }
step() { echo -e "\n${W}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}\n${BY} $1${NC}\n${W}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"; }

# ── Step 1: System update ─────────────────────────────────────
step "STEP 1 — Updating package lists"
apt-get update -qq 2>/dev/null && ok "Package lists updated" || warn "apt update failed — continuing"

# ── Step 2: Python3 & pip ─────────────────────────────────────
step "STEP 2 — Python3 & pip"

if command -v python3 &>/dev/null; then
    PYVER=$(python3 --version 2>&1)
    ok "Python3 found: $PYVER"
else
    info "Installing Python3..."
    apt-get install -y python3 2>/dev/null && ok "Python3 installed" || { err "Python3 install failed"; exit 1; }
fi

if command -v pip3 &>/dev/null; then
    ok "pip3 found: $(pip3 --version | cut -d' ' -f1-2)"
else
    info "Installing pip3..."
    apt-get install -y python3-pip 2>/dev/null && ok "pip3 installed" || { err "pip3 install failed"; exit 1; }
fi

# ── Step 3: Python dependencies ───────────────────────────────
step "STEP 3 — Python dependencies (requirements.txt)"

if [[ -f "$TOOL_DIR/requirements.txt" ]]; then
    info "Installing from requirements.txt..."
    pip3 install -r "$TOOL_DIR/requirements.txt" --quiet 2>/dev/null
    ok "Python dependencies installed"
    while IFS= read -r line; do
        [[ "$line" =~ ^# || -z "$line" ]] && continue
        pkg=$(echo "$line" | cut -d'>' -f1 | cut -d'=' -f1 | tr -d ' ')
        echo -e "  ${G}✓${NC} $pkg"
    done < "$TOOL_DIR/requirements.txt"
else
    info "requirements.txt not found — installing requests manually"
    pip3 install requests urllib3 --quiet && ok "requests + urllib3 installed"
fi

# ── Step 4: Kali Linux tools ──────────────────────────────────
step "STEP 4 — Kali Linux Tools"

declare -A TOOLS=(
    ["nmap"]="nmap"
    ["gobuster"]="gobuster"
    ["nikto"]="nikto"
    ["sublist3r"]="sublist3r"
    ["wafw00f"]="wafw00f"
    ["whatweb"]="whatweb"
    ["whois"]="whois"
    ["dig"]="dnsutils"
    ["searchsploit"]="exploitdb"
)

MISSING=()
for tool in "${!TOOLS[@]}"; do
    if command -v "$tool" &>/dev/null; then
        ok "$tool — already installed"
    else
        pkg="${TOOLS[$tool]}"
        info "Installing $tool ($pkg)..."
        apt-get install -y "$pkg" -qq 2>/dev/null
        if command -v "$tool" &>/dev/null; then
            ok "$tool — installed successfully"
        else
            warn "$tool — install failed (try manually: apt install $pkg)"
            MISSING+=("$tool")
        fi
    fi
done

# wafw00f via pip if apt failed
if ! command -v wafw00f &>/dev/null; then
    info "Trying wafw00f via pip3..."
    pip3 install wafw00f --quiet 2>/dev/null && ok "wafw00f installed via pip3"
fi

# ── Step 5: Permissions ───────────────────────────────────────
step "STEP 5 — Setting Permissions"

if [[ -f "$WEBSPY" ]]; then
    chmod +x "$WEBSPY"
    ok "webspy.py — executable permission set"
else
    err "webspy.py not found in $TOOL_DIR"
    err "Make sure webspy.py is in the same directory as install.sh"
    exit 1
fi

chmod +x "$0"
ok "install.sh — permissions set"

# ── Step 6: Optional — add to PATH ───────────────────────────
step "STEP 6 — PATH Setup (Optional)"

LINK="/usr/local/bin/webspy"
if [[ ! -f "$LINK" ]]; then
    ln -sf "$WEBSPY" "$LINK" 2>/dev/null && ok "Symlink created: webspy → /usr/local/bin/webspy" || warn "Could not create symlink (non-critical)"
else
    ok "webspy already in /usr/local/bin"
fi

# ── Step 7: Verify install ────────────────────────────────────
step "STEP 7 — Installation Verification"

echo -e "\n  ${W}Tool Check:${NC}"
ALL_OK=true
for tool in nmap gobuster wafw00f whatweb whois dig python3 pip3; do
    if command -v "$tool" &>/dev/null; then
        echo -e "  ${BG}[✓]${NC} $tool"
    else
        echo -e "  ${BR}[✗]${NC} $tool ${R}(missing)${NC}"
        ALL_OK=false
    fi
done

echo -e "\n  ${W}Python Libraries:${NC}"
python3 -c "import requests; print('  \033[1;32m[✓]\033[0m requests ' + requests.__version__)" 2>/dev/null || echo -e "  ${BR}[✗]${NC} requests"
python3 -c "import urllib3; print('  \033[1;32m[✓]\033[0m urllib3  ' + urllib3.__version__)" 2>/dev/null || echo -e "  ${BR}[✗]${NC} urllib3"

# ── Final: The Quote ──────────────────────────────────────────
echo -e "\n\n${R}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${R}║                                                              ║${NC}"
echo -e "${R}║${NC}  ${BR}\"${NC}${W}They locked their doors. They patched their walls.           ${NC}${R}║${NC}"
echo -e "${R}║${NC}  ${W}  They prayed their firewalls would hold.                     ${NC}${R}║${NC}"
echo -e "${R}║${NC}  ${W}  But no wall was ever built that silence couldn't cross.     ${NC}${R}║${NC}"
echo -e "${R}║${NC}                                                              ${R}║${NC}"
echo -e "${R}║${NC}  ${W}  I do not hack systems. I ${BR}whisper${NC}${W} to them —             ${NC}${R}║${NC}"
echo -e "${R}║${NC}  ${W}  and they ${BR}open${NC}${W} for me.                                  ${NC}${R}║${NC}"
echo -e "${R}║${NC}                                                              ${R}║${NC}"
echo -e "${R}║${NC}  ${W}  The internet is not a network.                            ${NC}${R}║${NC}"
echo -e "${R}║${NC}  ${W}  It is a ${BR}graveyard${NC}${W} of secrets waiting to be exhumed.    ${NC}${R}║${NC}"
echo -e "${R}║${NC}  ${W}  And I... am the ${BR}gravedigger${NC}${W}.                           ${NC}${R}║${NC}"
echo -e "${R}║${NC}                                                              ${R}║${NC}"
echo -e "${R}║${NC}  ${W}  Now, with this tool in your hands —                       ${NC}${R}║${NC}"
echo -e "${R}║${NC}  ${W}  you don't just ${BR}break the web${NC}${W}.                          ${NC}${R}║${NC}"
echo -e "${R}║${NC}  ${W}  You ${BR}own${NC}${W} it.${NC}${W}                                          ${NC}${R}║${NC}"
echo -e "${R}║${NC}                                                              ${R}║${NC}"
echo -e "${R}║${NC}                   ${BC}— Silentium Noctis${NC}                       ${R}║${NC}"
echo -e "${R}║${NC}                     ${C}[ The Ghost in the Wire ]${NC}              ${R}║${NC}"
echo -e "${R}║                                                              ║${NC}"
echo -e "${R}╚══════════════════════════════════════════════════════════════╝${NC}"

sleep 1

# ── Run command ───────────────────────────────────────────────
echo -e "\n${W}════════════════════════════════════════════════════════════${NC}"
echo -e "${BG}  INSTALLATION COMPLETE — WebSpy v2.0 is ready.${NC}"
echo -e "${W}════════════════════════════════════════════════════════════${NC}"

echo -e "\n${BY}  ▸  To run WebSpy (Interactive Mode):${NC}"
echo -e "     ${BG}python3 $WEBSPY${NC}"

echo -e "\n${BY}  ▸  If added to PATH, you can also run:${NC}"
echo -e "     ${BG}webspy${NC}"

echo -e "\n${BY}  ▸  Quick examples:${NC}"
echo -e "     ${C}python3 $WEBSPY -h${NC}                         ${W}# Help${NC}"
echo -e "     ${C}python3 $WEBSPY -t example.com -m full -T3${NC}  ${W}# Full scan${NC}"
echo -e "     ${C}python3 $WEBSPY -t example.com --cf --headers${NC} ${W}# CF bypass + headers${NC}"

if [[ ${#MISSING[@]} -gt 0 ]]; then
    echo -e "\n${BY}  ▸  Missing tools (install manually):${NC}"
    for t in "${MISSING[@]}"; do
        echo -e "     ${Y}apt install ${TOOLS[$t]}${NC}"
    done
fi

echo -e "\n${R}  [!] Use only on authorized targets.${NC}"
echo -e "${W}════════════════════════════════════════════════════════════${NC}\n"
