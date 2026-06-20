# hermes-fetch

A Neofetch-style system and Hermes Agent status display for your terminal.

Shows live Hermes Agent stats, OpenRouter credit balance, and system info in a single-page side-by-side layout with a caduceus ASCII art logo.

Pure Python 3 stdlib. No pip dependencies. Copy one file and run.

---

## Screenshot

```
              ▟█████████████████████▙    HERMES AGENT
             ▟█████▟███████████▙█████▙     ──────────────────────────────────────────
            ████████  ⚕  ☿  ⚕  ████████      Version: Hermes Agent v0.17.0 (2026.6.19)
            ███████████████████████████      Model: z-ai/glm-5.2
            ████████  ⚕  ☿  ⚕  ████████      Provider: openrouter
            ███████████████████████████      Python: 3.14.4
             ▜█████▜███████████▛█████▛       Skills: 71
                ▜█████████████████████▛      Sessions: 53 (5131 messages)
                   ▜█████████████▛           Cron Jobs: 1 active / 2 total
                     ▜█████████▛             Gateway: ● running (pid 11470) :8642
                ▟██▙  ▜███▛  ▟██▙            Dashboard: ● running (pid 7906) :9119
               ██   ██  ▟█▙  ██   ██         Telegram: ● connected (home: 8XXXXXXXXXX)
               ██   ██  ███  ██   ██         Codex OAuth: ● logged in
                ▜██▛  ▟█████▙  ▜██▛          Resp Cache: ● enabled
                   ▟███  ███  ███▙           API Keys: OpenRouter Firecrawl Kimi
                  ▟██▙  ▟█████▙  ▟██▙
                 ▟█▙   ███   ███  ▟█▙      OPENROUTER BALANCE
                 ▜██▛  ▜█████████▛ ▜██▛    ──────────────────────────────────────────
                                             Credits: $10.00
                                             Used: $0.71 (7.1%)
                                             Remaining: $9.29
                                             Usage: [██░░░░░░░░░░░░░░░░░░░░░░░░░░░░]

                                           SYSTEM
                                           ──────────────────────────────────────────
                                             Hardware: Raspberry Pi 5 Model B Rev 1.0
                                             OS: Linux 7.0.0-1011-raspi
                                             Hostname: hermes
                                             CPU: Raspberry Pi 5 Model B Rev 1.0 (4 cores)
                                             Memory: 1.4Gi / 7.7Gi (18%)
                                             Swap: disabled
                                             Disk: 21G / 235G (9%)
                                             Uptime: 16h 48m
                                             Load: 0.20 0.17 0.11
                                             Tailscale: ● online 100.XXXXXXXXX
                                               DNS: hermes.XXXXXXXXXX

```

---

## Requirements

- Python 3.10+ (uses `match`-free syntax, but needs `list[str]` type hints — 3.9+ with `from __future__ import annotations` works too, but 3.10+ is simplest)
- Hermes Agent installed at `~/.hermes` (or set `HERMES_HOME` env var)
- An OpenRouter API key in `~/.hermes/.env` (for balance display)
- Linux (reads `/proc` for system stats; other platforms will show partial data)

No pip packages needed. The script ships with a manual YAML fallback parser if PyYAML is not installed.

---

## Installation

### Option A: Direct download

```bash
curl -o ~/hermes-fetch.py https://raw.githubusercontent.com/USER/REPO/main/hermes-fetch.py
chmod +x ~/hermes-fetch.py
```

### Option B: Just copy the file

Save `hermes-fetch.py` anywhere on your system. Make it executable:

```bash
chmod +x hermes-fetch.py
```

### Option C: Symlink to PATH

```bash
chmod +x ~/hermes-fetch.py
sudo ln -s ~/hermes-fetch.py /usr/local/bin/hermes-fetch
```

Then run from anywhere:

```bash
hermes-fetch
```

---

## Usage

```bash
python3 hermes-fetch.py              # full color display (default)
python3 hermes-fetch.py --no-color   # plain text, no ANSI codes
python3 hermes-fetch.py --json       # JSON output for scripting
python3 hermes-fetch.py --help       # show help
```

### Flags

| Flag          | Description                                      |
|---------------|--------------------------------------------------|
| `--no-color`  | Disable ANSI color codes (for pipes, logs, etc.) |
| `--json`      | Output all data as JSON instead of formatted view|
| `--help`      | Show usage help                                  |

---

## What It Shows

### HERMES AGENT

| Field        | Source                                      |
|--------------|---------------------------------------------|
| Version      | `hermes --version`                          |
| Model        | `~/.hermes/config.yaml` → `model.default`   |
| Provider     | `~/.hermes/config.yaml` → `model.provider`  |
| Python       | `platform.python_version()`                 |
| Skills       | Count of `~/.hermes/skills/*/*/SKILL.md`    |
| Sessions     | `~/.hermes/state.db` → `sessions` table     |
| Messages     | `~/.hermes/state.db` → `messages` table     |
| Cron Jobs    | `~/.hermes/cron/jobs.json`                  |
| Gateway      | Port 8642 listener check via `ss`           |
| Dashboard    | Port 9119 listener check via `ss`           |
| Telegram     | `TELEGRAM_BOT_TOKEN` in `~/.hermes/.env`    |
| Codex OAuth  | `~/.hermes/auth.json` → `providers`         |
| Resp Cache   | `~/.hermes/config.yaml` → `openrouter`      |
| API Keys     | `~/.hermes/.env` (OpenRouter, Firecrawl, Kimi)|

