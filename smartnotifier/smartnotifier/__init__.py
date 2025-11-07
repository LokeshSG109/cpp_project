"""
smartnotifier
-------------
A reusable library for managing and prioritizing notifications
for cloud-based service requests.
"""

__version__ = "0.1.0"
from .notifier import SmartNotifier
from .priority import calculate_priority
from .templates import get_message_template
