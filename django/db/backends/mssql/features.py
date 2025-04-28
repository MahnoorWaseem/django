from django.db.backends.base.features import BaseDatabaseFeatures

class DatabaseFeatures(BaseDatabaseFeatures):
    allows_group_by_selected_pks = True
    can_return_columns_from_insert = True
    can_return_ids_from_bulk_insert = True
    has_bulk_insert = True
    has_native_uuid_field = True
    has_native_duration_field = False
    has_select_for_update = True
    has_select_for_update_nowait = True
    has_select_for_update_of = True
    has_select_for_update_skip_locked = True
    supports_transactions = True
    supports_timezones = False
    supports_partial_indexes = True
    supports_deferrable_unique_constraints = True
    supports_expression_indexes = True
    can_introspect_check_constraints = True
    can_introspect_default = False  # SQL Server stores defaults as constraints
    can_introspect_foreign_keys = True
    can_introspect_json_field = True
    can_introspect_small_integer_field = True
    supports_column_check_constraints = True
    supports_table_check_constraints = True
    ignores_table_name_case = True
    supports_ignore_conflicts = False
    supports_over_clause = True
    supports_paramstyle_pyformat = False
    supports_paramstyle_format = True
    requires_literal_defaults = True
    can_rollback_ddl = True
    supports_comments = True
    supports_comments_inline = True
    supports_sequence_reset = False
    can_create_inline_fk = False
    supports_json_field_contains = False
    supports_primitives_in_json_field = True
    supports_collation_on_charfield = True
    supports_collation_on_textfield = True
    test_collations = {
        'ci': 'Latin1_General_CI_AS',
        'cs': 'Latin1_General_CS_AS',
        'non_default': 'Latin1_General_CS_AS',
        'swedish_ci': 'Finnish_Swedish_CI_AS',
    }