### OPENROUTER BALANCE

| Field      | Source                                      |
|------------|---------------------------------------------|
| Credits    | `GET https://openrouter.ai/api/v1/credits`  |
| Used       | Same API, `total_usage` field               |
| Remaining  | `total_credits - total_usage`               |
| Usage bar  | Visual percentage bar (color-coded)         |

The usage percentage changes color: green under 50%, yellow 50-80%, red above 80%.

### SYSTEM

| Field     | Source                        |
|-----------|-------------------------------|
| Hardware  | `/proc/device-tree/model`     |
| OS        | `platform.system()` + version |
| Hostname  | `platform.node()`             |
| CPU       | `/proc/cpuinfo`               |
| Memory    | `/proc/meminfo`               |
| Swap      | `/proc/meminfo`               |
| Disk      | `df -h /`                     |
| Uptime    | `/proc/uptime`                |
| Load      | `os.getloadavg()`             |
| Tailscale | `tailscale status --json`     |

---

## Environment Variables

| Variable         | Default     | Description                         |
|------------------|-------------|-------------------------------------|
| `HERMES_HOME`    | `~/.hermes` | Path to Hermes Agent home directory |

---

## Portability

The script is a single file with zero external dependencies:

- No pip install needed
- No virtual environment needed
- Falls back to a manual YAML parser if PyYAML is not available
- Uses only stdlib: `json`, `os`, `platform`, `sqlite3`, `subprocess`, `urllib`, `pathlib`, `re`, `time`, `argparse`, `glob`

It calls these external commands (all optional — missing commands show `?` or skip gracefully):

- `hermes` — for version string
- `ss` — for gateway/dashboard port detection
- `df` — for disk usage
- `tailscale` — for Tailscale IP/DNS

If any command is missing, the corresponding field shows `?` or is omitted. The script never crashes on missing data.

---

## JSON Output

For scripting or integration with other tools:

```bash
python3 hermes-fetch.py --json
```

```json
{
  "hermes": {
    "version": "Hermes Agent v0.17.0 (2026.6.19)",
    "model": "z-ai/glm-5.2",
    "provider": "openrouter",
    "skills_count": 71,
    "sessions": 53,
    "messages": 5131,
    "cron_active": 1,
    "cron_total": 2,
    "gateway_running": true,
    "dashboard_running": true,
    ...
  },
  "system": {
    "model": "Raspberry Pi 5 Model B Rev 1.0",
    "os": "Linux 7.0.0-1011-raspi",
    "cpu_cores": 4,
    "mem_total": 7932,
    ...
  },
  "openrouter": {
    "total": 10.0,
    "used": 0.71,
    "remaining": 9.29
  }
}
```

---

## Terminal Width

Optimized for 100-character width or wider. The longest output line is approximately 90 characters (system info lines with long hardware model names).

On narrower terminals the info column may wrap or misalign. For best results:

```bash
# Check your terminal width
tput cols
```

---

## Tips

### Run on login

Add to your `~/.bashrc` or `~/.zshrc`:

```bash
# Show hermes-fetch on terminal open (only in interactive shells)
if [[ $- == *i* ]] && command -v python3 &>/dev/null; then
    python3 ~/hermes-fetch.py
fi
```

### Cron job for balance monitoring

```bash
# Check OpenRouter balance daily, warn if below $2
0 9 * * * python3 ~/hermes-fetch.py --json | python3 -c "
import json, sys
d = json.load(sys.stdin)['openrouter']
if d and d['remaining'] < 2:
    print(f'Low OpenRouter balance: \${d[\"remaining\"]:.2f} remaining')
" 2>/dev/null
```

### Pipe without color codes

```bash
python3 hermes-fetch.py --no-color | less
```

---

## Troubleshooting

**OpenRouter balance shows "unavailable"**
- Ensure `OPENROUTER_API_KEY` is set in `~/.hermes/.env`
- Check network connectivity to `openrouter.ai`
- Verify the key is valid at https://openrouter.ai/keys

**Gateway shows "stopped" but it's running**
- The script checks port 8642 via `ss`. If your gateway runs on a different port, the detector won't find it.
- Ensure `ss` is installed (`iproute2` package on most distros)

**Tailscale info missing**
- Ensure `tailscale` CLI is installed and in PATH
- The script calls `tailscale status --json` with a 3-second timeout

**Cron jobs show "?"**
- Check that `~/.hermes/cron/jobs.json` exists and is valid JSON
- The file should have a `"jobs"` key containing an array

---

## License

MIT

---

## Author

Built by Belle (Hermes Agent) for Rachael, June 2026.
