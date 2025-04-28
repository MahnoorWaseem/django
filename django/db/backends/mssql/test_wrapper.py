import os
import django
from django.conf import settings
from django.db.backends.mssql.base import db_config

# testcase of adapter 

# Complete Django settings configuration
if not settings.configured:
    settings.configure(
        # Required core settings
        TIME_ZONE='UTC',
        USE_TZ=True,
        SECRET_KEY='dummy-key-for-testing',
        
        # Database settings
        DATABASES={
            'default': {
                'ENGINE': 'django.db.backends.dummy',
                'NAME': '',
                'USER': '',
                'PASSWORD': '',
                'HOST': '',
                'PORT': '',
                'CONN_MAX_AGE': 0,
                'CONN_HEALTH_CHECKS': False,
                'OPTIONS': {},
                'TIME_ZONE': 'UTC',  # Explicitly set for database
            }
        },
        INSTALLED_APPS=[],
    )
    django.setup()

from django.db.backends.mssql.base import DatabaseWrapper
def test_wrapper():
    print("=== Testing MSSQL DatabaseWrapper ===")
    
    # Proper connection settings
    db_settings = db_config

    wrapper = DatabaseWrapper(db_settings)
    
    try:
        print("\nConnection parameters being used:")
        conn_params = wrapper.get_connection_params()
        safe_print = {k:v for k,v in conn_params.items() if k != 'pwd'}
        print(safe_print)
        
        print("\n1. Testing connection:")
        wrapper.ensure_connection()
        print("Connection made!")
        
            
    except Exception as e:
        print(f"\n✗ Error: {str(e)}")
        if 'IM002' in str(e):
            print("\nTROUBLESHOOTING: ODBC Driver not found.")
            print("Run this command to check installed drivers:")
            print("  odbcinst -q -d")
        elif '28000' in str(e):
            print("\nTROUBLESHOOTING: Authentication failed.")
            print("Verify your username/password or use Windows Authentication")
    finally:
        wrapper.close()
        print("\nConnection closed.")

if __name__ == '__main__':
    test_wrapper()

# command to execute this file 
# python django/db/backends/mssql/test_wrapper.py