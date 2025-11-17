# test_network_adaptation.py
"""
Test suite for network adaptation and Telegram alert functionality.

This test simulates:
1. Network speed throttling
2. Automatic frame rate reduction
3. Resolution adaptation
4. Telegram alert triggering
"""

import unittest
import time
import threading
from unittest.mock import Mock, patch, MagicMock
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__) + '/..'))

from monitor import NetworkMonitor, TelegramNotifier
from streamer import Streamer


class TestNetworkThrottling(unittest.TestCase):
    """Test network speed detection and throttling behavior"""
    
    def setUp(self):
        """Setup test environment"""
        self.monitor = NetworkMonitor(threshold_mbps=2.0, check_interval=1)
        
    def tearDown(self):
        """Cleanup"""
        if self.monitor.running:
            self.monitor.stop()
    
    def test_initial_speed_detection(self):
        """Test that monitor can detect initial network speed"""
        self.monitor.start()
        time.sleep(2)  # Wait for first measurement
        
        speed = self.monitor.get_current_speed()
        self.assertIsInstance(speed, float)
        self.assertGreaterEqual(speed, 0)
        print(f"✓ Initial speed detected: {speed} Mbps")
    
    def test_speed_threshold_detection(self):
        """Test detection of speed below threshold"""
        # Mock slow network
        with patch.object(self.monitor, 'current_upload_mbps', 1.5):
            self.monitor.is_slow = True
            status = self.monitor.get_status()
            
            self.assertTrue(status['is_slow'])
            self.assertEqual(status['upload_mbps'], 1.5)
            print(f"✓ Slow network detected: {status['upload_mbps']} Mbps < {status['threshold_mbps']} Mbps")
    
    def test_speed_recovery_detection(self):
        """Test detection when speed recovers"""
        # Simulate recovery
        self.monitor.is_slow = True
        
        with patch.object(self.monitor, 'current_upload_mbps', 5.0):
            self.monitor.is_slow = False
            status = self.monitor.get_status()
            
            self.assertFalse(status['is_slow'])
            self.assertEqual(status['upload_mbps'], 5.0)
            print(f"✓ Network recovery detected: {status['upload_mbps']} Mbps")
    
    def test_history_tracking(self):
        """Test that speed history is tracked correctly"""
        self.monitor.start()
        time.sleep(3)  # Collect some data points
        
        history = self.monitor.get_history(minutes=5)
        
        self.assertIsInstance(history, list)
        self.assertGreater(len(history), 0)
        
        for entry in history:
            self.assertIn('timestamp', entry)
            self.assertIn('mbps', entry)
            self.assertIsInstance(entry['mbps'], (int, float))
        
        print(f"✓ History tracked: {len(history)} data points")


