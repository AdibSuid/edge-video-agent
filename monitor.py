# monitor.py
import psutil
import time
import threading
from datetime import datetime

class NetworkMonitor:
    """Monitor network upload speed and connection quality"""
    
    def __init__(self, threshold_mbps=2.0, check_interval=5):
        """
        Initialize network monitor
        
        Args:
            threshold_mbps: Threshold in Mbps for triggering low quality mode
            check_interval: Seconds between speed checks
        """
        self.threshold_mbps = threshold_mbps
        self.check_interval = check_interval
        self.current_upload_mbps = 0.0
        self.is_slow = False
        self.running = False
        self.monitor_thread = None
        self.last_bytes_sent = 0
        self.last_check_time = time.time()
        self.history = []  # Keep last N measurements
        self.max_history = 60  # 5 minutes at 5-second intervals
        self.lock = threading.Lock()
        
    def start(self):
        """Start monitoring thread"""
        if not self.running:
            self.running = True
            self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
            self.monitor_thread.start()
            print("Network monitor started")
    
    def stop(self):
        """Stop monitoring thread"""
        self.running = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=2)
            print("Network monitor stopped")
    
    def _monitor_loop(self):
        """Main monitoring loop"""
        # Initialize
        net_io = psutil.net_io_counters()
        self.last_bytes_sent = net_io.bytes_sent
        self.last_check_time = time.time()
        
        while self.running:
            try:
                time.sleep(self.check_interval)
                
                # Get current network stats
                net_io = psutil.net_io_counters()
                current_bytes_sent = net_io.bytes_sent
                current_time = time.time()
                
                # Calculate upload speed
                bytes_diff = current_bytes_sent - self.last_bytes_sent
                time_diff = current_time - self.last_check_time
                
                if time_diff > 0:
                    bytes_per_second = bytes_diff / time_diff
                    mbps = (bytes_per_second * 8) / (1024 * 1024)  # Convert to Mbps
                    
                    with self.lock:
                        self.current_upload_mbps = mbps
                        
                        # Update history
                        self.history.append({
                            'timestamp': datetime.now().isoformat(),
                            'mbps': round(mbps, 2)
                        })
                        
                        # Trim history
                        if len(self.history) > self.max_history:
                            self.history = self.history[-self.max_history:]
                        
                        # Check if speed is below threshold
                        was_slow = self.is_slow
                        self.is_slow = mbps < self.threshold_mbps
                        
                        # Log state changes
                        if self.is_slow and not was_slow:
                            print(f"⚠️ Network slow: {mbps:.2f} Mbps (threshold: {self.threshold_mbps} Mbps)")
                        elif not self.is_slow and was_slow:
                            print(f"✓ Network recovered: {mbps:.2f} Mbps")
                
                # Update for next iteration
                self.last_bytes_sent = current_bytes_sent
                self.last_check_time = current_time
                
            except Exception as e:
                print(f"Monitor error: {e}")
                time.sleep(self.check_interval)
    
    def get_current_speed(self):
        """Get current upload speed in Mbps"""
        with self.lock:
            return round(self.current_upload_mbps, 2)
    
    def get_status(self):
        """Get current network status"""
        with self.lock:
            return {
                'upload_mbps': round(self.current_upload_mbps, 2),
                'is_slow': self.is_slow,
                'threshold_mbps': self.threshold_mbps,
                'timestamp': datetime.now().isoformat()
            }
    
    def get_history(self, minutes=5):
        """Get speed history for last N minutes"""
        with self.lock:
            # Calculate how many records to return
            num_records = min(len(self.history), (minutes * 60) // self.check_interval)
            return self.history[-num_records:] if num_records > 0 else []
    
    def set_threshold(self, threshold_mbps):
        """Update threshold"""
        with self.lock:
            self.threshold_mbps = threshold_mbps
            print(f"Network threshold updated to {threshold_mbps} Mbps")


class TelegramNotifier:
    """Send Telegram notifications for network issues"""
    
    def __init__(self, bot_token, chat_id):
        """
        Initialize Telegram notifier
        
        Args:
            bot_token: Telegram bot token
            chat_id: Telegram chat ID
        """
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.enabled = bool(bot_token and chat_id)
        self.last_alert_time = {}
        self.alert_cooldown = 300  # 5 minutes between alerts
        
    def send_alert(self, message, alert_type='network'):
        """
        Send alert via Telegram with cooldown
        
        Args:
            message: Alert message
            alert_type: Type of alert for cooldown tracking
        """
        if not self.enabled:
            return False
        
        # Check cooldown
        now = time.time()
        if alert_type in self.last_alert_time:
            if now - self.last_alert_time[alert_type] < self.alert_cooldown:
                return False  # Still in cooldown
        
        try:
            import requests
            
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            data = {
                'chat_id': self.chat_id,
                'text': f"🚨 Edge Agent Alert\n\n{message}",
                'parse_mode': 'HTML'
            }
            
            response = requests.post(url, data=data, timeout=10)
            
            if response.status_code == 200:
                self.last_alert_time[alert_type] = now
                print(f"Telegram alert sent: {message}")
                return True
            else:
                print(f"Telegram send failed: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"Telegram error: {e}")
            return False
    
    def send_network_slow_alert(self, current_mbps, threshold_mbps):
        """Send network slow alert"""
        message = (
            f"⚠️ <b>Network Speed Alert</b>\n\n"
            f"Upload speed: <b>{current_mbps:.2f} Mbps</b>\n"
            f"Threshold: {threshold_mbps} Mbps\n\n"
            f"Switching to low quality mode..."
        )
        return self.send_alert(message, 'network_slow')
    
    def send_network_recovered_alert(self, current_mbps):
        """Send network recovered alert"""
        message = (
            f"✅ <b>Network Recovered</b>\n\n"
            f"Upload speed: <b>{current_mbps:.2f} Mbps</b>\n\n"
            f"Switching back to normal quality..."
        )
        return self.send_alert(message, 'network_recovered')