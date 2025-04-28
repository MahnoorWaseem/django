"""
Microsoft SQL Server database backend for Django.

Requires pyodbc: https://pypi.org/project/pyodbc/
"""
# extension of adapter
import pyodbc
from django.core.exceptions import ImproperlyConfigured
from django.db import IntegrityError
from django.db.backends import utils as backend_utils
from django.db.backends.base.base import BaseDatabaseWrapper
from django.utils.asyncio import async_unsafe
from django.utils.functional import cached_property
from django.utils.regex_helper import _lazy_re_compile

try:
    import pyodbc as Database
except ImportError as err:
    raise ImproperlyConfigured(
        "Error loading pyodbc module.\nDid you install pyodbc?"
    ) from err

# Some of these import pyodbc, so import them after checking if it's installed.

from django.db.backends.mssql.client import DatabaseClient
from django.db.backends.mssql.creation import DatabaseCreation
from django.db.backends.mssql.features import DatabaseFeatures
from django.db.backends.mssql.introspection import DatabaseIntrospection
from django.db.backends.mssql.operations import DatabaseOperations
from django.db.backends.mssql.schema import DatabaseSchemaEditor
from django.db.backends.mssql.validation import DatabaseValidation

# This should match the numerical portion of the version numbers
server_version_re = _lazy_re_compile(r"(\d{1,2})\.(\d{1,2})\.(\d{1,4})")

db_config =  {
        'ENGINE': 'django_mssql',
        'NAME': 'django_mssql',
        'USER': 'user123',  # Comment out for Windows Auth
        'PASSWORD': '*****',  # Comment out for Windows Auth
        'HOST': 'localhost',
        'PORT': '1433',
        'CONN_MAX_AGE': 0,
        'CONN_HEALTH_CHECKS': False,
        'TIME_ZONE': 'UTC',
        'OPTIONS': {
            'driver': 'ODBC Driver 17 for SQL Server',
            'timeout': 30,
            'trusted_connection': 'yes',  # Uncomment for Windows Auth
        },
    }


class CursorWrapper:
    """
    A thin wrapper around pyodbc's normal cursor class that catches particular
    exception instances and reraises them with the correct types.
    """

    codes_for_integrityerror = (
        515,  # Cannot insert NULL
        547,  # Foreign key violation
        2601,  # Unique constraint violation
        2627,  # Primary key violation
    )

    def __init__(self, cursor):
        self.cursor = cursor

    def execute(self, query, args=None):
        try:
            return self.cursor.execute(query, args)
        except Database.IntegrityError as e:
            raise IntegrityError(*tuple(e.args)) from e
        except Database.Error as e:
            # Map some error codes to IntegrityError
            if hasattr(e, 'sqlstate') and e.sqlstate in self.codes_for_integrityerror:
                raise IntegrityError(*tuple(e.args)) from e
            raise

    def executemany(self, query, args):
        try:
            return self.cursor.executemany(query, args)
        except Database.IntegrityError as e:
            raise IntegrityError(*tuple(e.args)) from e
        except Database.Error as e:
            # Map some error codes to IntegrityError
            if hasattr(e, 'sqlstate') and e.sqlstate in self.codes_for_integrityerror:
                raise IntegrityError(*tuple(e.args)) from e
            raise

    def __getattr__(self, attr):
        return getattr(self.cursor, attr)

    def __iter__(self):
        return iter(self.cursor)