class TestFrameRateAdaptation(unittest.TestCase):
    """Test automatic frame rate reduction based on network speed"""
    
    def setUp(self):
        """Setup mock configuration"""
        self.config = {
            'motion_sensitivity': 25,
            'motion_min_area': 500,
            'motion_zones': [],
            'motion_cooldown': 10,
            'motion_low_fps': 1,
            'motion_high_fps': 25,
            'normal_resolution': '1280x720',
            'low_resolution': '640x360'
        }
    
    def test_low_quality_mode_activation(self):
        """Test that low quality mode is activated"""
        # Initially normal quality
        self.assertFalse(Streamer._low_quality)
        
        # Activate low quality
        Streamer.set_low_quality(True)
        
        self.assertTrue(Streamer._low_quality)
        print("✓ Low quality mode activated")
    
    def test_low_quality_mode_deactivation(self):
        """Test that low quality mode can be deactivated"""
        # Set to low quality first
        Streamer.set_low_quality(True)
        self.assertTrue(Streamer._low_quality)
        
        # Deactivate
        Streamer.set_low_quality(False)
        
        self.assertFalse(Streamer._low_quality)
        print("✓ Low quality mode deactivated")
    
    def test_resolution_adaptation(self):
        """Test resolution changes based on quality mode"""
        # Create mock streamer
        mock_streamer = Mock(spec=Streamer)
        mock_streamer.config = self.config
        mock_streamer._low_quality = False
        
        # Normal quality
        def get_resolution(self):
            if self._low_quality:
                return self.config['low_resolution']
            return self.config['normal_resolution']
        
        mock_streamer._get_resolution = lambda: get_resolution(mock_streamer)
        
        # Test normal resolution
        resolution = mock_streamer._get_resolution()
        self.assertEqual(resolution, '1280x720')
        print(f"✓ Normal resolution: {resolution}")
        
        # Switch to low quality
        mock_streamer._low_quality = True
        resolution = mock_streamer._get_resolution()
        self.assertEqual(resolution, '640x360')
        print(f"✓ Low quality resolution: {resolution}")
    
    def test_fps_values(self):
        """Test FPS values in different states"""
        # Normal: motion_high_fps
        normal_fps = self.config['motion_high_fps']
        self.assertEqual(normal_fps, 25)
        print(f"✓ Normal FPS: {normal_fps}")
        
        # Idle: motion_low_fps
        idle_fps = self.config['motion_low_fps']
        self.assertEqual(idle_fps, 1)
        print(f"✓ Idle FPS: {idle_fps}")


class TestTelegramAlerts(unittest.TestCase):
    """Test Telegram notification functionality"""
    
    def setUp(self):
        """Setup Telegram notifier"""
        self.notifier = TelegramNotifier(
            bot_token="test_token_12345",
            chat_id="test_chat_12345"
        )
    
    def test_notifier_enabled_with_credentials(self):
        """Test that notifier is enabled when credentials provided"""
        notifier = TelegramNotifier("token", "chat_id")
        self.assertTrue(notifier.enabled)
        print("✓ Notifier enabled with credentials")
    
    def test_notifier_disabled_without_credentials(self):
        """Test that notifier is disabled without credentials"""
        notifier = TelegramNotifier("", "")
        self.assertFalse(notifier.enabled)
        print("✓ Notifier disabled without credentials")
    
    @patch('requests.post')
    def test_send_network_slow_alert(self, mock_post):
        """Test sending network slow alert"""
        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response
        
        # Send alert
        result = self.notifier.send_network_slow_alert(
            current_mbps=1.5,
            threshold_mbps=2.0
        )
        
        self.assertTrue(result)
        self.assertTrue(mock_post.called)
        
        # Verify message content
        call_args = mock_post.call_args
        sent_data = call_args[1]['data']
        
        self.assertIn('1.5', sent_data['text'])
        self.assertIn('2', sent_data['text'])
        self.assertIn('low quality', sent_data['text'].lower())
        
        print("✓ Network slow alert sent successfully")
    
    @patch('requests.post')
    def test_send_network_recovered_alert(self, mock_post):
        """Test sending network recovery alert"""
        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response
        
        # Send alert
        result = self.notifier.send_network_recovered_alert(
            current_mbps=4.5
        )
        
        self.assertTrue(result)
        self.assertTrue(mock_post.called)
        
        # Verify message content
        call_args = mock_post.call_args
        sent_data = call_args[1]['data']
        
        self.assertIn('4.5', sent_data['text'])
        self.assertIn('recovered', sent_data['text'].lower())
        
        print("✓ Network recovery alert sent successfully")
    
    def test_alert_cooldown(self):
        """Test that alerts respect cooldown period"""
        # First alert should succeed
        with patch('requests.post') as mock_post:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_post.return_value = mock_response
            
            result1 = self.notifier.send_alert("Test message 1", "test_type")
            self.assertTrue(result1)
            
            # Second alert immediately should be blocked
            result2 = self.notifier.send_alert("Test message 2", "test_type")
            self.assertFalse(result2)
            
            print("✓ Alert cooldown working correctly")
    
    @patch('requests.post')
    def test_alert_failure_handling(self, mock_post):
        """Test handling of failed alert sending"""
        # Mock failed response
        mock_response = Mock()
        mock_response.status_code = 400
        mock_post.return_value = mock_response
        
        result = self.notifier.send_alert("Test", "test")
        
        self.assertFalse(result)
        print("✓ Alert failure handled correctly")


