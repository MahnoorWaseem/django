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
    
  

if __name__ == "_main_":
    # Minimal Django setup for forms to work
    import os
    os.environ['DJANGO_SETTINGS_MODULE'] = 'django.conf.global_settings'
    import django
    django.setup()
    
    run_tests()