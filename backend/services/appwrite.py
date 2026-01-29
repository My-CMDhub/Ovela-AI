from services.db.base import AppwriteBase
from services.db.bookings import BookingsMixin
from services.db.customers import CustomersMixin
from services.db.settings import SettingsMixin
from services.db.leads import LeadsMixin
from services.db.conversations import ConversationsMixin
from services.db.notifications import NotificationsMixin
from services.db.transcripts import TranscriptsMixin
import logging

logger = logging.getLogger(__name__)

class AppwriteService(
    AppwriteBase,
    BookingsMixin,
    CustomersMixin,
    SettingsMixin,
    LeadsMixin,
    ConversationsMixin,
    NotificationsMixin,
    TranscriptsMixin
):
    """
    Main Service Facade.
    Inherits functionality from modular Mixins.
    """
    pass

db_service = AppwriteService()
