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
    
    # Test invalid hashtags
    invalid_hashtags = [
        "",
        "   ",
        "#test test",  # contains space
        "test test",  # contains space
        "#test-test",  # contains hyphen
        "#test.test",  # contains period
        "#test@test",  # contains @
        "##test",      # multiple #
        "test#test",   # # in middle
        123,           # not a string
        ["#test"],     # not a string
        {"#test"},     # not a string
        "#",           # just the hash
    ]
    
    print("Testing invalid hashtags:")
    for tag in invalid_hashtags:
        try:
            form = HashtagTestForm(data={'hashtag': tag})
            if form.is_valid():
                print(f"✗ '{tag}' was incorrectly validated as '{form.cleaned_data['hashtag']}'")
            else:
                print(f"✓ '{tag}' correctly failed validation: {form.errors['hashtag'][0]}")
        except Exception as e:
            print(f"✓ '{tag}' correctly raised exception: {str(e)}")
    print()
    
    # Test widget attributes
    print("Testing widget attributes:")
    field = HashtagField()
    form = HashtagTestForm()
    widget = form.fields['hashtag'].widget
    attrs = widget.attrs
    print(f"maxlength: {attrs.get('maxlength', 'not found')} (should be 50)")
    print(f"pattern: {attrs.get('pattern', 'not found')}")
    print(f"placeholder: {attrs.get('placeholder', 'not found')}")

if __name__ == "_main_":
    # Minimal Django setup for forms to work
    import os
    os.environ['DJANGO_SETTINGS_MODULE'] = 'django.conf.global_settings'
    import django
    django.setup()
    
    run_tests()