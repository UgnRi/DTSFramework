#ssh_client.py
import asyncio
import asyncssh
import json
from ..utils.logger import setup_logger
logger = setup_logger()

class SSHClient:
    def __init__(self, config):
        # Ensure config is a dictionary and extract nested configurations
        self.full_config = config if isinstance(config, dict) else {}
        
        # Try multiple paths to find IP
        self.ip = (
            self.full_config.get('ip') or 
            self.full_config.get('host') or 
            self.full_config.get('device', {}).get('ip') or 
            self.full_config.get('device', {}).get('host')
        )
        
        # Try to get SSH configuration
        ssh_config = self.full_config.get('ssh', {}) or self.full_config.get('device', {}).get('ssh', {})
        
        # Extract connection details
        self.port = ssh_config.get('port', 22)
        self.username = ssh_config.get('username')
        self.password = ssh_config.get('password')
        
        self.conn = None

    async def connect(self):
        try:
            # Validate required connection parameters
            if not self.ip:
                raise ValueError("No IP address found. Please check your configuration.")
            
            if not self.username:
                raise ValueError("SSH username is required")
            
            if not self.password:
                raise ValueError("SSH password is required")

            # Establish connection
            self.conn = await asyncssh.connect(
                self.ip,
                port=self.port,
                username=self.username,
                password=self.password,
                known_hosts=None
            )
            return self.conn
        
        except Exception as e:
            # Log the configuration used (without password)
            connection_info = {
                'ip': self.ip,
                'port': self.port,
                'username': self.username
            }
            raise

    async def execute_command(self, command):
        try:
            if not self.conn:
                raise RuntimeError("SSH connection not established. Call connect() first.")
            
            result = await self.conn.run(command)
            return result.stdout.strip()  # Strip whitespace
        except Exception as e:
            raise

    async def close(self):
        """Close the SSH connection"""
        try:
            if self.conn:
                self.conn.close()
        except Exception as e:
            logger.error(f"Error closing SSH connection: {str(e)}")