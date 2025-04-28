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

class DateTimeFormatsIterator:
    def __iter__(self):
        yield from formats.get_format("DATETIME_INPUT_FORMATS")
        yield from formats.get_format("DATE_INPUT_FORMATS")


class DateField:
    widget = DateInput
    input_formats = formats.get_format_lazy("DATE_INPUT_FORMATS")
    default_error_messages = {
        "invalid": _("Enter a valid date."),
        "required": _("This field is required."),
    }
    empty_values = list(validators.EMPTY_VALUES)

    def __init__(self, *, input_formats=None, **kwargs):
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
        
        if input_formats is not None:
            self.input_formats = input_formats
            
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
        
        self.validators = kwargs.get('validators', [])

    def to_python(self, value):
        if value in self.empty_values:
            return None
        if isinstance(value, datetime.datetime):
            return value.date()
        if isinstance(value, datetime.date):
            return value
            
        value = value.strip()
        for format in self.input_formats:
            try:
                return datetime.datetime.strptime(value, format).date()
            except (ValueError, TypeError):
                continue
        raise ValidationError(self.error_messages["invalid"], code="invalid")

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
        return {}

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

class TimeField:
    widget = TimeInput
    input_formats = formats.get_format_lazy("TIME_INPUT_FORMATS")
    default_error_messages = {
        "invalid": _("Enter a valid time."),
        "required": _("This field is required."),
    }
    empty_values = list(validators.EMPTY_VALUES)

    def __init__(self, *, input_formats=None, **kwargs):
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
        
        if input_formats is not None:
            self.input_formats = input_formats
            
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
        
        self.validators = kwargs.get('validators', [])

    def to_python(self, value):
        if value in self.empty_values:
            return None
        if isinstance(value, datetime.time):
            return value
            
        value = value.strip()
        for format in self.input_formats:
            try:
                return datetime.datetime.strptime(value, format).time()
            except (ValueError, TypeError):
                continue
        raise ValidationError(self.error_messages["invalid"], code="invalid")

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
        return {}

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

class DateTimeField:
    widget = DateTimeInput
    input_formats = DateTimeFormatsIterator()
    default_error_messages = {
        "invalid": _("Enter a valid date/time."),
        "required": _("This field is required."),
    }
    empty_values = list(validators.EMPTY_VALUES)

    def __init__(self, *, input_formats=None, **kwargs):
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
        
        if input_formats is not None:
            self.input_formats = input_formats
            
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
        
        self.validators = kwargs.get('validators', [])

    def prepare_value(self, value):
        if isinstance(value, datetime.datetime):
            value = to_current_timezone(value)
        return value

    def to_python(self, value):
        if value in self.empty_values:
            return None
        if isinstance(value, datetime.datetime):
            return from_current_timezone(value)
        if isinstance(value, datetime.date):
            result = datetime.datetime(value.year, value.month, value.day)
            return from_current_timezone(result)
        try:
            result = parse_datetime(value.strip())
        except ValueError:
            raise ValidationError(self.error_messages["invalid"], code="invalid")
        if not result:
            value = value.strip()
            for format in self.input_formats:
                try:
                    result = datetime.datetime.strptime(value, format)
                except (ValueError, TypeError):
                    continue
                else:
                    break
            else:
                raise ValidationError(self.error_messages["invalid"], code="invalid")
        return from_current_timezone(result)

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
        return {}

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

class DurationField:
    default_error_messages = {
        "invalid": _("Enter a valid duration."),
        "overflow": _("The number of days must be between {min_days} and {max_days}."),
        "required": _("This field is required."),
    }
    empty_values = list(validators.EMPTY_VALUES)

    def __init__(self, **kwargs):
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
        
        self.validators = kwargs.get('validators', [])

    def prepare_value(self, value):
        if isinstance(value, datetime.timedelta):
            return duration_string(value)
        return value

    def to_python(self, value):
        if value in self.empty_values:
            return None
        if isinstance(value, datetime.timedelta):
            return value
        try:
            value = parse_duration(str(value))
        except OverflowError:
            raise ValidationError(
                self.error_messages["overflow"].format(
                    min_days=datetime.timedelta.min.days,
                    max_days=datetime.timedelta.max.days,
                ),
                code="overflow",
            )
        if value is None:
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
        return {}

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

