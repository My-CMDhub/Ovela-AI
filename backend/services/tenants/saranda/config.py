"""
Saranda Pizza Shop Configuration
=================================
Environment-based configuration for Square API and tenant settings.
"""

import os
from dataclasses import dataclass
from typing import Optional
import logging

# Load .env file automatically when this module is imported
from dotenv import load_dotenv
load_dotenv()

logger = logging.getLogger(__name__)


@dataclass
class SarandaConfig:
    """
    Configuration for Saranda Pizza Shop integration.
    
    All values are read from environment variables with sensible defaults
    for development/sandbox mode.
    """
    # Square API
    square_access_token: str
    square_environment: str  # "sandbox" or "production"
    square_location_id: Optional[str]  # Auto-discovered if not set
    square_webhook_signature_key: Optional[str]
    
    # Business Info
    business_name: str = "Saranda Cafe & Pizzeria"
    business_address: str = "2/8 Mullingar Way, Landsdale WA 6065"
    business_phone: str = ""  # TODO: Get from client
    
    # HITL Settings
    order_ttl_minutes: int = 5  # How long before an unapproved order expires
    poll_interval_seconds: int = 120  # Fallback polling interval (2 mins)
    
    # SMS Notifications
    enable_sms_confirmation: bool = True
    sms_confirmation_template: str = (
        "Hi {name}! Your order is confirmed. "
        "Pickup in ~{pickup_time} at Saranda Pizza. See you soon! 🍕"
    )
    sms_rejection_template: str = (
        "Hi {name}, sorry but we can't fulfill your order right now. "
        "Please call us directly at {phone}. Apologies! - Saranda Team"
    )
    
    @classmethod
    def from_env(cls) -> "SarandaConfig":
        """Load configuration from environment variables."""
        access_token = os.getenv("SQUARE_ACCESS_TOKEN", "")
        environment = os.getenv("SQUARE_ENVIRONMENT", "sandbox")
        
        if not access_token:
            logger.warning(
                "SQUARE_ACCESS_TOKEN not set - Square integration will not work!"
            )
        
        return cls(
            square_access_token=access_token,
            square_environment=environment,
            square_location_id=os.getenv("SQUARE_LOCATION_ID"),
            square_webhook_signature_key=os.getenv("SQUARE_WEBHOOK_SIGNATURE_KEY"),
        )
    
    @property
    def is_sandbox(self) -> bool:
        """Check if running in sandbox mode."""
        return self.square_environment.lower() == "sandbox"
    
    @property
    def square_base_url(self) -> str:
        """Get the appropriate Square API base URL."""
        if self.is_sandbox:
            return "https://connect.squareupsandbox.com"
        return "https://connect.squareup.com"


# Global config instance (lazy-loaded)
_config: Optional[SarandaConfig] = None


def get_config() -> SarandaConfig:
    """Get the Saranda configuration (singleton)."""
    global _config
    if _config is None:
        _config = SarandaConfig.from_env()
    return _config
