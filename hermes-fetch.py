#!/usr/bin/env python3
"""
hermes-fetch — A Neofetch-style system & Hermes Agent status display.

Standalone and portable: pure Python 3 stdlib, no pip dependencies.
Optimized for 100+ character terminal width.

Usage:
    python3 hermes-fetch.py [--no-color] [--json]

Requires: Hermes Agent installed at ~/.hermes (or $HERMES_HOME).

Author: Belle (Hermes Agent)
"""

import argparse
import glob
import json
import os
import platform
import sqlite3
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

# ─── ANSI Colors ──────────────────────────────────────────────────────────────

class C:
    """ANSI color codes. Kept short for terminal efficiency."""
    RESET   = "\033[0m"
    BOLD    = "\033[1m"
    DIM     = "\033[2m"
    RED     = "\033[31m"
    GREEN   = "\033[32m"
    YELLOW  = "\033[33m"
    BLUE    = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN    = "\033[36m"
    WHITE   = "\033[37m"
    GRAY    = "\033[90m"
    BRED    = "\033[91m"
    BGREEN  = "\033[92m"
    BYELLOW = "\033[93m"
    BBLUE   = "\033[94m"
    BMAGENTA= "\033[95m"
    BCYAN   = "\033[96m"
    BWHITE  = "\033[97m"

# ─── Config ───────────────────────────────────────────────────────────────────

HERMES_HOME = Path(os.environ.get("HERMES_HOME", os.path.expanduser("~/.hermes")))
CONFIG_PATH = HERMES_HOME / "config.yaml"
STATE_DB    = HERMES_HOME / "state.db"
ENV_FILE    = HERMES_HOME / ".env"
CRON_FILE   = HERMES_HOME / "cron" / "jobs.json"
SKILLS_GLOB = str(HERMES_HOME / "skills" / "*" / "*" / "SKILL.md")

# ─── ASCII Art ────────────────────────────────────────────────────────────────

# The Hermes caduceus logo — stylized for terminal display.
# 30 chars wide, 18 lines tall.
LOGO = r"""
              {c_b}▟█████████████████████▙{c_r}
           {c_b}▟█████{c_c}▟███████████▙{c_b}█████▙{c_r}
          {c_b}██████{c_c}██{c_y}  ⚕  ☿  ⚕  {c_c}██{c_b}██████{c_r}
          {c_b}██████{c_c}███████████████{c_b}██████{c_r}
          {c_b}██████{c_c}██{c_y}  ⚕  ☿  ⚕  {c_c}██{c_b}██████{c_r}
          {c_b}██████{c_c}███████████████{c_b}██████{c_r}
           {c_b}▜█████{c_c}▜███████████▛{c_b}█████▛{c_r}
              {c_b}▜█████████████████████▛{c_r}
                 {c_p}▜█████████████▛{c_r}
                   {c_p}▜█████████▛{c_r}
              {c_p}▟██▙{c_y}  {c_p}▜███▛{c_y}  {c_p}▟██▙{c_r}
             {c_p}██   ██{c_y}  {c_p}▟█▙{c_y}  {c_p}██   ██{c_r}
             {c_p}██   ██{c_y}  {c_p}███{c_y}  {c_p}██   ██{c_r}
              {c_p}▜██▛{c_y}  {c_p}▟█████▙{c_y}  {c_p}▜██▛{c_r}
                 {c_p}▟███{c_y}  {c_p}███{c_y}  {c_p}███▙{c_r}
                {c_p}▟██▙{c_y}  {c_p}▟█████▙{c_y}  {c_p}▟██▙{c_r}
               {c_p}▟█▙ {c_y}  {c_p}███   ███{c_y}  {c_p}▟█▙{c_r}
               {c_p}▜██▛ {c_y} {c_p}▜█████████▛{c_y} {c_p}▜██▛{c_r}
"""