class FileField:
    widget = ClearableFileInput
    default_error_messages = {
        "invalid": _("No file was submitted. Check the encoding type on the form."),
        "missing": _("No file was submitted."),
        "empty": _("The submitted file is empty."),
        "max_length": ngettext_lazy(
            "Ensure this filename has at most %(max)d character (it has %(length)d).",
            "Ensure this filename has at most %(max)d characters (it has %(length)d).",
            "max",
        ),
        "contradiction": _("Please either submit a file or check the clear checkbox, not both."),
        "required": _("This field is required."),
    }
    empty_values = list(validators.EMPTY_VALUES)

    def __init__(self, *, max_length=None, allow_empty_file=False, **kwargs):
        self.max_length = max_length
        self.allow_empty_file = allow_empty_file
        
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
        
        self.validators = kwargs.get('validators', [])

    def to_python(self, data):
        if data in self.empty_values:
            return None
        try:
            file_name = data.name
            file_size = data.size
        except AttributeError:
            raise ValidationError(self.error_messages["invalid"], code="invalid")

        if self.max_length is not None and len(file_name) > self.max_length:
            params = {"max": self.max_length, "length": len(file_name)}
            raise ValidationError(
                self.error_messages["max_length"], code="max_length", params=params
            )
        if not file_name:
            raise ValidationError(self.error_messages["invalid"], code="invalid")
        if not self.allow_empty_file and not file_size:
            raise ValidationError(self.error_messages["empty"], code="empty")

        return data

    def clean(self, data, initial=None):
        if data is FILE_INPUT_CONTRADICTION:
            raise ValidationError(
                self.error_messages["contradiction"], code="contradiction"
            )
        if data is False:
            if not self.required:
                return False
            data = None
        if not data and initial:
            return initial
        
        data = self.to_python(data)
        self.validate(data)
        self.run_validators(data)
        return data

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

    def bound_data(self, _, initial):
        return initial

    def has_changed(self, initial, data):
        return not self.disabled and data is not None

    def widget_attrs(self, widget):
        return {}

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
        return self.clean(value, bf.initial)

class ImageField(FileField):
    default_validators = [validators.validate_image_file_extension]
    default_error_messages = {
        "invalid_image": _(
            "Upload a valid image. The file you uploaded was either not an "
            "image or a corrupted image."
        ),
    }

    def to_python(self, data):
        f = super().to_python(data)
        if f is None:
            return None

        if hasattr(data, "temporary_file_path"):
            file = data.temporary_file_path()
        else:
            if hasattr(data, "read"):
                file = BytesIO(data.read())
            else:
                file = BytesIO(data["content"])

        try:
            image = Image.open(file)
            image.verify()
            f.image = image
            f.content_type = Image.MIME.get(image.format)
        except Exception as exc:
            raise ValidationError(
                self.error_messages["invalid_image"],
                code="invalid_image",
            ) from exc
        if hasattr(f, "seek") and callable(f.seek):
            f.seek(0)
        return f

    def widget_attrs(self, widget):
        attrs = super().widget_attrs(widget)
        if isinstance(widget, FileInput) and "accept" not in widget.attrs:
            attrs.setdefault("accept", "image/*")
        return attrs


class EmailField(CharField):
    widget = EmailInput
    default_validators = [validators.validate_email]

    def __init__(self, **kwargs):
        kwargs.setdefault("max_length", 320)
        super().__init__(strip=True, **kwargs)

class URLField(CharField):
    widget = URLInput
    default_error_messages = {
        "invalid": _("Enter a valid URL."),
    }
    default_validators = [validators.URLValidator()]

    def __init__(self, *, assume_scheme=None, **kwargs):
        self.assume_scheme = assume_scheme or "https"
        super().__init__(strip=True, **kwargs)

    def to_python(self, value):
        def split_url(url):
            try:
                return list(urlsplit(url))
            except ValueError:
                raise ValidationError(self.error_messages["invalid"], code="invalid")

        value = super().to_python(value)
        if value:
            url_fields = split_url(value)
            if not url_fields[0]:
                url_fields[0] = self.assume_scheme
            if not url_fields[1]:
                url_fields[1] = url_fields[2]
                url_fields[2] = ""
                url_fields = split_url(urlunsplit(url_fields))
            value = urlunsplit(url_fields)
        return value

