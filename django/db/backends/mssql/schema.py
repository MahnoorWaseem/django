from django.db import models
from django.db.backends.base.schema import BaseDatabaseSchemaEditor

class DatabaseSchemaEditor(BaseDatabaseSchemaEditor):
    sql_create_column = "ALTER TABLE %(table)s ADD %(column)s %(definition)s"
    sql_alter_column_type = "ALTER COLUMN %(column)s %(type)s"
    sql_alter_column_null = "ALTER COLUMN %(column)s %(type)s %(null)s"
    sql_alter_column_not_null = "ALTER COLUMN %(column)s %(type)s NOT NULL"
    sql_alter_column_default = "ADD DEFAULT %(default)s FOR %(column)s"
    sql_alter_column_no_default = "DROP CONSTRAINT %(constraint_name)s"
    sql_delete_column = "ALTER TABLE %(table)s DROP COLUMN %(column)s"
    sql_delete_table = "DROP TABLE %(table)s"
    sql_create_index = "CREATE INDEX %(name)s ON %(table)s (%(columns)s)%(extra)s"
    sql_delete_index = "DROP INDEX %(name)s ON %(table)s"

    def quote_value(self, value):
        if isinstance(value, str):
            return "'%s'" % value.replace("'", "''")
        elif isinstance(value, (bytes, bytearray)):
            return "0x%s" % value.hex()
        elif isinstance(value, bool):
            return "1" if value else "0"
        elif value is None:
            return "NULL"
        else:
            return str(value)

    def _model_indexes_sql(self, model):
        # SQL Server doesn't support partial indexes
        return []

    def _alter_column_type_sql(self, table, old_field, new_field, new_type):
        # Get the column's current default
        with self.connection.cursor() as cursor:
            cursor.execute("""
                SELECT name
                FROM sys.default_constraints
                WHERE parent_object_id = OBJECT_ID(%s)
                AND parent_column_id = COLUMNPROPERTY(OBJECT_ID(%s), %s, 'ColumnId')
            """, [table, table, old_field.column])
            constraint_name = cursor.fetchone()
        
        sql = []
        if constraint_name:
            sql.append(self._delete_constraint_sql(
                self.sql_alter_column_no_default,
                table,
                constraint_name[0],
            ))
        
        sql.extend(super()._alter_column_type_sql(
            table, old_field, new_field, new_type
        ))
        
        # Add back any default
        if new_field.has_default():
            sql.append((
                self.sql_alter_column_default % {
                    "column": self.quote_name(new_field.column),
                    "default": self._column_default_sql(new_field),
                },
                [],
            ))
        
        return sql

    def _delete_constraint_sql(self, template, table, name):
        return template % {
            "table": self.quote_name(table),
            "constraint_name": self.quote_name(name),
        }

    def _create_index_sql(self, model, fields, *, name=None, suffix='', using='',
                         db_tablespace=None, col_suffixes=(), sql=None, opclasses=(),
                         condition=None, include=None, expressions=None):
        if condition or include:
            raise NotImplementedError(
                "Partial indexes or included columns are not supported."
            )
        return super()._create_index_sql(
            model, fields, name=name, suffix=suffix, using=using,
            db_tablespace=db_tablespace, col_suffixes=col_suffixes, sql=sql,
            opclasses=opclasses, condition=condition, include=include,
            expressions=expressions,
        )

    def _field_should_be_indexed(self, model, field):
        # Don't index text fields
        return (
            super()._field_should_be_indexed(model, field) and
            not isinstance(field, (models.TextField, models.BinaryField))
        )