class DatabaseWrapper(BaseDatabaseWrapper):
    vendor = "mssql"
    display_name = "Microsoft SQL Server"

    data_types = {
        "AutoField": "int IDENTITY (1, 1)",
        "BigAutoField": "bigint IDENTITY (1, 1)",
        "BinaryField": "varbinary(max)",
        "BooleanField": "bit",
        "CharField": "nvarchar(%(max_length)s)",
        "DateField": "date",
        "DateTimeField": "datetime2",
        "DecimalField": "numeric(%(max_digits)s, %(decimal_places)s)",
        "DurationField": "bigint",
        "FileField": "nvarchar(%(max_length)s)",
        "FilePathField": "nvarchar(%(max_length)s)",
        "FloatField": "float",
        "IntegerField": "int",
        "BigIntegerField": "bigint",
        "IPAddressField": "nvarchar(15)",
        "GenericIPAddressField": "nvarchar(39)",
        "JSONField": "nvarchar(max)",
        "OneToOneField": "int",
        "PositiveBigIntegerField": "bigint",
        "PositiveIntegerField": "int",
        "PositiveSmallIntegerField": "smallint",
        "SlugField": "nvarchar(%(max_length)s)",
        "SmallAutoField": "smallint IDENTITY (1, 1)",
        "SmallIntegerField": "smallint",
        "TextField": "nvarchar(max)",
        "TimeField": "time",
        "UUIDField": "uniqueidentifier",
    }

    operators = {
        "exact": "= %s",
        "iexact": "LIKE %s",
        "contains": "LIKE %s",
        "icontains": "LIKE %s",
        "gt": "> %s",
        "gte": ">= %s",
        "lt": "< %s",
        "lte": "<= %s",
        "startswith": "LIKE %s",
        "endswith": "LIKE %s",
        "istartswith": "LIKE %s",
        "iendswith": "LIKE %s",
    }

    pattern_esc = r"REPLACE(REPLACE(REPLACE({}, '\', '\\'), '%%', '\%%'), '_', '\_')"
    pattern_ops = {
        "contains": "LIKE '%%' + {} + '%%'",
        "icontains": "LIKE '%%' + {} + '%%'",
        "startswith": "LIKE {} + '%%'",
        "istartswith": "LIKE {} + '%%'",
        "endswith": "LIKE '%%' + {}",
        "iendswith": "LIKE '%%' + {}",
    }

    isolation_levels = {
        "read uncommitted",
        "read committed",
        "repeatable read",
        "serializable",
        "snapshot",
    }

    Database = Database
    SchemaEditorClass = DatabaseSchemaEditor
    client_class = DatabaseClient
    creation_class = DatabaseCreation
    features_class = DatabaseFeatures
    introspection_class = DatabaseIntrospection
    ops_class = DatabaseOperations
    validation_class = DatabaseValidation

    def get_database_version(self):
        return self.sql_server_version

    def get_connection_params(self):
        settings_dict = self.settings_dict
        kwargs = {
            'driver': settings_dict['OPTIONS'].get('driver', 'ODBC Driver 17 for SQL Server'),
            'server': settings_dict['HOST'],
            'database': settings_dict['NAME'],
            'port': str(settings_dict['PORT'] or 1433),
        }

        # Handle authentication
        if settings_dict['USER']:
            kwargs['uid'] = settings_dict['USER']
            kwargs['pwd'] = settings_dict['PASSWORD']
        else:
            kwargs['trusted_connection'] = 'yes'  # Windows Authentication

        # Add additional options
        kwargs.update(settings_dict.get('OPTIONS', {}))
        
        # Remove None values
        return {k: v for k, v in kwargs.items() if v is not None}

    @async_unsafe
    def get_new_connection(self, conn_params):
        connection_string = (
            "DRIVER={{{driver}}};"
            "SERVER={server},{port};"
            "DATABASE={database};"
            "UID={user};"
            "PWD={password};"
            "Trusted_Connection={trusted_connection};"
        ).format(**conn_params)
        
        connection = Database.connect(connection_string)
        return connection

    def init_connection_state(self):
        super().init_connection_state()
        assignments = []
        
        if self.isolation_level:
            assignments.append(
                "SET TRANSACTION ISOLATION LEVEL %s" % self.isolation_level.upper()
            )
            
        # Set ANSI_NULLS and QUOTED_IDENTIFIER for consistent behavior
        assignments.extend([
            "SET ANSI_NULLS ON",
            "SET QUOTED_IDENTIFIER ON",
            "SET ANSI_PADDING ON",
            "SET ANSI_WARNINGS ON",
        ])
        
        if assignments:
            with self.cursor() as cursor:
                cursor.execute("; ".join(assignments))

    @async_unsafe
    def create_cursor(self, name=None):
        cursor = self.connection.cursor()
        return CursorWrapper(cursor)

    def _set_autocommit(self, autocommit):
        with self.wrap_database_errors:
            self.connection.autocommit = autocommit

    def disable_constraint_checking(self):
        """
        Disable foreign key constraint checking.
        """
        with self.cursor() as cursor:
            cursor.execute("EXEC sp_MSforeachtable 'ALTER TABLE ? NOCHECK CONSTRAINT ALL'")
        return True

    def enable_constraint_checking(self):
        """
        Re-enable foreign key constraint checking.
        """
        # Override needs_rollback in case constraint_checks_disabled is
        # nested inside transaction.atomic.
        self.needs_rollback, needs_rollback = False, self.needs_rollback
        try:
            with self.cursor() as cursor:
                cursor.execute("EXEC sp_MSforeachtable 'ALTER TABLE ? CHECK CONSTRAINT ALL'")
        finally:
            self.needs_rollback = needs_rollback

    def check_constraints(self, table_names=None):
        """
        Check constraints on tables.
        """
        with self.cursor() as cursor:
            if table_names is None:
                table_names = self.introspection.table_names(cursor)
            for table_name in table_names:
                primary_key_column_name = self.introspection.get_primary_key_column(
                    cursor, table_name
                )
                if not primary_key_column_name:
                    continue
                relations = self.introspection.get_relations(cursor, table_name)
                for column_name, (
                    referenced_column_name,
                    referenced_table_name,
                ) in relations.items():
                    cursor.execute(
                        """
                        SELECT REFERRING.%s, REFERRING.%s FROM %s as REFERRING
                        LEFT JOIN %s as REFERRED
                        ON (REFERRING.%s = REFERRED.%s)
                        WHERE REFERRING.%s IS NOT NULL AND REFERRED.%s IS NULL
                        """
                        % (
                            primary_key_column_name,
                            column_name,
                            table_name,
                            referenced_table_name,
                            column_name,
                            referenced_column_name,
                            column_name,
                            referenced_column_name,
                        )
                    )
                    for bad_row in cursor.fetchall():
                        raise IntegrityError(
                            "The row in table '%s' with primary key '%s' has an "
                            "invalid foreign key: %s.%s contains a value '%s' that "
                            "does not have a corresponding value in %s.%s."
                            % (
                                table_name,
                                bad_row[0],
                                table_name,
                                column_name,
                                bad_row[1],
                                referenced_table_name,
                                referenced_column_name,
                            )
                        )

    def is_usable(self):
        try:
            # Use a simple query to check connection
            with self.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
            return True
        except Database.Error:
            return False

    @cached_property
    def sql_server_data(self):
        with self.temporary_connection() as cursor:
            cursor.execute("""
                SELECT @@VERSION,
                        @@LOCK_TIMEOUT,
                        @@MAX_PRECISION,
                        @@TEXTSIZE
            """)
            row = cursor.fetchone()
        return {
            "version": row[0],
            "lock_timeout": row[1],
            "max_precision": row[2],
            "textsize": row[3],
        }

    @cached_property
    def sql_server_info(self):
        return self.sql_server_data["version"]

    @cached_property
    def sql_server_version(self):
        match = server_version_re.search(self.sql_server_info)
        if not match:
            raise Exception(
                "Unable to determine SQL Server version from version string %r"
                % self.sql_server_info
            )
        return tuple(int(x) for x in match.groups())

    @cached_property
    def data_type_check_constraints(self):
        check_constraints = {
            "PositiveBigIntegerField": "%(column)s >= 0",
            "PositiveIntegerField": "%(column)s >= 0",
            "PositiveSmallIntegerField": "%(column)s >= 0",
        }
        return check_constraints

# to make it runnable
if __name__ == '__main__':
    # Minimal Django settings configuration
    from django.conf import settings
    if not settings.configured:
        settings.configure(
            TIME_ZONE='UTC',
            USE_TZ=True,
            DATABASES={
                'default': {
                    'ENGINE': 'django.db.backends.dummy',  # Just for settings
                }
            }
        )

    # Test code with proper settings
    wrapper = DatabaseWrapper({
        'ENGINE': 'django_mssql',
        'NAME': 'your_db',
        'USER': 'your_user',
        'PASSWORD': 'your_pwd',
        'HOST': 'localhost',
        'PORT': '1433',
        'OPTIONS': {'driver': 'ODBC Driver 17 for SQL Server'},
        'TIME_ZONE': 'UTC',  # Add this
    })
    
    print("Testing DatabaseWrapper directly:")
    print(f"Display name: {wrapper.display_name}")
    
    try:
        wrapper.ensure_connection()
        with wrapper.cursor() as cursor:
            cursor.execute("SELECT @@VERSION")
            print("SQL Server version:", cursor.fetchone()[0])
    except Exception as e:
        print(f"Connection failed: {e}")
    finally:
        wrapper.close()