class RegexField(CharField):
    def __init__(self, regex, **kwargs):
        kwargs.setdefault("strip", False)
        super().__init__(**kwargs)
        self._set_regex(regex)

    def _get_regex(self):
        return self._regex

    def _set_regex(self, regex):
        if isinstance(regex, str):
            regex = re.compile(regex)
        self._regex = regex
        if hasattr(self, "_regex_validator") and self._regex_validator in self.validators:
            self.validators.remove(self._regex_validator)
        self._regex_validator = validators.RegexValidator(regex=regex)
        self.validators.append(self._regex_validator)

    regex = property(_get_regex, _set_regex)


class BooleanField:
    widget = CheckboxInput
    default_error_messages = {
        "required": _("This field is required."),
    }
    empty_values = list(validators.EMPTY_VALUES)

    def __init__(self, **kwargs):
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
            
        self.error_messages = {}
        for cls in reversed(self.__class__.__mro__):
            self.error_messages.update(getattr(cls, 'default_error_messages', {}))
        self.error_messages.update(kwargs.get('error_messages', {}))
        
        self.validators = kwargs.get('validators', [])

    def to_python(self, value):
        if isinstance(value, str) and value.lower() in ("false", "0"):
            value = False
        else:
            value = bool(value)
        return value

    def validate(self, value):
        if not value and self.required:
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

    def has_changed(self, initial, data):
        if self.disabled:
            return False
        return self.to_python(initial) != self.to_python(data)

    def widget_attrs(self, widget):
        return {}

    def bound_data(self, data, initial):
        if self.disabled:
            return initial
        return data

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

class NullBooleanField(BooleanField):
    widget = NullBooleanSelect

    def to_python(self, value):
        if value in (True, "True", "true", "1"):
            return True
        elif value in (False, "False", "false", "0"):
            return False
        else:
            return None

    def validate(self, value):
        pass

class ChoiceField:
    widget = Select
    default_error_messages = {
        "invalid_choice": _("Select a valid choice. %(value)s is not one of the available choices."),
        "required": _("This field is required."),
    }
    empty_values = list(validators.EMPTY_VALUES)

    def __init__(self, *, choices=(), **kwargs):
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
        
        self.validators = kwargs.get('validators', [])
        self.choices = choices

    def __deepcopy__(self, memo):
        result = copy.copy(self)
        memo[id(self)] = result
        result._choices = copy.deepcopy(self._choices, memo)
        result.widget = copy.deepcopy(self.widget, memo)
        result.error_messages = self.error_messages.copy()
        result.validators = self.validators[:]
        return result

    @property
    def choices(self):
        return self._choices

    @choices.setter
    def choices(self, value):
        self._choices = self.widget.choices = normalize_choices(value)

    def to_python(self, value):
        if value in self.empty_values:
            return ""
        return str(value)

    def validate(self, value):
        if value in self.empty_values and self.required:
            raise ValidationError(self.error_messages["required"], code="required")
        if value and not self.valid_value(value):
            raise ValidationError(
                self.error_messages["invalid_choice"],
                code="invalid_choice",
                params={"value": value},
            )

    def valid_value(self, value):
        text_value = str(value)
        for k, v in self.choices:
            if isinstance(v, (list, tuple)):
                for k2, v2 in v:
                    if value == k2 or text_value == str(k2):
                        return True
            else:
                if value == k or text_value == str(k):
                    return True
        return False

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
        return {}

    def bound_data(self, data, initial):
        if self.disabled:
            return initial
        return data

    def has_changed(self, initial, data):
        if self.disabled:
            return False
        initial_value = initial if initial is not None else ""
        data_value = data if data is not None else ""
        return initial_value != data_value

    def get_bound_field(self, form, field_name):
        bound_field_class = self.bound_field_class or form.bound_field_class or BoundField
        return bound_field_class(form, self, field_name)

    def _clean_bound_field(self, bf):
        value = bf.initial if self.disabled else bf.data
        return self.clean(value)

