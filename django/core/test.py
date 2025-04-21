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
   

if __name__ == "_main_":
    main()