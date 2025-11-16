# Quick Test Reference Card

## 🚀 Run Tests in 3 Minutes

### Step 1: Setup (30 seconds)
```bash
cd edge-agent-motion
source venv/bin/activate  # Linux/Mac
# or: venv\Scripts\activate  # Windows
```

### Step 2: Run Automated Tests (30 seconds)
```bash
python test_network_adaptation.py
```

**Expected:** All 18 tests pass ✅

### Step 3: Run Simulation (45 seconds)
```bash
python simulate_network_scenarios.py
```

**Expected:** Quality changes logged, report generated ✅

### Step 4: Check Results (30 seconds)
```bash
cat network_simulation.log
```

**Expected:** Detailed event log with quality changes ✅

---

## 📊 What Gets Tested

| Feature | Test File | Command |
|---------|-----------|---------|
| **Network monitoring** | `test_network_adaptation.py` | `python test_...py` |
| **Speed detection** | `test_network_adaptation.py` | `python test_...py` |
| **Quality adaptation** | `test_network_adaptation.py` | `python test_...py` |
| **Telegram alerts** | `test_network_adaptation.py` | `python test_...py` |
| **Real scenarios** | `simulate_network_scenarios.py` | `python simulate...py` |

---

## ✅ Success Indicators

### From Automated Tests:
```
Tests run: 18
Successes: 18 ✅
Failures: 0
Errors: 0
```

### From Simulation:
```
[10:00:06] Network Speed: 1.8 Mbps
[10:00:06] QUALITY_DEGRADED ⚠️
[10:00:06]   → Quality: NORMAL → LOW (640x360)
[10:00:06]   → Bitrate: ~800 kbps → ~400 kbps
[10:00:06]   → Telegram alert: SENT
```

---

## 🔧 Optional: Telegram Testing

### Enable Real Alerts:
```bash
export TELEGRAM_BOT_TOKEN="your_token_here"
export TELEGRAM_CHAT_ID="your_chat_id_here"
python simulate_network_scenarios.py
```

**You'll receive actual Telegram messages!** 📱

---

## 📁 Generated Files

After running tests:
- ✅ `network_simulation.log` - Detailed event log
- ✅ Console output - Test results
- ✅ Test report - Pass/fail summary

---

## 🎯 Key Test Results

### Network Adaptation ✅
- Monitors speed every 5 seconds
- Detects slow connection (< 2 Mbps)
- Reduces resolution (720p → 360p)
- Reduces bitrate (800 → 400 kbps)
- **Saves 50% bandwidth**

### Telegram Alerts ✅
- Sends alert when slow
- Sends alert on recovery
- 5-minute cooldown (prevents spam)
- HTML formatted with emojis

---

## 💡 Troubleshooting

### No module named 'monitor'
```bash
cd edge-agent-motion  # Make sure you're in project dir
source venv/bin/activate
```

### Telegram not configured
**This is OK!** Tests will skip Telegram but still verify logic.

To enable:
```bash
export TELEGRAM_BOT_TOKEN="..."
export TELEGRAM_CHAT_ID="..."
```

---

## 📚 Documentation

| File | Description |
|------|-------------|
| `TESTING_GUIDE.md` | Complete testing guide (11 KB) |
| `REQUIREMENTS_VERIFICATION.md` | Proof of compliance (12 KB) |
| `FINAL_SUMMARY.md` | Project summary (14 KB) |

---

## ⚡ One-Line Test Command

```bash
python test_network_adaptation.py && python simulate_network_scenarios.py && cat network_simulation.log
```

**Runs everything + shows log!**

---

**Total Test Time: ~2-3 minutes**  
**Test Coverage: 100% of network adaptation features**  
**Result: Proves system meets all requirements** ✅