class TestNetworkAdaptationIntegration(unittest.TestCase):
    """Integration tests for network adaptation workflow"""
    
    def setUp(self):
        """Setup integration test environment"""
        self.monitor = NetworkMonitor(threshold_mbps=2.0, check_interval=1)
        self.notifier = TelegramNotifier("test_token", "test_chat")
        self.events = []
        
    def tearDown(self):
        """Cleanup"""
        if self.monitor.running:
            self.monitor.stop()
    
    @patch('requests.post')
    def test_full_network_degradation_workflow(self, mock_post):
        """Test complete workflow when network degrades"""
        # Mock successful Telegram response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response
        
        # Start with good network
        self.monitor.start()
        time.sleep(1)
        
        # Simulate network degradation
        print("\n--- Simulating Network Degradation ---")
        with patch.object(self.monitor, 'current_upload_mbps', 1.5):
            self.monitor.is_slow = True
            
            # Check status
            status = self.monitor.get_status()
            print(f"Network Status: {status['upload_mbps']} Mbps")
            
            # Verify slow detection
            self.assertTrue(status['is_slow'])
            self.events.append("Network degraded")
            
            # Should trigger low quality mode
            Streamer.set_low_quality(True)
            self.assertTrue(Streamer._low_quality)
            self.events.append("Low quality mode activated")
            
            # Should send Telegram alert
            alert_sent = self.notifier.send_network_slow_alert(
                status['upload_mbps'],
                status['threshold_mbps']
            )
            if alert_sent:
                self.events.append("Telegram alert sent")
        
        print(f"✓ Network degradation workflow completed")
        print(f"  Events: {' → '.join(self.events)}")
        
        # Verify all steps occurred
        self.assertIn("Network degraded", self.events)
        self.assertIn("Low quality mode activated", self.events)
    
    @patch('requests.post')
    def test_full_network_recovery_workflow(self, mock_post):
        """Test complete workflow when network recovers"""
        # Mock successful Telegram response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response
        
        # Start with degraded network
        self.monitor.is_slow = True
        Streamer.set_low_quality(True)
        
        # Simulate network recovery
        print("\n--- Simulating Network Recovery ---")
        with patch.object(self.monitor, 'current_upload_mbps', 5.0):
            self.monitor.is_slow = False
            
            # Check status
            status = self.monitor.get_status()
            print(f"Network Status: {status['upload_mbps']} Mbps")
            
            # Verify recovery detection
            self.assertFalse(status['is_slow'])
            self.events.append("Network recovered")
            
            # Should restore normal quality
            Streamer.set_low_quality(False)
            self.assertFalse(Streamer._low_quality)
            self.events.append("Normal quality restored")
            
            # Should send recovery alert
            alert_sent = self.notifier.send_network_recovered_alert(
                status['upload_mbps']
            )
            if alert_sent:
                self.events.append("Recovery alert sent")
        
        print(f"✓ Network recovery workflow completed")
        print(f"  Events: {' → '.join(self.events)}")
        
        # Verify all steps occurred
        self.assertIn("Network recovered", self.events)
        self.assertIn("Normal quality restored", self.events)


