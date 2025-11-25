"""
Cloud Video Chunk Uploader
Handles authentication and upload of video chunks to cloud server
"""

import requests
import time
import logging
from pathlib import Path
from typing import Optional, Dict
from datetime import datetime
import threading


class CloudUploader:
    """Upload video chunks to cloud server with authentication"""
    
    def __init__(self, server_url: str, username: str, password: str):
        """
        Initialize cloud uploader
        
        Args:
            server_url: Cloud server URL (e.g., https://demo.example.com)
            username: Authentication username
            password: Authentication password
        """
        self.server_url = server_url.rstrip('/')
        self.username = username
        self.password = password
        self.access_token = None
        self.token_expiry = 0
        self.enabled = bool(server_url and username and password)
        self.logger = self._setup_logger()
        self.upload_queue = []
        self.lock = threading.Lock()
        
    def _setup_logger(self):
        """Setup logger"""
        logger = logging.getLogger('cloud_uploader')
        logger.setLevel(logging.INFO)
        
        # Console handler
        ch = logging.StreamHandler()
        ch.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(message)s'))
        logger.addHandler(ch)
        
        # File handler
        log_dir = Path('logs')
        log_dir.mkdir(exist_ok=True)
        fh = logging.FileHandler(log_dir / 'cloud_upload.log')
        fh.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
        logger.addHandler(fh)
        
        return logger
    
    def authenticate(self) -> bool:
        """
        Authenticate with cloud server and get access token
        
        Returns:
            bool: True if authentication successful
        """
        if not self.enabled:
            self.logger.warning("Cloud upload not configured (missing server_url, username, or password)")
            return False
        
        auth_url = f"{self.server_url}/auth/login"
        
        try:
            self.logger.info(f"Authenticating with {auth_url}...")
            
            response = requests.post(
                auth_url,
                json={
                    "username": self.username,
                    "password": self.password
                },
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                self.access_token = data.get('access_token')
                
                if self.access_token:
                    # Assume token valid for 1 hour (adjust based on server)
                    self.token_expiry = time.time() + 3600
                    self.logger.info("Authentication successful")
                    return True
                else:
                    self.logger.error("No access_token in response")
                    return False
            else:
                self.logger.error(f"Authentication failed: {response.status_code} - {response.text}")
                return False
                
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Authentication error: {e}")
            return False
        def authenticate(self) -> bool:
            """
            Authenticate with Samurai Inspector API and get access token
            Returns:
                bool: True if authentication successful
            """
            if not self.enabled:
                self.logger.warning("Cloud upload not configured (missing server_url, username, or password)")
                return False

            # Samurai Inspector API auth endpoint
            auth_url = f"{self.server_url}/auth/login"

            try:
                self.logger.info(f"Authenticating with {auth_url}...")
                response = requests.post(
                    auth_url,
                    data={
                        "username": self.username,
                        "password": self.password
                    },
                    headers={"Content-Type": "application/x-www-form-urlencoded", "accept": "application/json"},
                    timeout=10
                )
                if response.status_code == 200:
                    data = response.json()
                    self.access_token = data.get('access_token')
                    if self.access_token:
                        self.token_expiry = time.time() + 3600
                        self.logger.info("Authentication successful")
                        return True
                    else:
                        self.logger.error("No access_token in response")
                        return False
                else:
                    self.logger.error(f"Authentication failed: {response.status_code} - {response.text}")
                    return False
            except requests.exceptions.RequestException as e:
                self.logger.error(f"Authentication error: {e}")
                return False
    
    def _ensure_authenticated(self) -> bool:
        """Ensure we have a valid token, refresh if needed"""
        if not self.access_token or time.time() >= self.token_expiry - 60:
            # Token expired or about to expire (60s buffer)
            return self.authenticate()
        return True
    
    def upload_chunk(self, chunk_path: Path, stream_id: str, ts_start: int, ts_end: int) -> bool:
        """
        Upload a video chunk to cloud server
        
        Args:
            chunk_path: Path to video chunk file
            stream_id: Stream identifier (camera name)
            ts_start: Start timestamp (Unix epoch)
            ts_end: End timestamp (Unix epoch)
            
        Returns:
            bool: True if upload successful
        """
        if not self.enabled:
            self.logger.debug("Cloud upload disabled")
            return False
        
        if not chunk_path.exists():
            self.logger.error(f"Chunk file not found: {chunk_path}")
            return False
        
        # Ensure authenticated
        if not self._ensure_authenticated():
            self.logger.error("Failed to authenticate before upload")
            return False
        
        upload_url = f"{self.server_url}/streams/upload-chunk"
        
        try:
            self.logger.info(f"Uploading {chunk_path.name} (stream={stream_id}, duration={ts_end-ts_start}s)")
            
            # Prepare multipart form data
            files = {
                'file': (chunk_path.name, open(chunk_path, 'rb'), 'video/mp4')
            }
            
            data = {
                'stream_id': stream_id,
                'ts_start': str(ts_start),
                'ts_end': str(ts_end)
            }
            
            headers = {
                'Authorization': f'Bearer {self.access_token}'
            }
            
            response = requests.post(
                upload_url,
                headers=headers,
                data=data,
                files=files,
                timeout=30
            )
            
            files['file'][1].close()  # Close file handle
            
            if response.status_code == 200 or response.status_code == 201:
                self.logger.info(f"Upload successful: {chunk_path.name}")
                return True
            else:
                self.logger.error(f"Upload failed: {response.status_code} - {response.text}")
                return False
                
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Upload error: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error during upload: {e}")
            return False
        def upload_chunk(self, chunk_path: Path, stream_id: str, ts_start: int, ts_end: int) -> bool:
            """
            Upload a video chunk to Samurai Inspector API
            Args:
                chunk_path: Path to video chunk file
                stream_id: Stream identifier (camera name)
                ts_start: Start timestamp (Unix epoch)
                ts_end: End timestamp (Unix epoch)
            Returns:
                bool: True if upload successful
            """
            if not self.enabled:
                self.logger.debug("Cloud upload disabled")
                return False
            if not chunk_path.exists():
                self.logger.error(f"Chunk file not found: {chunk_path}")
                return False
            if not self._ensure_authenticated():
                self.logger.error("Failed to authenticate before upload")
                return False
            # Samurai Inspector API upload endpoint
            upload_url = f"{self.server_url}/streams/upload-chunk"
            try:
                self.logger.info(f"Uploading {chunk_path.name} (stream={stream_id}, duration={ts_end-ts_start}s)")
                files = {
                    'file': (chunk_path.name, open(chunk_path, 'rb'), 'video/mp4')
                }
                data = {
                    'stream_id': stream_id,
                    'ts_start': str(ts_start),
                    'ts_end': str(ts_end)
                }
                headers = {
                    'Authorization': f'Bearer {self.access_token}'
                }
                response = requests.post(
                    upload_url,
                    headers=headers,
                    data=data,
                    files=files,
                    timeout=30
                )
                files['file'][1].close()
                if response.status_code == 200 or response.status_code == 201:
                    self.logger.info(f"Upload successful: {chunk_path.name}")
                    return True
                else:
                    self.logger.error(f"Upload failed: {response.status_code} - {response.text}")
                    return False
            except requests.exceptions.RequestException as e:
                self.logger.error(f"Upload error: {e}")
                return False
            except Exception as e:
                self.logger.error(f"Unexpected error during upload: {e}")
                return False
    
    def queue_chunk(self, chunk_path: Path, stream_id: str, ts_start: int, ts_end: int):
        """Add chunk to upload queue"""
        with self.lock:
            self.upload_queue.append({
                'chunk_path': chunk_path,
                'stream_id': stream_id,
                'ts_start': ts_start,
                'ts_end': ts_end,
                'queued_at': time.time()
            })
            self.logger.debug(f"Queued {chunk_path.name} for upload (queue size: {len(self.upload_queue)})")
    
    def process_queue(self):
        """Process upload queue (call this periodically or in a thread)"""
        if not self.enabled:
            self.logger.debug("Upload queue processing skipped - uploader disabled")
            return
        
        with self.lock:
            if not self.upload_queue:
                return
            
            # Process first item
            item = self.upload_queue.pop(0)
            self.logger.info(f"Processing queued upload: {item['chunk_path'].name}")
        
        # Upload (outside lock to avoid blocking)
        success = self.upload_chunk(
            item['chunk_path'],
            item['stream_id'],
            item['ts_start'],
            item['ts_end']
        )
        
        if success:
            # Optionally delete local file after successful upload
            # item['chunk_path'].unlink()
            pass
        else:
            # Re-queue if failed (with limit to avoid infinite retries)
            if time.time() - item['queued_at'] < 3600:  # Retry for 1 hour
                with self.lock:
                    self.upload_queue.append(item)
                    self.logger.warning(f"Re-queued {item['chunk_path'].name} after failed upload")
    
    def get_queue_status(self) -> Dict:
        """Get upload queue status"""
        with self.lock:
            return {
                'queue_size': len(self.upload_queue),
                'enabled': self.enabled,
                'authenticated': self.access_token is not None
            }


# Global instance (initialized in app.py)
cloud_uploader = None


def init_cloud_uploader(config: dict) -> CloudUploader:
    """Initialize global cloud uploader from config"""
    global cloud_uploader
    
    server_url = config.get('cloud_upload_url', '')
    username = config.get('cloud_username', '')
    password = config.get('cloud_password', '')
    
    cloud_uploader = CloudUploader(server_url, username, password)
    
    if cloud_uploader.enabled:
        # Authenticate on startup
        cloud_uploader.authenticate()
    
    return cloud_uploader
