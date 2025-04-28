from django.db.backends.base.validation import BaseDatabaseValidation

class DatabaseValidation(BaseDatabaseValidation):
    def check_field_type(self, field, field_type):
        """
        SQL Server has slightly different restrictions on field types than other
        databases, so override this method to implement those.
        """
        errors = []
        
        # Check max_length for char fields
        if field_type in ('CharField', 'TextField') and field.max_length and field.max_length > 8000:
            errors.append(
                "SQL Server does not support CharFields with max_length > 8000. "
                "Use TextField instead."
            )
        
        return errors