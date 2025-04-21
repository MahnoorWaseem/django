# ------------------------- PROPOSED EXTENSION FOR OBSERVER PATTERN ------------------------------------#

import time
import logging
from django.dispatch import Signal, receiver
from django.utils.functional import cached_property
import weakref

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(_name_)

# Needed for Django's signal internals
NONE_ID = -1

def _make_id(obj):
    if obj is None:
        return NONE_ID
    return id(obj)

# 1. Extended Signal class
class EventSignal(Signal):
     
    def _init_(self, use_caching=False, max_history=10):
        super()._init_(use_caching=use_caching)
        self.history = []
        self.max_history = max_history
        self._send_count = 0
        self._receiver_count = 0
        # Initialize cache properly for None sender
        if use_caching:
            self.sender_receivers_cache = {}
        
   