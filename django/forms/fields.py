import copy
import datetime
import json
import math
import operator
import os
import re
import uuid
from decimal import Decimal, DecimalException
from io import BytesIO
from urllib.parse import urlsplit, urlunsplit
from PIL import Image

from django.core import validators
from django.core.exceptions import ValidationError
from django.forms.boundfield import BoundField
from django.forms.utils import from_current_timezone, to_current_timezone
from django.forms.widgets import (
    FILE_INPUT_CONTRADICTION,
    CheckboxInput,
    ClearableFileInput,
    DateInput,
    DateTimeInput,
    EmailInput,
    FileInput,
    HiddenInput,
    MultipleHiddenInput,
    NullBooleanSelect,
    NumberInput,
    Select,
    SelectMultiple,
    SplitDateTimeWidget,
    SplitHiddenDateTimeWidget,
    Textarea,
    TextInput,
    TimeInput,
    URLInput,
)
from django.utils import formats
from django.utils.choices import normalize_choices
from django.utils.dateparse import parse_datetime, parse_duration
from django.utils.duration import duration_string
from django.utils.ipv6 import MAX_IPV6_ADDRESS_LENGTH, clean_ipv6_address
from django.utils.regex_helper import _lazy_re_compile
from django.utils.translation import gettext_lazy as _
from django.utils.translation import ngettext_lazy


class CharField:
    widget = TextInput
    hidden_widget = HiddenInput
    default_validators = []
    default_error_messages = {
        "required": _("This field is required."),
    }
    empty_values = list(validators.EMPTY_VALUES)

    def __init__(self, *, max_length=None, min_length=None, strip=True, empty_value="", **kwargs):
        self.max_length = max_length
        self.min_length = min_length
        self.strip = strip
        self.empty_value = empty_value
        
        self.required = kwargs.get('required', True)
        self.label = kwargs.get('label')
        self.initial = kwargs.get('initial')
        self.help_text = kwargs.get('help_text', '')
        self.disabled = kwargs.get('disabled', False)
        self.label_suffix = kwargs.get('label_suffix')
        self.localize = kwargs.get('localize', False)
        self.template_name = kwargs.get('template_name')
        self.bound_field_class = kwargs.get('bound_field_class')
        self.show_hidden_initial = kwargs.get('show_hidden_initial', False)
        
        widget = kwargs.get('widget', self.widget)
        if isinstance(widget, type):
            widget = widget()
        self.widget = copy.deepcopy(widget)
        self.widget.is_required = self.required
        if self.localize:
            self.widget.is_localized = True
            
        self.error_messages = {}
        for cls in reversed(self.__class__.__mro__):
            self.error_messages.update(getattr(cls, 'default_error_messages', {}))
        self.error_messages.update(kwargs.get('error_messages', {}))
        
        self.validators = list(self.default_validators)
        if min_length is not None:
            self.validators.append(validators.MinLengthValidator(int(min_length)))
        if max_length is not None:
            self.validators.append(validators.MaxLengthValidator(int(max_length)))
        self.validators.append(validators.ProhibitNullCharactersValidator())
        self.validators.extend(kwargs.get('validators', []))

    def to_python(self, value):
        if value not in self.empty_values:
            value = str(value)
            if self.strip:
                value = value.strip()
        if value in self.empty_values:
            return self.empty_value
        return value

    def validate(self, value):
        if value in self.empty_values and self.required:
            raise ValidationError(self.error_messages["required"], code="required")

    def run_validators(self, value):
        if value in self.empty_values:
            return
        errors = []
        for v in self.validators:
            try:
                v(value)
            except ValidationError as e:
                if hasattr(e, "code") and e.code in self.error_messages:
                    e.message = self.error_messages[e.code]
                errors.extend(e.error_list)
        if errors:
            raise ValidationError(errors)

    def clean(self, value):
        value = self.to_python(value)
        self.validate(value)
        self.run_validators(value)
        return value

    def widget_attrs(self, widget):
        attrs = {}
        if self.max_length is not None and not widget.is_hidden:
            attrs["maxlength"] = str(self.max_length)
        if self.min_length is not None and not widget.is_hidden:
            attrs["minlength"] = str(self.min_length)
        return attrs

    def bound_data(self, data, initial):
        if self.disabled:
            return initial
        return data

    def has_changed(self, initial, data):
        if self.disabled:
            return False
        try:
            data = self.to_python(data)
        except ValidationError:
            return True
        initial_value = initial if initial is not None else ""
        data_value = data if data is not None else ""
        return initial_value != data_value

    def get_bound_field(self, form, field_name):
        bound_field_class = self.bound_field_class or form.bound_field_class or BoundField
        return bound_field_class(form, self, field_name)

    def __deepcopy__(self, memo):
        result = copy.copy(self)
        memo[id(self)] = result
        result.widget = copy.deepcopy(self.widget, memo)
        result.error_messages = self.error_messages.copy()
        result.validators = self.validators[:]
        return result

    def _clean_bound_field(self, bf):
        value = bf.initial if self.disabled else bf.data
        return self.clean(value)

