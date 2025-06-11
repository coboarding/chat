"""
gdpr_compliance.py

Implements GDPR compliance functionality for handling user data with appropriate
time-to-live (TTL) mechanisms and data protection features.
"""

import json
import time
from datetime import datetime, timedelta
from pathlib import Path
import logging
from typing import Dict, Any, Optional

class GDPRManager:
    """Manages GDPR compliance for user data with TTL functionality."""
    
    def __init__(self, storage_dir: str = "temp_uploads"):
        """Initialize the GDPR Manager.
        
        Args:
            storage_dir: Directory to store temporary user data
        """
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(exist_ok=True)
        self.logger = logging.getLogger("gdpr_manager")
        
    def store_with_ttl(self, session_id: str, data: Dict[str, Any], ttl_hours: int = 24) -> bool:
        """Store user data with a time-to-live expiration.
        
        Args:
            session_id: Unique identifier for the user session
            data: User data to store
            ttl_hours: Number of hours before data should be deleted
            
        Returns:
            bool: True if data was stored successfully
        """
        try:
            expiry_time = datetime.now() + timedelta(hours=ttl_hours)
            
            # Create storage object with metadata
            storage_obj = {
                "data": data,
                "metadata": {
                    "created_at": datetime.now().isoformat(),
                    "expires_at": expiry_time.isoformat(),
                    "ttl_hours": ttl_hours
                }
            }
            
            # Store data in file
            file_path = self.storage_dir / f"{session_id}.json"
            with open(file_path, "w") as f:
                json.dump(storage_obj, f)
                
            self.logger.info(f"Stored data for session {session_id} with {ttl_hours}h TTL")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to store data: {str(e)}")
            return False
    
    def update_with_ttl(self, session_id: str, data: Dict[str, Any]) -> bool:
        """Update existing data while preserving TTL settings.
        
        Args:
            session_id: Unique identifier for the user session
            data: Updated user data
            
        Returns:
            bool: True if data was updated successfully
        """
        try:
            file_path = self.storage_dir / f"{session_id}.json"
            
            if not file_path.exists():
                self.logger.warning(f"Session {session_id} not found for update")
                return False
            
            # Read existing data to preserve metadata
            with open(file_path, "r") as f:
                storage_obj = json.load(f)
            
            # Update data while keeping metadata
            storage_obj["data"] = data
            
            # Write updated data
            with open(file_path, "w") as f:
                json.dump(storage_obj, f)
                
            self.logger.info(f"Updated data for session {session_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to update data: {str(e)}")
            return False
    
    def get_data(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve data if not expired.
        
        Args:
            session_id: Unique identifier for the user session
            
        Returns:
            Optional[Dict]: The stored data or None if expired/not found
        """
        try:
            file_path = self.storage_dir / f"{session_id}.json"
            
            if not file_path.exists():
                return None
            
            with open(file_path, "r") as f:
                storage_obj = json.load(f)
            
            # Check if data has expired
            expires_at = datetime.fromisoformat(storage_obj["metadata"]["expires_at"])
            if datetime.now() > expires_at:
                self.logger.info(f"Data for session {session_id} has expired")
                file_path.unlink(missing_ok=True)  # Delete expired data
                return None
                
            return storage_obj["data"]
            
        except Exception as e:
            self.logger.error(f"Failed to retrieve data: {str(e)}")
            return None
    
    def delete_data(self, session_id: str) -> bool:
        """Delete user data regardless of TTL.
        
        Args:
            session_id: Unique identifier for the user session
            
        Returns:
            bool: True if data was deleted successfully
        """
        try:
            file_path = self.storage_dir / f"{session_id}.json"
            
            if not file_path.exists():
                return False
                
            file_path.unlink()
            self.logger.info(f"Deleted data for session {session_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to delete data: {str(e)}")
            return False
    
    def cleanup_expired(self) -> int:
        """Clean up all expired data files.
        
        Returns:
            int: Number of expired files removed
        """
        try:
            count = 0
            for file_path in self.storage_dir.glob("*.json"):
                try:
                    with open(file_path, "r") as f:
                        storage_obj = json.load(f)
                    
                    expires_at = datetime.fromisoformat(storage_obj["metadata"]["expires_at"])
                    if datetime.now() > expires_at:
                        file_path.unlink()
                        count += 1
                except Exception:
                    # Skip files that can't be processed
                    continue
            
            self.logger.info(f"Cleaned up {count} expired data files")
            return count
            
        except Exception as e:
            self.logger.error(f"Failed during cleanup: {str(e)}")
            return 0