class TypedChoiceField(ChoiceField):
    def __init__(self, *, coerce=lambda val: val, empty_value="", **kwargs):
        self.coerce = coerce
        self.empty_value = empty_value
        super().__init__(**kwargs)

    def _coerce(self, value):
        if value == self.empty_value or value in self.empty_values:
            return self.empty_value
        try:
            value = self.coerce(value)
        except (ValueError, TypeError, ValidationError):
            raise ValidationError(
                self.error_messages["invalid_choice"],
                code="invalid_choice",
                params={"value": value},
            )
        return value

    def clean(self, value):
        value = super().clean(value)
        return self._coerce(value)

class MultipleChoiceField(ChoiceField):
    hidden_widget = MultipleHiddenInput
    widget = SelectMultiple
    default_error_messages = {
        "invalid_choice": _("Select a valid choice. %(value)s is not one of the available choices."),
        "invalid_list": _("Enter a list of values."),
        "required": _("This field is required."),
    }

    def to_python(self, value):
        if not value:
            return []
        elif not isinstance(value, (list, tuple)):
            raise ValidationError(
                self.error_messages["invalid_list"], code="invalid_list"
            )
        return [str(val) for val in value]

    def validate(self, value):
        if self.required and not value:
            raise ValidationError(self.error_messages["required"], code="required")
        for val in value:
            if not self.valid_value(val):
                raise ValidationError(
                    self.error_messages["invalid_choice"],
                    code="invalid_choice",
                    params={"value": val},
                )

    def has_changed(self, initial, data):
        if self.disabled:
            return False
        if initial is None:
            initial = []
        if data is None:
            data = []
        if len(initial) != len(data):
            return True
        initial_set = {str(value) for value in initial}
        data_set = {str(value) for value in data}
        return data_set != initial_set

class TypedMultipleChoiceField(MultipleChoiceField):
    def __init__(self, *, coerce=lambda val: val, **kwargs):
        self.coerce = coerce
        self.empty_value = kwargs.pop("empty_value", [])
        super().__init__(**kwargs)

    def _coerce(self, value):
        if value == self.empty_value or value in self.empty_values:
            return self.empty_value
        new_value = []
        for choice in value:
            try:
                new_value.append(self.coerce(choice))
            except (ValueError, TypeError, ValidationError):
                raise ValidationError(
                    self.error_messages["invalid_choice"],
                    code="invalid_choice",
                    params={"value": choice},
                )
        return new_value

    def clean(self, value):
        value = super().clean(value)
        return self._coerce(value)

    def validate(self, value):
        if value != self.empty_value:
            super().validate(value)
        elif self.required:
            raise ValidationError(self.error_messages["required"], code="required")

class FilePathField(ChoiceField):
    def __init__(
        self,
        path,
        *,
        match=None,
        recursive=False,
        allow_files=True,
        allow_folders=False,
        **kwargs,
    ):
        self.path = path
        self.match = match
        self.recursive = recursive
        self.allow_files = allow_files
        self.allow_folders = allow_folders
        
        super().__init__(choices=(), **kwargs)

        if self.required:
            self.choices = []
        else:
            self.choices = [("", "---------")]

        if self.match is not None:
            self.match_re = re.compile(self.match)

        if recursive:
            for root, dirs, files in sorted(os.walk(self.path)):
                if self.allow_files:
                    for f in sorted(files):
                        if self.match is None or self.match_re.search(f):
                            f = os.path.join(root, f)
                            self.choices.append((f, f.replace(path, "", 1)))
                if self.allow_folders:
                    for f in sorted(dirs):
                        if f == "__pycache__":
                            continue
                        if self.match is None or self.match_re.search(f):
                            f = os.path.join(root, f)
                            self.choices.append((f, f.replace(path, "", 1)))
        else:
            choices = []
            with os.scandir(self.path) as entries:
                for f in entries:
                    if f.name == "__pycache__":
                        continue
                    if (
                        (self.allow_files and f.is_file())
                        or (self.allow_folders and f.is_dir())
                    ) and (self.match is None or self.match_re.search(f.name)):
                        choices.append((f.path, f.name))
            choices.sort(key=operator.itemgetter(1))
            self.choices.extend(choices)

        self.widget.choices = self.choices