class IntegerField:
    widget = NumberInput
    default_error_messages = {
        "invalid": _("Enter a whole number."),
        "required": _("This field is required."),
    }
    re_decimal = _lazy_re_compile(r"\.0*\s*$")
    empty_values = list(validators.EMPTY_VALUES)

    def __init__(self, *, max_value=None, min_value=None, step_size=None, **kwargs):
        self.max_value = max_value
        self.min_value = min_value
        self.step_size = step_size
        
        self.required = kwargs.get('required', True)
        self.label = kwargs.get('label')
        self.initial = kwargs.get('initial')
        self.help_text = kwargs.get('help_text', '')
        self.disabled = kwargs.get('disabled', False)
        self.label_suffix = kwargs.get('label_suffix')
        self.localize = kwargs.get('localize', False)
        self.template_name = kwargs.get('template_name')
        self.bound_field_class = kwargs.get('bound_field_class')
        self.show_hidden_initial = kwargs.get('show_hidden_initial', False)
        
        if kwargs.get('localize') and self.widget == NumberInput:
            kwargs.setdefault('widget', super().widget)
            
        widget = kwargs.get('widget', self.widget)
        if isinstance(widget, type):
            widget = widget()
        self.widget = copy.deepcopy(widget)
        self.widget.is_required = self.required
        if self.localize:
            self.widget.is_localized = True
            
        self.error_messages = {}
        for cls in reversed(self.__class__.__mro__):
            self.error_messages.update(getattr(cls, 'default_error_messages', {}))
        self.error_messages.update(kwargs.get('error_messages', {}))
        
        self.validators = []
        if max_value is not None:
            self.validators.append(validators.MaxValueValidator(max_value))
        if min_value is not None:
            self.validators.append(validators.MinValueValidator(min_value))
        if step_size is not None:
            self.validators.append(validators.StepValueValidator(step_size, offset=min_value))
        self.validators.extend(kwargs.get('validators', []))

    def to_python(self, value):
        if value in self.empty_values:
            return None
        if self.localize:
            value = formats.sanitize_separators(value)
        try:
            value = int(self.re_decimal.sub("", str(value)))
        except (ValueError, TypeError):
            raise ValidationError(self.error_messages["invalid"], code="invalid")
        return value

    def validate(self, value):
        if value in self.empty_values and self.required:
            raise ValidationError(self.error_messages["required"], code="required")

    def run_validators(self, value):
        if value in self.empty_values:
            return
        errors = []
        for v in self.validators:
            try:
                v(value)
            except ValidationError as e:
                if hasattr(e, "code") and e.code in self.error_messages:
                    e.message = self.error_messages[e.code]
                errors.extend(e.error_list)
        if errors:
            raise ValidationError(errors)

    def clean(self, value):
        value = self.to_python(value)
        self.validate(value)
        self.run_validators(value)
        return value

    def widget_attrs(self, widget):
        attrs = {}
        if isinstance(widget, NumberInput):
            if self.min_value is not None:
                attrs["min"] = self.min_value
            if self.max_value is not None:
                attrs["max"] = self.max_value
            if self.step_size is not None:
                attrs["step"] = self.step_size
        return attrs

    def bound_data(self, data, initial):
        if self.disabled:
            return initial
        return data

    def has_changed(self, initial, data):
        if self.disabled:
            return False
        try:
            data = self.to_python(data)
            if hasattr(self, "_coerce"):
                return self._coerce(data) != self._coerce(initial)
        except ValidationError:
            return True
        initial_value = initial if initial is not None else ""
        data_value = data if data is not None else ""
        return initial_value != data_value

    def get_bound_field(self, form, field_name):
        bound_field_class = self.bound_field_class or form.bound_field_class or BoundField
        return bound_field_class(form, self, field_name)

    def __deepcopy__(self, memo):
        result = copy.copy(self)
        memo[id(self)] = result
        result.widget = copy.deepcopy(self.widget, memo)
        result.error_messages = self.error_messages.copy()
        result.validators = self.validators[:]
        return result

    def _clean_bound_field(self, bf):
        value = bf.initial if self.disabled else bf.data
        return self.clean(value)

class FloatField(IntegerField):
    default_error_messages = {
        "invalid": _("Enter a number."),
    }

    def to_python(self, value):
        if value in self.empty_values:
            return None
        if self.localize:
            value = formats.sanitize_separators(value)
        try:
            value = float(value)
        except (ValueError, TypeError):
            raise ValidationError(self.error_messages["invalid"], code="invalid")
        return value

    def validate(self, value):
        super().validate(value)
        if value in self.empty_values:
            return
        if not math.isfinite(value):
            raise ValidationError(self.error_messages["invalid"], code="invalid")

    def widget_attrs(self, widget):
        attrs = super().widget_attrs(widget)
        if isinstance(widget, NumberInput) and "step" not in widget.attrs:
            if self.step_size is not None:
                step = str(self.step_size)
            else:
                step = "any"
            attrs.setdefault("step", step)
        return attrs

class DecimalField(IntegerField):
    default_error_messages = {
        "invalid": _("Enter a number."),
    }

    def __init__(self, *, max_value=None, min_value=None, max_digits=None, decimal_places=None, **kwargs):
        self.max_digits = max_digits
        self.decimal_places = decimal_places
        super().__init__(max_value=max_value, min_value=min_value, **kwargs)
        self.validators.append(validators.DecimalValidator(max_digits, decimal_places))

    def to_python(self, value):
        if value in self.empty_values:
            return None
        if self.localize:
            value = formats.sanitize_separators(value)
        try:
            value = Decimal(str(value))
        except DecimalException:
            raise ValidationError(self.error_messages["invalid"], code="invalid")
        return value

    def validate(self, value):
        super().validate(value)
        if value in self.empty_values:
            return
        if not value.is_finite():
            raise ValidationError(
                self.error_messages["invalid"],
                code="invalid",
                params={"value": value},
            )

    def widget_attrs(self, widget):
        attrs = super().widget_attrs(widget)
        if isinstance(widget, NumberInput) and "step" not in widget.attrs:
            if self.decimal_places is not None:
                step = str(Decimal(1).scaleb(-self.decimal_places)).lower()
            else:
                step = "any"
            attrs.setdefault("step", step)
        return attrs
