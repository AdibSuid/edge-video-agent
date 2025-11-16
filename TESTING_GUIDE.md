# Testing Guide - Network Adaptation

## Overview

This guide covers testing the network adaptation features:
- ✅ Network speed monitoring
- ✅ Automatic frame rate reduction
- ✅ Resolution adaptation
- ✅ Telegram alerts

## Test Files

### 1. `test_network_adaptation.py`
**Unit and integration tests using unittest framework**

**Tests included:**
- Network speed detection
- Threshold-based triggering
- Frame rate adaptation
- Resolution changes
- Telegram notification sending
- Full integration workflows
- Simulated network conditions

**Run:**
```bash
python test_network_adaptation.py
```

**Expected Output:**
```
============================================================
EDGE AGENT - NETWORK ADAPTATION TEST SUITE
============================================================

test_initial_speed_detection ... ✓ Initial speed detected: 0.0 Mbps
ok
test_speed_threshold_detection ... ✓ Slow network detected: 1.5 Mbps < 2.0 Mbps
ok
test_speed_recovery_detection ... ✓ Network recovery detected: 5.0 Mbps
ok
...

============================================================
TEST SUMMARY
============================================================
Tests run: 18
Successes: 18
Failures: 0
Errors: 0
============================================================
```

---

### 2. `simulate_network_scenarios.py`
**Real-world simulation script with logging**

**Scenarios tested:**
1. **Gradual Degradation** - Speed slowly decreases
2. **Fluctuating Network** - Speed varies up and down
3. **Network Recovery** - Speed gradually improves
4. **Stress Test** - Rapid speed changes

**Run:**
```bash
python simulate_network_scenarios.py
```

**Expected Output:**
```
============================================================
EDGE AGENT - NETWORK ADAPTATION SIMULATION
============================================================

SCENARIO 1: Gradual Network Degradation
============================================================

[10:00:00] Network Speed: 5.0 Mbps
[10:00:00] Threshold: 2.0 Mbps
[10:00:00] Status: GOOD
[10:00:00]   → Quality: NORMAL (no change)

[10:00:01] Network Speed: 4.0 Mbps
[10:00:01] Threshold: 2.0 Mbps
[10:00:01] Status: GOOD
[10:00:01]   → Quality: NORMAL (no change)

...

[10:00:06] Network Speed: 1.8 Mbps
[10:00:06] Threshold: 2.0 Mbps
[10:00:06] Status: SLOW
[10:00:06] QUALITY_DEGRADED: Speed 1.8 < 2.0
[10:00:06]   → Quality: NORMAL → LOW (640x360)
[10:00:06]   → Bitrate: ~800 kbps → ~400 kbps
[10:00:06]   → Telegram alert: SENT

...

============================================================
SIMULATION REPORT
============================================================

Total Events: 4
  QUALITY_DEGRADED: 2
  QUALITY_RESTORED: 2

✓ Network monitoring: WORKING
✓ Speed detection: WORKING
✓ Quality adaptation: WORKING
✓ Threshold detection: WORKING
✓ Telegram alerts: ENABLED
```

---

## Running Tests

### Prerequisites

```bash
# Activate virtual environment
source venv/bin/activate  # Linux/Mac
# or
venv\Scripts\activate  # Windows

# Install test dependencies (if not already)
pip install -r requirements.txt
```

### Option 1: Run Unit Tests

```bash
cd edge-agent-motion
python test_network_adaptation.py
```

This will:
- Run 18+ automated tests
- Mock network conditions
- Test all components
- Generate test report

**Duration:** ~30 seconds

---

### Option 2: Run Simulation

```bash
cd edge-agent-motion
python simulate_network_scenarios.py
```

This will:
- Simulate 4 different network scenarios
- Log all quality changes
- Test Telegram alerts (if configured)
- Generate detailed log file

**Duration:** ~45 seconds

**Output Files:**
- `network_simulation.log` - Detailed simulation log

---

### Option 3: Run with Telegram Alerts

**Setup Telegram:**
```bash
# Export your Telegram credentials
export TELEGRAM_BOT_TOKEN="your_bot_token"
export TELEGRAM_CHAT_ID="your_chat_id"

# Run simulation
python simulate_network_scenarios.py
```