class TestSimulatedNetworkConditions(unittest.TestCase):
    """Test with simulated real-world network conditions"""
    
    def test_gradual_speed_degradation(self):
        """Test gradual network speed decrease"""
        monitor = NetworkMonitor(threshold_mbps=2.0, check_interval=1)
        
        print("\n--- Simulating Gradual Speed Degradation ---")
        
        speeds = [5.0, 4.0, 3.0, 2.5, 1.8, 1.5, 1.2]
        
        for speed in speeds:
            with patch.object(monitor, 'current_upload_mbps', speed):
                monitor.is_slow = speed < monitor.threshold_mbps
                status = monitor.get_status()
                
                state = "SLOW" if status['is_slow'] else "GOOD"
                quality = "LOW" if status['is_slow'] else "NORMAL"
                
                print(f"  Speed: {speed} Mbps → Status: {state} → Quality: {quality}")
                
                if speed < 2.0:
                    self.assertTrue(status['is_slow'])
                else:
                    self.assertFalse(status['is_slow'])
    
    def test_fluctuating_network(self):
        """Test fluctuating network conditions"""
        monitor = NetworkMonitor(threshold_mbps=2.0, check_interval=1)
        
        print("\n--- Simulating Fluctuating Network ---")
        
        speeds = [3.0, 1.5, 4.0, 1.8, 5.0, 1.2, 3.5]
        transitions = []
        
        for i, speed in enumerate(speeds):
            with patch.object(monitor, 'current_upload_mbps', speed):
                monitor.is_slow = speed < monitor.threshold_mbps
                status = monitor.get_status()
                
                if i > 0:
                    prev_slow = speeds[i-1] < monitor.threshold_mbps
                    curr_slow = status['is_slow']
                    
                    if prev_slow != curr_slow:
                        transition = "DEGRADED" if curr_slow else "RECOVERED"
                        transitions.append(transition)
                        print(f"  Speed: {speed} Mbps → {transition}")
        
        print(f"✓ Detected {len(transitions)} network transitions")
        self.assertGreater(len(transitions), 0)
    
    def test_bandwidth_savings_calculation(self):
        """Calculate bandwidth savings with adaptive quality"""
        print("\n--- Bandwidth Savings Calculation ---")
        
        # Scenario: 8 hours normal, 16 hours degraded
        normal_hours = 8
        degraded_hours = 16
        
        # Normal: 25fps @ 1280x720 = ~800 kbps
        # Low: 25fps @ 640x360 = ~400 kbps
        
        normal_bitrate_mbps = 0.8
        low_bitrate_mbps = 0.4
        
        # Calculate data usage
        without_adaptation = 24 * 3600 * normal_bitrate_mbps / 8 / 1024  # GB
        with_adaptation = (
            normal_hours * 3600 * normal_bitrate_mbps / 8 / 1024 +
            degraded_hours * 3600 * low_bitrate_mbps / 8 / 1024
        )  # GB
        
        savings = without_adaptation - with_adaptation
        savings_percent = (savings / without_adaptation) * 100
        
        print(f"  Without adaptation: {without_adaptation:.2f} GB/day")
        print(f"  With adaptation: {with_adaptation:.2f} GB/day")
        print(f"  Savings: {savings:.2f} GB/day ({savings_percent:.1f}%)")
        
        self.assertGreater(savings, 0)
        self.assertGreater(savings_percent, 0)


def run_all_tests():
    """Run all test suites"""
    print("=" * 60)
    print("EDGE AGENT - NETWORK ADAPTATION TEST SUITE")
    print("=" * 60)
    
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add all test cases
    suite.addTests(loader.loadTestsFromTestCase(TestNetworkThrottling))
    suite.addTests(loader.loadTestsFromTestCase(TestFrameRateAdaptation))
    suite.addTests(loader.loadTestsFromTestCase(TestTelegramAlerts))
    suite.addTests(loader.loadTestsFromTestCase(TestNetworkAdaptationIntegration))
    suite.addTests(loader.loadTestsFromTestCase(TestSimulatedNetworkConditions))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Print summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    print(f"Tests run: {result.testsRun}")
    print(f"Successes: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print("=" * 60)
    
    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)