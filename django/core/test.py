import logging
from django.core.eventSignal import SettingsNotifier, setting_changed  # Updated import

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(_name_)


def main():
    print("=== Testing EventSignal ===")
    
    # Test 1: Basic signal send
    print("\nTest 1: Changing time_zone")
    SettingsNotifier.notify_change(  # Updated call
        setting_name="time_zone",
        old_value="UTC",
        new_value="EST",
        changed_by="user1"
    )
    
    # Test 2: Changing protected setting
    print("\nTest 2: Changing admin_password (should show warning)")
    try:
        SettingsNotifier.notify_change(  # Updated call
            setting_name="admin_password",
            old_value="old123",
            new_value="new456",
            changed_by="hacker"
        )
    except ValueError as e:
        logger.error(f"Expected error caught: {e}")
    
    # Test 3: Multiple changes to show history
    print("\nTest 3: Making multiple changes")
    for i in range(3):
        SettingsNotifier.notify_change(  # Updated call
            setting_name=f"setting_{i}",
            old_value=f"old_{i}",
            new_value=f"new_{i}",
            changed_by=f"user_{i}"
        )
    
    # Show statistics and history
    print("\nSignal Statistics:")
    for k, v in setting_changed.statistics.items():
        print(f"{k}: {v}")
    
    print("\nSignal History (last 5):")
    for i, event in enumerate(setting_changed.history, 1):
        print(f"\nEvent {i}:")
        print(f"  Sender: {event['sender']}")
        print(f"  Timestamp: {event['timestamp']}")
        print("  Responses:")
        for receiver, response in event['responses']:
            print(f"    - {receiver}: {response}")

if __name__ == "_main_":
    main()