class ComboField:
    default_error_messages = {
        "required": _("This field is required."),
    }
    empty_values = list(validators.EMPTY_VALUES)

    def __init__(self, fields, **kwargs):
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
        
        for f in fields:
            f.required = False
        self.fields = fields
        
        widget = kwargs.get('widget', self.widget)
        if isinstance(widget, type):
            widget = widget()
        self.widget = copy.deepcopy(widget)
        self.widget.is_required = self.required
            
        self.error_messages = {}
        for cls in reversed(self.__class__.__mro__):
            self.error_messages.update(getattr(cls, 'default_error_messages', {}))
        self.error_messages.update(kwargs.get('error_messages', {}))
        
        self.validators = kwargs.get('validators', [])

    def clean(self, value):
        value = super().clean(value)
        for field in self.fields:
            value = field.clean(value)
        return value


class MultiValueField:
    default_error_messages = {
        "invalid": _("Enter a list of values."),
        "incomplete": _("Enter a complete value."),
        "required": _("This field is required."),
    }
    empty_values = list(validators.EMPTY_VALUES)

    def __init__(self, fields, *, require_all_fields=True, **kwargs):
        self.require_all_fields = require_all_fields
        self.fields = fields
        
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
        
        for f in fields:
            f.error_messages.setdefault("incomplete", self.error_messages["incomplete"])
            if self.disabled:
                f.disabled = True
            if self.require_all_fields:
                f.required = False
                
        widget = kwargs.get('widget', self.widget)
        if isinstance(widget, type):
            widget = widget()
        self.widget = copy.deepcopy(widget)
        self.widget.is_required = self.required
            
        self.error_messages = {}
        for cls in reversed(self.__class__.__mro__):
            self.error_messages.update(getattr(cls, 'default_error_messages', {}))
        self.error_messages.update(kwargs.get('error_messages', {}))
        
        self.validators = kwargs.get('validators', [])

    def __deepcopy__(self, memo):
        result = copy.copy(self)
        memo[id(self)] = result
        result.fields = tuple(x.__deepcopy__(memo) for x in self.fields)
        result.widget = copy.deepcopy(self.widget, memo)
        result.error_messages = self.error_messages.copy()
        result.validators = self.validators[:]
        return result

    def validate(self, value):
        pass

    def clean(self, value):
        clean_data = []
        errors = []
        
        if self.disabled and not isinstance(value, list):
            value = self.widget.decompress(value)
            
        if not value or isinstance(value, (list, tuple)):
            if not value or not [v for v in value if v not in self.empty_values]:
                if self.required:
                    raise ValidationError(self.error_messages["required"], code="required")
                return self.compress([])
        else:
            raise ValidationError(self.error_messages["invalid"], code="invalid")
            
        for i, field in enumerate(self.fields):
            try:
                field_value = value[i]
            except IndexError:
                field_value = None
                
            if field_value in self.empty_values:
                if self.require_all_fields and self.required:
                    raise ValidationError(self.error_messages["required"], code="required")
                elif field.required:
                    if field.error_messages["incomplete"] not in errors:
                        errors.append(field.error_messages["incomplete"])
                    continue
                    
            try:
                clean_data.append(field.clean(field_value))
            except ValidationError as e:
                errors.extend(m for m in e.error_list if m not in errors)
                
        if errors:
            raise ValidationError(errors)

        out = self.compress(clean_data)
        self.validate(out)
        self.run_validators(out)
        return out

    def compress(self, data_list):
        raise NotImplementedError("Subclasses must implement this method.")

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

    def has_changed(self, initial, data):
        if self.disabled:
            return False
        if initial is None:
            initial = ["" for x in range(0, len(data))]
        else:
            if not isinstance(initial, list):
                initial = self.widget.decompress(initial)
        for field, initial, data in zip(self.fields, initial, data):
            try:
                initial = field.to_python(initial)
            except ValidationError:
                return True
            if field.has_changed(initial, data):
                return True
        return False

    def widget_attrs(self, widget):
        return {}

    def bound_data(self, data, initial):
        if self.disabled:
            return initial
        return data

    def get_bound_field(self, form, field_name):
        bound_field_class = self.bound_field_class or form.bound_field_class or BoundField
        return bound_field_class(form, self, field_name)

    def _clean_bound_field(self, bf):
        value = bf.initial if self.disabled else bf.data
        return self.clean(value)

