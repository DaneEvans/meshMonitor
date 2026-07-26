"""
User management and session handling for multi-user support.
"""
import json
import hashlib
from pathlib import Path
from typing import Dict, Any, Optional, Tuple


class UserManager:
    """Manages user authentication, credentials, and per-user state persistence."""
    
    def __init__(self, users_config_path: Optional[Path] = None):
        """
        Initialize the user manager.
        
        Args:
            users_config_path: Path to the users configuration file.
                If None, uses default location (project_root/users.json).
        """
        if users_config_path is None:
            project_root = Path(__file__).resolve().parents[2]
            users_config_path = project_root / "users.json"
        
        self.users_config_path = Path(users_config_path)
        self.users_data: Dict[str, Any] = {}
        self.current_user: Optional[str] = None
        
        self._load_users()
        self._ensure_default_user()
    
    def _load_users(self) -> None:
        """Load user data from the configuration file."""
        if self.users_config_path.exists():
            try:
                with open(self.users_config_path, 'r', encoding='utf-8') as f:
                    self.users_data = json.load(f)
                print(f"Loaded {len(self.users_data)} users from {self.users_config_path}")
            except Exception as e:
                print(f"Error loading users config: {e}")
                self.users_data = {}
        else:
            print(f"Users config file not found at {self.users_config_path}")
            self.users_data = {}
    
    def _save_users(self) -> None:
        """Save user data to the configuration file."""
        try:
            self.users_config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.users_config_path, 'w', encoding='utf-8') as f:
                json.dump(self.users_data, f, indent=2)
            print(f"Saved users config to {self.users_config_path}")
        except Exception as e:
            print(f"Error saving users config: {e}")
    
    def _ensure_default_user(self) -> None:
        """Ensure there's at least one default user for initial setup."""
        if not self.users_data:
            # Create a default admin user with password "admin"
            self.add_user("admin", "admin", is_admin=True)
            print("Created default admin user (username: admin, password: admin)")
    
    @staticmethod
    def _hash_password(password: str) -> str:
        """Hash a password using SHA256."""
        return hashlib.sha256(password.encode()).hexdigest()
    
    def add_user(self, username: str, password: str, is_admin: bool = False) -> bool:
        """
        Add a new user to the system.
        
        Args:
            username: The username
            password: The plaintext password
            is_admin: Whether this user is an admin
            
        Returns:
            True if the user was added successfully, False if the username already exists
        """
        if username in self.users_data:
            return False
        
        self.users_data[username] = {
            "password_hash": self._hash_password(password),
            "is_admin": is_admin,
            "created_at": str(Path.cwd()),  # Simple timestamp reference
        }
        self._save_users()
        return True
    
    def authenticate(self, username: str, password: str) -> bool:
        """
        Authenticate a user with their password.
        
        Args:
            username: The username
            password: The plaintext password
            
        Returns:
            True if authentication successful, False otherwise
        """
        if username not in self.users_data:
            return False
        
        user_data = self.users_data[username]
        password_hash = self._hash_password(password)
        
        if user_data["password_hash"] == password_hash:
            self.current_user = username
            return True
        
        return False
    
    def get_current_user(self) -> Optional[str]:
        """Get the currently logged-in user."""
        return self.current_user
    
    def logout(self) -> None:
        """Log out the current user."""
        self.current_user = None
    
    def is_admin(self, username: Optional[str] = None) -> bool:
        """
        Check if a user is an admin.
        
        Args:
            username: The username to check. If None, checks current user.
            
        Returns:
            True if the user is an admin, False otherwise
        """
        if username is None:
            username = self.current_user
        
        if username is None or username not in self.users_data:
            return False
        
        return self.users_data[username].get("is_admin", False)
    
    def get_all_users(self) -> list:
        """Get a list of all usernames."""
        return list(self.users_data.keys())
    
    def change_password(self, username: str, old_password: str, new_password: str) -> bool:
        """
        Change a user's password.
        
        Args:
            username: The username
            old_password: The current password
            new_password: The new password
            
        Returns:
            True if password changed successfully, False otherwise
        """
        if not self.authenticate(username, old_password):
            return False
        
        self.users_data[username]["password_hash"] = self._hash_password(new_password)
        self._save_users()
        return True
    
    def delete_user(self, username: str) -> bool:
        """
        Delete a user from the system.
        
        Args:
            username: The username to delete
            
        Returns:
            True if user was deleted, False if user doesn't exist
        """
        if username not in self.users_data:
            return False
        
        del self.users_data[username]
        self._save_users()
        
        # Log out if this is the current user
        if self.current_user == username:
            self.current_user = None
        
        return True