You'll receive actual Telegram messages when:
- Network speed drops below threshold
- Network speed recovers
- Quality mode changes

---

## Test Scenarios Explained

### Scenario 1: Gradual Degradation

**Purpose:** Test smooth quality transition as network slowly degrades

**Network Speeds:**
```
5.0 → 4.0 → 3.5 → 3.0 → 2.5 → 2.0 → 1.8 → 1.5 → 1.2 Mbps
```

**Expected Behavior:**
1. Start at 5.0 Mbps - Normal quality (1280x720)
2. Remains normal until 1.8 Mbps
3. **Trigger at 1.8 Mbps** - Switch to low quality (640x360)
4. Send Telegram alert
5. Continue at low quality for remaining speeds

**Log Output:**
```
[10:00:00] Network Speed: 5.0 Mbps → Quality: NORMAL
[10:00:01] Network Speed: 4.0 Mbps → Quality: NORMAL
...
[10:00:06] Network Speed: 1.8 Mbps → Quality: NORMAL → LOW ⚠️
[10:00:06]   → Telegram alert: SENT
[10:00:07] Network Speed: 1.5 Mbps → Quality: LOW
```

---

### Scenario 2: Fluctuating Network

**Purpose:** Test rapid quality switching with unstable connection

**Network Speeds:**
```
3.0 → 1.5 → 4.0 → 1.8 → 5.0 → 1.2 → 3.5 → 1.0 → 4.5 Mbps
```

**Expected Behavior:**
- Multiple quality transitions
- Telegram cooldown prevents spam
- System handles rapid changes

**Log Output:**
```
[10:00:00] Network Speed: 3.0 Mbps → Quality: NORMAL
[10:00:01] Network Speed: 1.5 Mbps → QUALITY_DEGRADED ⚠️
[10:00:02] Network Speed: 4.0 Mbps → QUALITY_RESTORED ✓
[10:00:03] Network Speed: 1.8 Mbps → QUALITY_DEGRADED ⚠️
[10:00:04] Network Speed: 5.0 Mbps → QUALITY_RESTORED ✓
...
```

---

### Scenario 3: Recovery

**Purpose:** Test restoration to normal quality as network improves

**Network Speeds:**
```
1.0 → 1.2 → 1.5 → 1.8 → 2.0 → 2.5 → 3.0 → 4.0 → 5.0 Mbps
```

**Expected Behavior:**
1. Start degraded at 1.0 Mbps - Low quality
2. Remains low until 2.0 Mbps
3. **Restore at 2.0 Mbps** - Switch to normal quality
4. Send recovery alert
5. Continue at normal quality

**Log Output:**
```
[10:00:00] Network Speed: 1.0 Mbps → Quality: LOW
[10:00:01] Network Speed: 1.2 Mbps → Quality: LOW
...
[10:00:04] Network Speed: 2.0 Mbps → Quality: LOW → NORMAL ✓
[10:00:04]   → Telegram alert: SENT (Recovery)
[10:00:05] Network Speed: 2.5 Mbps → Quality: NORMAL
```

---

### Scenario 4: Stress Test

**Purpose:** Test system stability with rapid changes

**Network Speeds:**
```
5.0 → 1.0 → 4.0 → 1.5 → 3.0 → 1.2 → 5.0 → 1.0 Mbps
(Changes every 0.5 seconds)
```

**Expected Behavior:**
- System remains stable
- No crashes or errors
- Cooldown prevents alert spam
- All transitions logged

---

## Interpreting Results

### Successful Test Indicators

✅ **All tests pass**
```
Tests run: 18
Successes: 18
Failures: 0
```

✅ **Quality changes logged**
```
QUALITY_DEGRADED: Speed 1.8 < 2.0
QUALITY_RESTORED: Speed 2.5 >= 2.0
```

✅ **Telegram alerts sent** (if configured)
```
→ Telegram alert: SENT
```

✅ **No crashes or exceptions**

---

### Common Issues

#### Issue 1: Import Errors

**Error:**
```
ModuleNotFoundError: No module named 'monitor'
```

**Fix:**
```bash
# Make sure you're in the project directory
cd edge-agent-motion

# Activate virtual environment
source venv/bin/activate
```

---

