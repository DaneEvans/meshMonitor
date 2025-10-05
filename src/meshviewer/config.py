"""
Configuration management for MeshViewer.
"""
import yaml
from typing import Dict, Any, Optional
from pathlib import Path


class ConfigManager:
    """Manages configuration loading and access."""
    
    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize the configuration manager.
        
        Args:
            config_path: Path to the configuration file. If None, uses default location.
        """
        if config_path is None:
            # Look for config.yaml in the project root
            project_root = Path(__file__).parent.parent.parent
            config_path = project_root / "config.yaml"
        
        self.config_path = Path(config_path)
        self._config: Dict[str, Any] = {}
        self.load_config()
    
    def load_config(self) -> None:
        """Load configuration from the YAML file."""
        try:
            if self.config_path.exists():
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    self._config = yaml.safe_load(f) or {}
            else:
                print(f"Warning: Configuration file not found at {self.config_path}")
                self._config = {}
        except Exception as e:
            print(f"Error loading configuration: {e}")
            self._config = {}
    
    def get(self, key_path: str, default: Any = None) -> Any:
        """
        Get a configuration value using dot notation.
        
        Args:
            key_path: Dot-separated path to the configuration value (e.g., 'theme.colors.primary')
            default: Default value if the key is not found
            
        Returns:
            The configuration value or default
        """
        keys = key_path.split('.')
        value = self._config
        
        try:
            for key in keys:
                value = value[key]
            return value
        except (KeyError, TypeError):
            return default
    
    def get_theme_colors(self) -> Dict[str, str]:
        """Get theme colors configuration."""
        return self.get('theme.colors', {})
    
    def get_ui_text(self) -> Dict[str, Any]:
        """Get UI text configuration."""
        return self.get('ui_text', {})
    
    def get_connection_defaults(self) -> Dict[str, Any]:
        """Get default connection settings."""
        return self.get('connection', {})
    
    
    def is_dark_mode(self) -> bool:
        """Check if dark mode is enabled."""
        return self.get('theme.dark_mode', False)
    
    
    def reload(self) -> None:
        """Reload configuration from file."""
        self.load_config()