def render_logo(colors: bool = True) -> list[str]:
    """Return the logo as a list of lines with color codes applied."""
    if not colors:
        # Strip template placeholders for plain text mode
        import re
        art = re.sub(r'\{c_\w+\}', '', LOGO)
    else:
        art = LOGO.format(
            c_b=C.BBLUE, c_c=C.BCYAN, c_y=C.BYELLOW,
            c_p=C.BMAGENTA, c_r=C.RESET
        )
    return art.strip("\n").split("\n")

# ─── Data Collection ──────────────────────────────────────────────────────────

def run(cmd: list[str], timeout: int = 5) -> str:
    """Run a command and return stdout, or empty string on failure."""
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip()
    except Exception:
        return ""

def read_env_file(path: Path) -> dict:
    """Parse a .env file into a dict (key -> value)."""
    env = {}
    if not path.exists():
        return env
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip().strip("'\"")
    return env

def try_yaml(path: Path) -> dict:
    """Attempt to load YAML. Falls back to manual parsing if PyYAML unavailable."""
    if not path.exists():
        return {}
    text = path.read_text()
    try:
        import yaml
        return yaml.safe_load(text) or {}
    except ImportError:
        return _manual_yaml_parse(text)

def _manual_yaml_parse(text: str) -> dict:
    """Minimal YAML parser for the flat keys we need. Not a general parser."""
    result = {}
    current_section = result
    section_path = []
    for line in text.splitlines():
        stripped = line.rstrip()
        if not stripped or stripped.startswith("#"):
            continue
        indent = len(line) - len(line.lstrip())
        if indent == 0 and ":" in stripped and not stripped.startswith(" "):
            key = stripped.split(":")[0].strip()
            val = stripped.split(":", 1)[1].strip()
            if val:
                result[key] = val.strip("'\"")
            else:
                result[key] = {}
                section_path = [(0, key)]
                current_section = result[key]
        elif section_path:
            # Pop sections deeper than current indent
            while section_path and section_path[-1][0] >= indent:
                section_path.pop()
            if ":" in stripped:
                key = stripped.lstrip().split(":")[0].strip()
                val = stripped.lstrip().split(":", 1)[1].strip()
                parent = result
                for _, sk in section_path:
                    parent = parent.get(sk, {})
                if val:
                    parent[key] = val.strip("'\"")
                else:
                    parent[key] = {}
                    section_path.append((indent, key))
    return result

