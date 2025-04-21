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
        
    def connect(self, receiver, sender=None, weak=True, dispatch_uid=None, priority=0):
        self._receiver_count += 1
        super().connect(receiver, sender, weak, dispatch_uid)
        # Store priority by modifying the receiver tuple
        if hasattr(self, 'receivers'):
            for i, (lookup_key, r, is_async) in enumerate(self.receivers):
                if lookup_key == (dispatch_uid or _make_id(receiver), _make_id(sender)):
                    self.receivers[i] = (lookup_key, r, is_async, priority)
                    break
    
    def send(self, sender=None, **named):
        self._send_count += 1
        
        # Sort receivers by priority
        if all(len(r) == 4 for r in self.receivers):
            self.receivers.sort(key=lambda x: x[3], reverse=True)
        
        # Handle None sender case
        if sender is None:
            responses = []
            for lookup_key, receiver, is_async, _ in self.receivers:
                if lookup_key[1] == NONE_ID:  # Receiver listens to None sender
                    try:
                        response = receiver(signal=self, sender=sender, **named)
                        responses.append((receiver, response))
                    except Exception as e:
                        logger.error(f"Receiver {receiver} failed: {e}")
        else:
            responses = super().send(sender, **named)
        
        # Maintain history
        self.history.append({
            'sender': str(sender),
            'responses': [(str(r), str(response)) for r, response in responses],
            'timestamp': time.time(),
            'kwargs': named
        })
        
        if len(self.history) > self.max_history:
            self.history = self.history[-self.max_history:]
            
        return responses
    
    @cached_property
    def statistics(self):
        return {
            'total_sends': self._send_count,
            'total_receivers': self._receiver_count,
            'current_receivers': len(self.receivers),
            'history_size': len(self.history)
        }

# 2. Create our signal instance
setting_changed = EventSignal(use_caching=True, max_history=5)
