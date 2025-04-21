# Commands
# cd .\django\forms
# python test.py

import re
from django.core.exceptions import ValidationError
from django.forms import  Form
from django.forms.fields import HashtagField

# Test Form
class HashtagTestForm(Form):
    hashtag = HashtagField()

def run_tests():
    print("Running HashtagField tests...\n")
    
    # Test valid hashtags
    valid_hashtags = [
        "#test",
        "test",  # should be converted to #test
        "#TEST",
        "#test123",
        "#test_123",
        "#123",
        "#_test",
    ]
    
    print("Testing valid hashtags:")
    for tag in valid_hashtags:
        form = HashtagTestForm(data={'hashtag': tag})
        if form.is_valid():
            print(f"✓ '{tag}' → '{form.cleaned_data['hashtag']}'")
        else:
            print(f"✗ '{tag}' failed validation: {form.errors}")
    print()
    
    

if __name__ == "_main_":
    # Minimal Django setup for forms to work
    import os
    os.environ['DJANGO_SETTINGS_MODULE'] = 'django.conf.global_settings'
    import django
    django.setup()
    
    run_tests()