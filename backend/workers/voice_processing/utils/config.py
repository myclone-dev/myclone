"""Configuration management for voice processing system."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict

import yaml
from loguru import logger


@dataclass
class ProfileConfig:
    """Configuration for a specific processing profile."""

    min_duration: int
    max_duration: int
    target_duration: int
    sample_rate: int
    bit_depth: int
    channels: int
    target_rms_min: float
    target_rms_max: float
    true_peak_max: float
    format: str
    bitrate: int
    min_snr: float
    max_silence_ratio: float


class Config:
    """Main configuration manager."""

    def __init__(self, config_path: str = None):
        """Initialize configuration.

        Args:
            config_path: Path to configuration file. If None, uses default.
        """
        if config_path is None:
            # Get path relative to this file
            base_dir = Path(__file__).parent.parent.parent
            config_path = base_dir / "config" / "settings.yaml"

        self.config_path = Path(config_path)
        self._config = self._load_config()

    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from YAML file."""
        try:
            with open(self.config_path, "r") as f:
                return yaml.safe_load(f)
        except FileNotFoundError:
            raise FileNotFoundError(f"Configuration file not found: {self.config_path}")
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML configuration: {e}")

    def get_profile(self, profile_name: str) -> ProfileConfig:
        """Get configuration for a specific profile.

        Args:
            profile_name: Name of the profile (e.g., 'elevenlabs', 'generic')

        Returns:
            ProfileConfig object with profile settings

        Raises:
            KeyError: If profile doesn't exist
        """
        if profile_name not in self._config["profiles"]:
            available = list(self._config["profiles"].keys())
            raise KeyError(f"Profile '{profile_name}' not found. Available: {available}")

        profile_data = self._config["profiles"][profile_name]
        return ProfileConfig(**profile_data)

    def get_processing_config(self) -> Dict[str, Any]:
        """Get general processing configuration."""
        return self._config.get("processing", {})

    def get_validation_config(self) -> Dict[str, Any]:
        """Get file validation configuration."""
        return self._config.get("validation", {})

    def get_youtube_config(self) -> Dict[str, Any]:
        """Get YouTube processing configuration."""
        return self._config.get("youtube", {})

    def get_output_dir(self, subdir: str = None) -> Path:
        """Get output directory path.

        Args:
            subdir: Subdirectory name (e.g., 'raw', 'segments')

        Returns:
            Path to output directory
        """
        # Use /app/uploads/output as the base directory
        output_dir = Path("/app/uploads/output")

        if subdir:
            output_dir = output_dir / subdir

        # Create directory if it doesn't exist with proper error handling
        try:
            output_dir.mkdir(parents=True, exist_ok=True)
        except PermissionError as e:
            logger.error(f"Permission denied creating output directory {output_dir}: {e}")
            # Fallback to a temp directory in the current working directory
            fallback_dir = Path.cwd() / "output"
            if subdir:
                fallback_dir = fallback_dir / subdir
            logger.warning(f"Falling back to {fallback_dir}")
            fallback_dir.mkdir(parents=True, exist_ok=True)
            return fallback_dir
        except Exception as e:
            logger.error(f"Failed to create output directory {output_dir}: {e}")
            raise

        return output_dir

    def get_temp_dir(self) -> Path:
        """Get temporary directory path."""
        # Use /app/uploads/temp for temporary files
        temp_dir = Path("/app/uploads/temp")
        try:
            temp_dir.mkdir(parents=True, exist_ok=True)
        except PermissionError as e:
            logger.error(f"Permission denied creating temp directory {temp_dir}: {e}")
            # Fallback to system temp directory
            import tempfile

            fallback_dir = Path(tempfile.gettempdir()) / "voice_processing"
            logger.warning(f"Falling back to {fallback_dir}")
            fallback_dir.mkdir(parents=True, exist_ok=True)
            return fallback_dir
        except Exception as e:
            logger.error(f"Failed to create temp directory {temp_dir}: {e}")
            raise
        return temp_dir


# Global configuration instance
config = Config()
