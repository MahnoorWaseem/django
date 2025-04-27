# test_token_backend.py
from django.contrib.auth.backends import TokenHeaderBackend
from django.contrib.auth.backends import UserModel


# 4. Simple tests
if _name_ == "_main_":
    backend = TokenHeaderBackend()
    
   # Test 1: Valid active user
user1 = backend.authenticate(None, token="token123")
print(f"Test 1 - Valid active user ('token123'): {'SUCCESS (User exists and is active)' if user1 and user1.username == 'user1' else 'FAIL (User not found or inactive)'}")

# Test 2: Valid but inactive user
user2 = backend.authenticate(None, token="token456")
if user2:
    print("Test 2 - Inactive user ('token456'): FAIL (User authenticated, but should be rejected)")
else:
    # Check if the user exists but is inactive
    mock_user = UserModel.get(auth_token="token456")
    if mock_user:
        print("Test 2 - Inactive user ('token456'): SUCCESS (User exists but is inactive → correctly rejected)")
    else:
        print("Test 2 - Inactive user ('token456'): FAIL (User not found)")

# Test 3: Invalid token
user3 = backend.authenticate(None, token="bad_token")
if user3:
    print("Test 3 - Invalid token ('bad_token'): FAIL (User authenticated, but token is invalid)")
else:
    # Check if the token truly doesn't exist
    mock_user = UserModel.get(auth_token="bad_token")
    if mock_user:
        print("Test 3 - Invalid token ('bad_token'): FAIL (Token actually exists)")
    else:
        print("Test 3 - Invalid token ('bad_token'): SUCCESS (Token does not exist → correctly rejected)")


# python django/contrib/auth/test.py