#### Issue 2: Telegram Not Configured

**Warning:**
```
⚠ Telegram alert: SKIPPED (not configured)
```

**This is OK!** Tests will still pass. To enable Telegram:
```bash
export TELEGRAM_BOT_TOKEN="your_token"
export TELEGRAM_CHAT_ID="your_chat_id"
```

---

#### Issue 3: GStreamer Warnings

**Warning:**
```
GStreamer-WARNING: ...
```

**This is OK!** These are informational warnings from GStreamer and don't affect tests.

---

## Manual Testing

### Test 1: Monitor Real Network Speed

```bash
# Start application
python app.py

# Open browser
http://localhost:5000

# Watch the network graph update every 5 seconds
```

---

### Test 2: Simulate Slow Network (Linux)

Using `tc` (traffic control):

```bash
# Install tc
sudo apt-get install iproute2

# Limit upload to 1 Mbps
sudo tc qdisc add dev eth0 root tbf rate 1mbit burst 32kbit latency 400ms

# Test - should trigger low quality mode
python simulate_network_scenarios.py

# Remove limit
sudo tc qdisc del dev eth0 root
```

---

### Test 3: Monitor with Wireshark

```bash
# Capture traffic on SRT port
sudo wireshark -i eth0 -f "udp port 9000"

# Start streaming
python app.py

# You'll see:
# - Normal: High packet rate
# - Degraded: Low packet rate
```

---

## Performance Benchmarks

### Expected Bandwidth Usage

| Network State | Resolution | FPS | Bitrate | Data/Hour |
|--------------|-----------|-----|---------|-----------|
| **Normal** | 1280x720 | 25 | ~800 kbps | ~350 MB |
| **Degraded** | 640x360 | 25 | ~400 kbps | ~175 MB |
| **Savings** | - | - | **50%** | **50%** |

### Expected CPU Usage

| State | CPU per Stream | 10 Streams |
|-------|---------------|------------|
| **Normal** | ~15% | ~150% (2 cores) |
| **Degraded** | ~8% | ~80% (1 core) |

---

## Continuous Testing

### Automated Testing Setup

Create `test_runner.sh`:

```bash
#!/bin/bash
# Run all tests

echo "Running unit tests..."
python test_network_adaptation.py

echo ""
echo "Running simulation..."
python simulate_network_scenarios.py

echo ""
echo "✓ All tests completed!"
```

Run regularly:
```bash
chmod +x test_runner.sh
./test_runner.sh
```

---

## Integration with CI/CD

### GitHub Actions Example

```yaml
# .github/workflows/test.yml
name: Test Network Adaptation

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - uses: actions/setup-python@v2
        with:
          python-version: '3.10'
      - run: pip install -r requirements.txt
      - run: python test_network_adaptation.py
```

---

## Troubleshooting Test Failures

### Test fails: "Speed detection not working"

**Check:**
1. Is `psutil` installed? `pip install psutil`
2. Run with admin/sudo if needed
3. Network interface exists and is active

---

### Test fails: "Telegram alert not sent"

**Check:**
1. Are credentials set? `echo $TELEGRAM_BOT_TOKEN`
2. Is bot token valid?
3. Is chat ID correct?
4. Is Telegram API accessible?

---

## Summary

✅ **Unit Tests** - Verify individual components  
✅ **Integration Tests** - Test full workflow  
✅ **Simulation** - Real-world scenarios  
✅ **Manual Tests** - Visual verification  
✅ **Performance Tests** - Benchmark results  

**Run both test suites to ensure complete coverage!**

---

## Quick Test Commands

```bash
# Full test suite (unit tests)
python test_network_adaptation.py

# Real-world simulation
python simulate_network_scenarios.py

# With Telegram alerts
TELEGRAM_BOT_TOKEN=xxx TELEGRAM_CHAT_ID=xxx python simulate_network_scenarios.py

# View simulation log
cat network_simulation.log
```

---

**All tests validate that the system:**
1. ✅ Monitors network speed continuously
2. ✅ Detects when speed drops below threshold
3. ✅ Reduces quality automatically (resolution + bitrate)
4. ✅ Sends Telegram alerts for slow network
5. ✅ Restores quality when network recovers
6. ✅ Handles rapid network fluctuations gracefully