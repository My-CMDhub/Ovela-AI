"""
Saranda Pizza Shop Tenant Module
================================
Square-centric HITL integration for Saranda Cafe & Pizzeria.

Location: 2/8 Mullingar Way, Landsdale WA 6065 (Perth)
"""

from .config import SarandaConfig, get_config
from .square_client import SquareClient, SquareOrderItem, SquareOrder
from .square_flows import (
    SquareApprovalTracker,
    SquareOrderRequest,
    ApprovalState,
    saranda_approval_tracker,
    generate_request_id,
)
from .notifications import send_customer_notification, send_order_created_acknowledgment

__all__ = [
    # Config
    "SarandaConfig",
    "get_config",
    # Square Client
    "SquareClient",
    "SquareOrderItem",
    "SquareOrder",
    # Flow Management
    "SquareApprovalTracker",
    "SquareOrderRequest",
    "ApprovalState",
    "saranda_approval_tracker",
    "generate_request_id",
    # Notifications
    "send_customer_notification",
    "send_order_created_acknowledgment",
]

