# Systemd Service Installation

## Services Overview

This directory contains systemd service files for the market data infrastructure:

- **market-data-fetch.service** - Fetches data at 4:15 PM ET Mon-Fri
- **market-data-scan.service** - Runs scanners at 5:00 PM ET Mon-Fri
- **market-data-analyze.service** - Analyzes results at 9:00 AM ET Mon-Fri

## Installation Instructions

### 1. Copy service files to systemd directory

```bash
sudo cp /home/ubuntu/projects/md/systemd/*.service /etc/systemd/system/
```

### 2. Reload systemd daemon

```bash
sudo systemctl daemon-reload
```

### 3. Enable services to start on boot

```bash
sudo systemctl enable market-data-fetch.service
sudo systemctl enable market-data-scan.service
sudo systemctl enable market-data-analyze.service
```

### 4. Start services now

```bash
sudo systemctl start market-data-fetch.service
sudo systemctl start market-data-scan.service
sudo systemctl start market-data-analyze.service
```

## Management Commands

### Check service status

```bash
# Check all services
sudo systemctl status market-data-{fetch,scan,analyze}.service

# Check individual service
sudo systemctl status market-data-fetch.service
```

### View logs

```bash
# Service logs
sudo journalctl -u market-data-fetch.service -f
sudo journalctl -u market-data-scan.service -f
sudo journalctl -u market-data-analyze.service -f

# Application logs
tail -f /home/ubuntu/projects/md/logs/fetch-scheduler.log
tail -f /home/ubuntu/projects/md/logs/scan-scheduler.log
tail -f /home/ubuntu/projects/md/logs/analyze-scheduler.log
```

### Stop/Restart services

```bash
# Stop
sudo systemctl stop market-data-fetch.service

# Restart
sudo systemctl restart market-data-fetch.service

# Disable (prevent auto-start on boot)
sudo systemctl disable market-data-fetch.service
```

## Schedule Overview

| Service | Time (ET) | Days | Description |
|---------|-----------|------|-------------|
| market-data-fetch | 4:15 PM | Mon-Fri | Fetch daily candles, earnings, cleanup old data |
| market-data-scan | 5:00 PM | Mon-Fri | Run scanners on fetched data |
| market-data-analyze | 9:00 AM | Mon-Fri | Analyze results with trading agent |

## Troubleshooting

### Service fails to start

```bash
# Check detailed logs
sudo journalctl -u market-data-fetch.service -n 50 --no-pager

# Check syntax
sudo systemd-analyze verify /etc/systemd/system/market-data-fetch.service
```

### Service not running at expected time

```bash
# Check if service is active
sudo systemctl is-active market-data-fetch.service

# Check last run time
sudo journalctl -u market-data-fetch.service --since "today" | grep "Starting"
```

### Manual testing

Before enabling services, test them manually:

```bash
# Test fetch
python3 -m src.main fetch-data

# Test scan
python3 -m src.main scan

# Test analyze
python3 -m src.main analyze

# Test schedulers (run in foreground with Ctrl+C to stop)
python3 -m src.main schedule-fetch
python3 -m src.main schedule-scan
python3 -m src.main schedule-analyze
```

## Uninstallation

```bash
# Stop and disable services
sudo systemctl stop market-data-{fetch,scan,analyze}.service
sudo systemctl disable market-data-{fetch,scan,analyze}.service

# Remove service files
sudo rm /etc/systemd/system/market-data-*.service

# Reload systemd
sudo systemctl daemon-reload
```