def get_openrouter_balance(api_key: str) -> dict | None:
    """Fetch OpenRouter credit balance via API."""
    if not api_key:
        return None
    try:
        req = urllib.request.Request(
            "https://openrouter.ai/api/v1/credits",
            headers={"Authorization": f"Bearer {api_key}"}
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
            d = data.get("data", {})
            return {
                "total": d.get("total_credits", 0),
                "used": d.get("total_usage", 0),
                "remaining": d.get("total_credits", 0) - d.get("total_usage", 0),
            }
    except Exception:
        return None

def get_system_info() -> dict:
    """Collect system information."""
    info = {}
    
    # Hardware model
    model_path = Path("/proc/device-tree/model")
    if model_path.exists():
        info["model"] = model_path.read_text().rstrip("\x00")
    else:
        info["model"] = platform.machine()
    
    # OS
    info["os"] = f"{platform.system()} {platform.release()}"
    info["arch"] = platform.machine()
    info["hostname"] = platform.node()
    info["python"] = platform.python_version()
    
    # CPU
    info["cpu_cores"] = os.cpu_count() or "?"
    try:
        with open("/proc/cpuinfo") as f:
            for line in f:
                # Check common field names: "model name", "Hardware", "Model"
                if line.startswith("model name"):
                    info["cpu_model"] = line.split(":")[1].strip()
                    break
                elif line.startswith("Hardware"):
                    info["cpu_model"] = line.split(":")[1].strip()
                    break
                elif line.startswith("Model\t"):
                    info["cpu_model"] = line.split(":")[1].strip()
                    break
        if "cpu_model" not in info:
            # Fallback: use device-tree model, strip "Rev" suffix for brevity
            model = info.get("model", platform.machine())
            info["cpu_model"] = model
    except Exception:
        info["cpu_model"] = "unknown"
    
    # Memory
    try:
        with open("/proc/meminfo") as f:
            mem = {}
            for line in f:
                parts = line.split()
                if len(parts) >= 2:
                    mem[parts[0].rstrip(":")] = int(parts[1])
        total = mem.get("MemTotal", 0) // 1024
        avail = mem.get("MemAvailable", 0) // 1024
        used = total - avail
        info["mem_total"] = total
        info["mem_used"] = used
        info["mem_avail"] = avail
        swap_total = mem.get("SwapTotal", 0) // 1024
        swap_free = mem.get("SwapFree", 0) // 1024
        info["swap_total"] = swap_total
        info["swap_used"] = swap_total - swap_free
    except Exception:
        info["mem_total"] = 0
        info["mem_used"] = 0
    
    # Disk
    try:
        df = run(["df", "-h", "/"])
        lines = df.split("\n")
        if len(lines) > 1:
            parts = lines[1].split()
            if len(parts) >= 6:
                info["disk_total"] = parts[1]
                info["disk_used"] = parts[2]
                info["disk_avail"] = parts[3]
                info["disk_pct"] = parts[4]
    except Exception:
        pass
    
    # Uptime
    try:
        with open("/proc/uptime") as f:
            uptime_s = float(f.read().split()[0])
        info["uptime"] = _format_uptime(uptime_s)
    except Exception:
        info["uptime"] = "?"
    
    # Load average
    try:
        loadavg = os.getloadavg()
        info["load"] = f"{loadavg[0]:.2f} {loadavg[1]:.2f} {loadavg[2]:.2f}"
    except Exception:
        info["load"] = "?"
    
    # Tailscale
    ts = run(["tailscale", "status", "--json"], timeout=3)
    if ts:
        try:
            tsd = json.loads(ts)
            self_info = tsd.get("Self", {})
            ips = self_info.get("TailscaleIPs", [])
            info["tailscale_ip"] = ips[0] if ips else "?"
            suffix = tsd.get("MagicDNSSuffix", "")
            info["tailscale_dns"] = f"{self_info.get('HostName', 'hermes')}.{suffix}" if suffix else ""
            info["tailscale_online"] = self_info.get("Online", False)
        except (json.JSONDecodeError, KeyError):
            pass
    
    return info

def _format_uptime(seconds: float) -> str:
    """Format uptime seconds into human-readable string."""
    days = int(seconds // 86400)
    hours = int((seconds % 86400) // 3600)
    mins = int((seconds % 3600) // 60)
    parts = []
    if days > 0:
        parts.append(f"{days}d")
    if hours > 0 or days > 0:
        parts.append(f"{hours}h")
    parts.append(f"{mins}m")
    return " ".join(parts)

def get_hermes_info() -> dict:
    """Collect Hermes Agent information."""
    info = {}
    
    # Version
    version_out = run(["hermes", "--version"])
    info["version"] = version_out.split("·")[0].strip() if version_out else "unknown"
    
    # Config
    config = try_yaml(CONFIG_PATH)
    model_cfg = config.get("model", {})
    if isinstance(model_cfg, dict):
        info["model"] = model_cfg.get("default", "unknown")
        info["provider"] = model_cfg.get("provider", "unknown")
    else:
        info["model"] = str(model_cfg)
        info["provider"] = config.get("provider", "unknown")
    
    # API keys from .env
    env = read_env_file(ENV_FILE)
    info["has_openrouter_key"] = bool(env.get("OPENROUTER_API_KEY"))
    info["has_firecrawl_key"] = bool(env.get("FIRECRAWL_API_KEY"))
    info["has_kimi_key"] = bool(env.get("KIMI_API_KEY") or env.get("MOONSHOT_API_KEY"))
    
    # Telegram — token lives in .env, behavioral config in config.yaml
    tg_token = env.get("TELEGRAM_BOT_TOKEN", "")
    info["telegram"] = bool(tg_token)
    info["telegram_home"] = env.get("TELEGRAM_HOME_CHANNEL")
    
    # Response cache
    or_cfg = config.get("openrouter", {})
    info["response_cache"] = or_cfg.get("response_cache", False) if isinstance(or_cfg, dict) else False
    
    # Skills count
    skills = glob.glob(SKILLS_GLOB)
    info["skills_count"] = len(skills)
    
    # Sessions and messages from state.db
    if STATE_DB.exists():
        try:
            conn = sqlite3.connect(str(STATE_DB))
            c = conn.cursor()
            c.execute("SELECT COUNT(*) FROM sessions")
            info["sessions"] = c.fetchone()[0]
            c.execute("SELECT COUNT(*) FROM messages")
            info["messages"] = c.fetchone()[0]
            conn.close()
        except Exception:
            info["sessions"] = "?"
            info["messages"] = "?"
    else:
        info["sessions"] = 0
        info["messages"] = 0
    
    # Cron jobs
    if CRON_FILE.exists():
        try:
            raw = json.loads(CRON_FILE.read_text())
            # jobs.json is {"jobs": [...]} not a bare list
            jobs = raw.get("jobs", raw) if isinstance(raw, dict) else raw
            if isinstance(jobs, list):
                info["cron_total"] = len(jobs)
                info["cron_active"] = sum(1 for j in jobs if j.get("enabled", True))
            else:
                info["cron_total"] = "?"
                info["cron_active"] = "?"
        except Exception:
            info["cron_total"] = "?"
            info["cron_active"] = "?"
    else:
        info["cron_total"] = 0
        info["cron_active"] = 0
    
    # Gateway & dashboard — detect from listening ports
    gateway_pid = _find_port_pid(8642)
    dashboard_pid = _find_port_pid(9119)
    info["gateway_running"] = gateway_pid is not None
    info["gateway_pid"] = gateway_pid
    info["dashboard_running"] = dashboard_pid is not None
    info["dashboard_pid"] = dashboard_pid
    
    # Codex OAuth — auth.json has {"providers": {"openai-codex": {...}}, ...}
    auth_file = HERMES_HOME / "auth.json"
    if auth_file.exists():
        try:
            auth = json.loads(auth_file.read_text())
            providers = auth.get("providers", {})
            info["codex_auth"] = bool(providers.get("openai-codex"))
        except Exception:
            info["codex_auth"] = False
    else:
        info["codex_auth"] = False
    
    # Terminal backend
    info["terminal_backend"] = "local"
    info["sudo"] = os.geteuid() == 0 or run(["sudo", "-n", "true"], timeout=2) == ""
    
    return info

def _find_port_pid(port: int) -> int | None:
    """Find the PID listening on a given port using ss."""
    out = run(["ss", "-tlnp"], timeout=3)
    for line in out.split("\n"):
        if f":{port}" in line and "users:" in line:
            # Extract pid from users:(("proc",pid=12345,fd=..))
            try:
                pid_part = line.split("pid=")[1].split(",")[0]
                return int(pid_part)
            except (IndexError, ValueError):
                pass
    return None

def _format_mib(mib: int) -> str:
    """Format MiB value into human-readable string."""
    if mib >= 1024:
        return f"{mib / 1024:.1f}Gi"
    else:
        return f"{mib}Mi"

# ─── Display ──────────────────────────────────────────────────────────────────

def build_info_lines(sys_info: dict, hermes: dict, or_balance: dict | None,
                     colors: bool) -> list[tuple[str, str, str]]:
    """
    Build the info lines as (label, value, color_class) tuples.
    The color_class is applied to the label.
    """
    def c(text: str, color: str) -> str:
        return f"{color}{text}{C.RESET}" if colors else text
    
    def dim(text: str) -> str:
        return f"{C.DIM}{text}{C.RESET}" if colors else text
    
    lines = []
    
    # ── Hermes Section ──
    lines.append(("section", "HERMES AGENT", ""))
    
    lines.append(("version", 
        f"{c('Version', C.BCYAN)}{dim(':')}",
        hermes.get("version", "unknown")))
    
    lines.append(("model",
        f"{c('Model', C.BCYAN)}{dim(':')}",
        hermes.get("model", "unknown")))
    
    lines.append(("provider",
        f"{c('Provider', C.BCYAN)}{dim(':')}",
        hermes.get("provider", "unknown")))
    
    lines.append(("python",
        f"{c('Python', C.BCYAN)}{dim(':')}",
        sys_info.get("python", "?")))
    
    lines.append(("skills",
        f"{c('Skills', C.BCYAN)}{dim(':')}",
        str(hermes.get("skills_count", "?"))))
    
    lines.append(("sessions",
        f"{c('Sessions', C.BCYAN)}{dim(':')}",
        f"{hermes.get('sessions', '?')} ({hermes.get('messages', '?')} messages)"))
    
    cron_active = hermes.get("cron_active", "?")
    cron_total = hermes.get("cron_total", "?")
    lines.append(("cron",
        f"{c('Cron Jobs', C.BCYAN)}{dim(':')}",
        f"{cron_active} active / {cron_total} total"))
    
    # Gateway
    gw_status = f"{c('●', C.BGREEN)} running" if hermes.get("gateway_running") else f"{c('●', C.BRED)} stopped"
    gw_pid = hermes.get("gateway_pid")
    gw_str = f"{gw_status} (pid {gw_pid})" if gw_pid else gw_status
    lines.append(("gateway",
        f"{c('Gateway', C.BCYAN)}{dim(':')}",
        f"{gw_str} :8642"))
    
    # Dashboard
    dash_status = f"{c('●', C.BGREEN)} running" if hermes.get("dashboard_running") else f"{c('●', C.BRED)} stopped"
    dash_pid = hermes.get("dashboard_pid")
    dash_str = f"{dash_status} (pid {dash_pid})" if dash_pid else dash_status
    lines.append(("dashboard",
        f"{c('Dashboard', C.BCYAN)}{dim(':')}",
        f"{dash_str} :9119"))
    
    # Telegram
    if hermes.get("telegram"):
        tg_str = f"{c('●', C.BGREEN)} connected"
        if hermes.get("telegram_home"):
            tg_str += f" (home: {hermes['telegram_home']})"
    else:
        tg_str = f"{c('●', C.GRAY)} not configured"
    lines.append(("telegram",
        f"{c('Telegram', C.BCYAN)}{dim(':')}",
        tg_str))
    
    # Codex OAuth
    if hermes.get("codex_auth"):
        codex_str = f"{c('●', C.BGREEN)} logged in"
    else:
        codex_str = f"{c('●', C.GRAY)} not logged in"
    lines.append(("codex",
        f"{c('Codex OAuth', C.BCYAN)}{dim(':')}",
        codex_str))
    
    # Response cache
    cache_str = f"{c('●', C.BGREEN)} enabled" if hermes.get("response_cache") else f"{c('●', C.GRAY)} disabled"
    lines.append(("cache",
        f"{c('Resp Cache', C.BCYAN)}{dim(':')}",
        cache_str))
    
    # API Keys
    keys_parts = []
    if hermes.get("has_openrouter_key"):
        keys_parts.append(f"{c('OpenRouter', C.BGREEN)}")
    if hermes.get("has_firecrawl_key"):
        keys_parts.append(f"{c('Firecrawl', C.BGREEN)}")
    if hermes.get("has_kimi_key"):
        keys_parts.append(f"{c('Kimi', C.BGREEN)}")
    keys_str = " ".join(keys_parts) if keys_parts else f"{c('none', C.GRAY)}"
    lines.append(("keys",
        f"{c('API Keys', C.BCYAN)}{dim(':')}",
        keys_str))
    
    # ── OpenRouter Section ──
    lines.append(("section", "OPENROUTER BALANCE", ""))
    
    if or_balance:
        total = or_balance["total"]
        used = or_balance["used"]
        remaining = or_balance["remaining"]
        pct = (used / total * 100) if total > 0 else 0
        
        # Color the percentage based on usage
        if pct < 50:
            pct_color = C.BGREEN
        elif pct < 80:
            pct_color = C.BYELLOW
        else:
            pct_color = C.BRED
        
        lines.append(("or_total",
            f"{c('Credits', C.BMAGENTA)}{dim(':')}",
            f"${total:.2f}"))
        lines.append(("or_used",
            f"{c('Used', C.BMAGENTA)}{dim(':')}",
            f"${used:.2f} ({c(f'{pct:.1f}%', pct_color)})"))
        lines.append(("or_remaining",
            f"{c('Remaining', C.BMAGENTA)}{dim(':')}",
            f"${remaining:.2f}"))
        
        # Mini progress bar
        bar_width = 30
        filled = int(pct / 100 * bar_width)
        bar = "█" * filled + "░" * (bar_width - filled)
        if colors:
            bar = f"{pct_color}{bar}{C.RESET}"
        lines.append(("or_bar",
            f"{c('Usage', C.BMAGENTA)}{dim(':')}",
            f"[{bar}]"))
    else:
        lines.append(("or_none",
            f"{c('Credits', C.BMAGENTA)}{dim(':')}",
            f"{c('unavailable (no API key or network error)', C.GRAY)}"))
    
    # ── System Section ──
    lines.append(("section", "SYSTEM", ""))
    
    lines.append(("model",
        f"{c('Hardware', C.BYELLOW)}{dim(':')}",
        sys_info.get("model", "?")))
    
    lines.append(("os",
        f"{c('OS', C.BYELLOW)}{dim(':')}",
        sys_info.get("os", "?")))
    
    lines.append(("hostname",
        f"{c('Hostname', C.BYELLOW)}{dim(':')}",
        sys_info.get("hostname", "?")))
    
    lines.append(("cpu",
        f"{c('CPU', C.BYELLOW)}{dim(':')}",
        f"{sys_info.get('cpu_model', '?')} ({sys_info.get('cpu_cores', '?')} cores)"))
    
    mem_total = sys_info.get("mem_total", 0)
    mem_used = sys_info.get("mem_used", 0)
    mem_pct = (mem_used / mem_total * 100) if mem_total > 0 else 0
    lines.append(("memory",
        f"{c('Memory', C.BYELLOW)}{dim(':')}",
        f"{_format_mib(mem_used)} / {_format_mib(mem_total)} ({mem_pct:.0f}%)"))
    
    swap_total = sys_info.get("swap_total", 0)
    swap_used = sys_info.get("swap_used", 0)
    if swap_total > 0:
        lines.append(("swap",
            f"{c('Swap', C.BYELLOW)}{dim(':')}",
            f"{_format_mib(swap_used)} / {_format_mib(swap_total)}"))
    else:
        lines.append(("swap",
            f"{c('Swap', C.BYELLOW)}{dim(':')}",
            f"{c('disabled', C.GRAY)}"))
    
    lines.append(("disk",
        f"{c('Disk', C.BYELLOW)}{dim(':')}",
        f"{sys_info.get('disk_used', '?')} / {sys_info.get('disk_total', '?')} ({sys_info.get('disk_pct', '?')})"))
    
    lines.append(("uptime",
        f"{c('Uptime', C.BYELLOW)}{dim(':')}",
        sys_info.get("uptime", "?")))
    
    lines.append(("load",
        f"{c('Load', C.BYELLOW)}{dim(':')}",
        sys_info.get("load", "?")))
    
    # Tailscale
    if sys_info.get("tailscale_ip"):
        ts_status = f"{c('●', C.BGREEN)} online" if sys_info.get("tailscale_online") else f"{c('●', C.GRAY)} offline"
        lines.append(("tailscale",
            f"{c('Tailscale', C.BYELLOW)}{dim(':')}",
            f"{ts_status} {sys_info['tailscale_ip']}"))
        if sys_info.get("tailscale_dns"):
            lines.append(("tailscale_dns",
                f"{c('  DNS', C.GRAY)}{dim(':')}",
                sys_info["tailscale_dns"]))
    
    return lines

def display(logo_lines: list[str], info_lines: list[tuple[str, str, str]],
            colors: bool) -> None:
    """Render the logo and info side by side."""
    # Calculate logo width (max line length, ignoring ANSI codes)
    def visible_len(s: str) -> int:
        """Length of string without ANSI escape codes."""
        import re
        return len(re.sub(r'\033\[[0-9;]*m', '', s))
    
    logo_width = max(visible_len(l) for l in logo_lines)
    gap = 4  # spaces between logo and info
    
    # Build info display
    info_display = []
    first_section = True
    for entry in info_lines:
        if entry[0] == "section":
            # Add blank line before sections (except the first)
            if not first_section:
                info_display.append("")
            first_section = False
            # Section header — bold colored title with underline
            label = entry[1]
            if colors:
                header = f"{C.BOLD}{C.BWHITE}{label}{C.RESET}"
                underline = f"{C.DIM}{'─' * 42}{C.RESET}"
            else:
                header = label
                underline = "─" * 42
            info_display.append(header)
            info_display.append(underline)
        else:
            _, label, value = entry
            line = f"  {label} {value}"
            info_display.append(line)
    
    # Calculate total height
    total_height = max(len(logo_lines), len(info_display))
    
    # Print side by side
    print()
    for i in range(total_height):
        # Logo side
        if i < len(logo_lines):
            logo_line = logo_lines[i]
            logo_vis = visible_len(logo_line)
            padding = " " * (logo_width - logo_vis)
            left = f"{logo_line}{padding}"
        else:
            left = " " * logo_width
        
        # Info side
        if i < len(info_display):
            right = info_display[i]
        else:
            right = ""
        
        print(f"  {left}{' ' * gap}{right}")
    
    print()
    # Footer
    ts = time.strftime("%Y-%m-%d %H:%M:%S %Z")
    footer_text = f"hermes-fetch · {ts}"
    if colors:
        footer = f"  {C.DIM}{footer_text}{C.RESET}"
    else:
        footer = f"  {footer_text}"
    print(footer)
    print()

# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Hermes-fetch: Neofetch-style Hermes Agent status display."
    )
    parser.add_argument("--no-color", action="store_true",
                        help="Disable ANSI color output")
    parser.add_argument("--json", action="store_true",
                        help="Output as JSON instead of formatted display")
    args = parser.parse_args()
    
    colors = not args.no_color
    
    # ── Collect data ──
    sys_info = get_system_info()
    hermes = get_hermes_info()
    
    # OpenRouter balance
    env = read_env_file(ENV_FILE)
    or_key = env.get("OPENROUTER_API_KEY", "")
    or_balance = get_openrouter_balance(or_key)
    
    if args.json:
        output = {
            "hermes": hermes,
            "system": sys_info,
            "openrouter": or_balance,
        }
        print(json.dumps(output, indent=2, default=str))
        return
    
    # ── Display ──
    logo_lines = render_logo(colors)
    info_lines = build_info_lines(sys_info, hermes, or_balance, colors)
    display(logo_lines, info_lines, colors)


if __name__ == "__main__":
    main()