class SplitDateTimeField(MultiValueField):
    widget = SplitDateTimeWidget
    hidden_widget = SplitHiddenDateTimeWidget
    default_error_messages = {
        "invalid_date": _("Enter a valid date."),
        "invalid_time": _("Enter a valid time."),
        "required": _("This field is required."),
    }

    def __init__(self, *, input_date_formats=None, input_time_formats=None, **kwargs):
        errors = self.default_error_messages.copy()
        if "error_messages" in kwargs:
            errors.update(kwargs["error_messages"])
        localize = kwargs.get("localize", False)
        fields = (
            DateField(
                input_formats=input_date_formats,
                error_messages={"invalid": errors["invalid_date"]},
                localize=localize,
            ),
            TimeField(
                input_formats=input_time_formats,
                error_messages={"invalid": errors["invalid_time"]},
                localize=localize,
            ),
        )
        super().__init__(fields, **kwargs)

    def compress(self, data_list):
        if data_list:
            if data_list[0] in self.empty_values:
                raise ValidationError(
                    self.error_messages["invalid_date"], code="invalid_date"
                )
            if data_list[1] in self.empty_values:
                raise ValidationError(
                    self.error_messages["invalid_time"], code="invalid_time"
                )
            result = datetime.datetime.combine(*data_list)
            return from_current_timezone(result)
        return None

class SlugField(CharField):
    default_validators = [validators.validate_slug]

    def __init__(self, *, allow_unicode=False, **kwargs):
        self.allow_unicode = allow_unicode
        if self.allow_unicode:
            self.default_validators = [validators.validate_unicode_slug]
        super().__init__(**kwargs)

class UUIDField(CharField):
    default_error_messages = {
        "invalid": _("Enter a valid UUID."),
        "required": _("This field is required."),
    }

    def prepare_value(self, value):
        if isinstance(value, uuid.UUID):
            return str(value)
        return value

    def to_python(self, value):
        value = super().to_python(value)
        if value in self.empty_values:
            return None
        if not isinstance(value, uuid.UUID):
            try:
                value = uuid.UUID(value)
            except ValueError:
                raise ValidationError(self.error_messages["invalid"], code="invalid")
        return value

class InvalidJSONInput(str):
    pass

class JSONString(str):
    pass

class JSONField(CharField):
    default_error_messages = {
        "invalid": _("Enter a valid JSON."),
        "required": _("This field is required."),
    }
    widget = Textarea

    def __init__(self, encoder=None, decoder=None, **kwargs):
        self.encoder = encoder
        self.decoder = decoder
        super().__init__(**kwargs)

    def to_python(self, value):
        if self.disabled:
            return value
        if value in self.empty_values:
            return None
        elif isinstance(value, (list, dict, int, float, JSONString)):
            return value
        try:
            converted = json.loads(value, cls=self.decoder)
        except json.JSONDecodeError:
            raise ValidationError(
                self.error_messages["invalid"],
                code="invalid",
                params={"value": value},
            )
        if isinstance(converted, str):
            return JSONString(converted)
        else:
            return converted

    def bound_data(self, data, initial):
        if self.disabled:
            return initial
        if data is None:
            return None
        try:
            return json.loads(data, cls=self.decoder)
        except json.JSONDecodeError:
            return InvalidJSONInput(data)

    def prepare_value(self, value):
        if isinstance(value, InvalidJSONInput):
            return value
        return json.dumps(value, ensure_ascii=False, cls=self.encoder)

    def has_changed(self, initial, data):
        if super().has_changed(initial, data):
            return True
        return json.dumps(initial, sort_keys=True, cls=self.encoder) != json.dumps(
            self.to_python(data), sort_keys=True, cls=self.encoder
        )
    
    
class GenericIPAddressField(CharField):
    def __init__(self, *, protocol="both", unpack_ipv4=False, **kwargs):
        self.unpack_ipv4 = unpack_ipv4
        self.default_validators = validators.ip_address_validators(protocol, unpack_ipv4)
        kwargs.setdefault("max_length", MAX_IPV6_ADDRESS_LENGTH)
        super().__init__(**kwargs)

    def to_python(self, value):
        if value in self.empty_values:
            return ""
        value = value.strip()
        if value and ":" in value:
            return clean_ipv6_address(value, self.unpack_ipv4, max_length=self.max_length)
        return value

