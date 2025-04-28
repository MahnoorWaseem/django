from django.db.backends.base.introspection import (
    BaseDatabaseIntrospection, FieldInfo, TableInfo,
)

class DatabaseIntrospection(BaseDatabaseIntrospection):
    # Map type codes to Django Field types.
    data_types_reverse = {
        34: 'CharField',      # image
        35: 'TextField',      # text
        36: 'UUIDField',      # uniqueidentifier
        48: 'SmallIntegerField',  # tinyint
        52: 'SmallIntegerField',  # smallint
        56: 'IntegerField',   # int
        58: 'DateField',      # smalldatetime
        59: 'FloatField',     # real
        60: 'DecimalField',   # money
        61: 'DateTimeField',  # datetime
        62: 'FloatField',     # float
        98: 'JSONField',      # sql_variant
        99: 'TextField',      # ntext
        104: 'BooleanField',  # bit
        106: 'DecimalField',  # decimal
        108: 'DecimalField',  # numeric
        122: 'FloatField',    # smallmoney
        127: 'BigIntegerField',  # bigint
        165: 'BinaryField',   # varbinary
        167: 'CharField',    # varchar
        173: 'BinaryField',   # binary
        175: 'CharField',     # char
        189: 'DateTimeField', # timestamp
        231: 'CharField',     # nvarchar
        239: 'CharField',     # nchar
        241: 'TextField',     # xml
    }

    def get_table_list(self, cursor):
        """Return a list of table and view names in the current database."""
        cursor.execute("""
            SELECT table_name, table_type
            FROM information_schema.tables
            WHERE table_schema = SCHEMA_NAME()
            ORDER BY table_name
        """)
        return [
            TableInfo(row[0], row[1].lower())
            for row in cursor.fetchall()
            if row[0] not in self.ignored_tables
        ]

    def get_table_description(self, cursor, table_name):
        """
        Return a description of the table with the DB-API cursor.description
        interface.
        """
        cursor.execute(
            f"SELECT * FROM [{table_name}] WHERE 1=0"
        )
        return cursor.description

    def get_relations(self, cursor, table_name):
        """
        Return a dictionary of {field_name: (field_name_other_table, other_table)}
        representing all relationships to the given table.
        """
        relations = {}
        cursor.execute("""
            SELECT
                KCU1.COLUMN_NAME,
                KCU2.TABLE_NAME,
                KCU2.COLUMN_NAME
            FROM
                INFORMATION_SCHEMA.REFERENTIAL_CONSTRAINTS AS RC
                INNER JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE AS KCU1
                    ON KCU1.CONSTRAINT_CATALOG = RC.CONSTRAINT_CATALOG
                    AND KCU1.CONSTRAINT_SCHEMA = RC.CONSTRAINT_SCHEMA
                    AND KCU1.CONSTRAINT_NAME = RC.CONSTRAINT_NAME
                INNER JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE AS KCU2
                    ON KCU2.CONSTRAINT_CATALOG = RC.UNIQUE_CONSTRAINT_CATALOG
                    AND KCU2.CONSTRAINT_SCHEMA = RC.UNIQUE_CONSTRAINT_SCHEMA
                    AND KCU2.CONSTRAINT_NAME = RC.UNIQUE_CONSTRAINT_NAME
            WHERE
                KCU1.TABLE_NAME = %s
                AND KCU1.TABLE_SCHEMA = SCHEMA_NAME()
        """, [table_name])
        for row in cursor.fetchall():
            relations[row[0]] = (row[2], row[1])
        return relations

    def get_primary_key_column(self, cursor, table_name):
        """
        Return the name of the primary key column for the given table.
        """
        cursor.execute("""
            SELECT COLUMN_NAME
            FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE
            WHERE TABLE_NAME = %s
            AND CONSTRAINT_NAME LIKE 'PK%'
            AND TABLE_SCHEMA = SCHEMA_NAME()
        """, [table_name])
        row = cursor.fetchone()
        return row[0] if row else None

    def get_constraints(self, cursor, table_name):
        """
        Retrieve any constraints or keys (unique, pk, fk, check, index) across
        one or more columns.
        """
        constraints = {}
        # Get PK and unique constraints
        cursor.execute("""
            SELECT
                K.CONSTRAINT_NAME,
                K.COLUMN_NAME,
                C.CONSTRAINT_TYPE,
                K.ORDINAL_POSITION
            FROM
                INFORMATION_SCHEMA.KEY_COLUMN_USAGE AS K
                JOIN INFORMATION_SCHEMA.TABLE_CONSTRAINTS AS C ON
                    K.CONSTRAINT_NAME = C.CONSTRAINT_NAME AND
                    K.TABLE_NAME = C.TABLE_NAME AND
                    K.TABLE_SCHEMA = C.TABLE_SCHEMA
            WHERE
                K.TABLE_NAME = %s AND
                K.TABLE_SCHEMA = SCHEMA_NAME()
            ORDER BY
                K.ORDINAL_POSITION
        """, [table_name])
        for constraint, column, kind, order in cursor.fetchall():
            if constraint not in constraints:
                constraints[constraint] = {
                    'columns': [],
                    'primary_key': kind == 'PRIMARY KEY',
                    'unique': kind in ('PRIMARY KEY', 'UNIQUE'),
                    'foreign_key': None,
                    'check': False,
                    'index': False,
                }
            constraints[constraint]['columns'].append(column)
        
        # Get check constraints
        cursor.execute("""
            SELECT
                CC.CONSTRAINT_NAME,
                CC.CHECK_CLAUSE
            FROM
                INFORMATION_SCHEMA.CHECK_CONSTRAINTS AS CC
                JOIN INFORMATION_SCHEMA.TABLE_CONSTRAINTS AS TC ON
                    CC.CONSTRAINT_NAME = TC.CONSTRAINT_NAME AND
                    CC.CONSTRAINT_SCHEMA = TC.CONSTRAINT_SCHEMA
            WHERE
                TC.TABLE_NAME = %s AND
                TC.CONSTRAINT_TYPE = 'CHECK' AND
                TC.TABLE_SCHEMA = SCHEMA_NAME()
        """, [table_name])
        for constraint, check in cursor.fetchall():
            if constraint not in constraints:
                constraints[constraint] = {
                    'columns': [],
                    'primary_key': False,
                    'unique': False,
                    'foreign_key': None,
                    'check': True,
                    'index': False,
                }
            constraints[constraint]['check'] = check
        
        # Get foreign keys
        cursor.execute("""
            SELECT
                RC.CONSTRAINT_NAME,
                K.COLUMN_NAME,
                PK.TABLE_NAME,
                PK.COLUMN_NAME
            FROM
                INFORMATION_SCHEMA.REFERENTIAL_CONSTRAINTS AS RC
                JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE AS K ON
                    RC.CONSTRAINT_NAME = K.CONSTRAINT_NAME AND
                    RC.CONSTRAINT_SCHEMA = K.CONSTRAINT_SCHEMA
                JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE AS PK ON
                    RC.UNIQUE_CONSTRAINT_NAME = PK.CONSTRAINT_NAME AND
                    RC.UNIQUE_CONSTRAINT_SCHEMA = PK.CONSTRAINT_SCHEMA
            WHERE
                K.TABLE_NAME = %s AND
                K.TABLE_SCHEMA = SCHEMA_NAME()
        """, [table_name])
        for constraint, column, other_table, other_column in cursor.fetchall():
            if constraint not in constraints:
                constraints[constraint] = {
                    'columns': [],
                    'primary_key': False,
                    'unique': False,
                    'foreign_key': (other_table, other_column),
                    'check': False,
                    'index': False,
                }
            constraints[constraint]['columns'].append(column)
            constraints[constraint]['foreign_key'] = (other_table, other_column)
        
        # Get indexes
        cursor.execute("""
            SELECT
                I.name AS index_name,
                IC.key_ordinal AS ordinal_position,
                C.name AS column_name,
                I.is_unique
            FROM
                sys.indexes AS I
                JOIN sys.index_columns AS IC ON I.object_id = IC.object_id AND I.index_id = IC.index_id
                JOIN sys.columns AS C ON IC.object_id = C.object_id AND IC.column_id = C.column_id
                JOIN sys.tables AS T ON I.object_id = T.object_id
            WHERE
                T.name = %s AND
                I.name IS NOT NULL AND
                I.is_primary_key = 0 AND
                I.is_unique_constraint = 0
            ORDER BY
                I.name, IC.key_ordinal
        """, [table_name])
        for index, order, column, unique in cursor.fetchall():
            if index not in constraints:
                constraints[index] = {
                    'columns': [],
                    'primary_key': False,
                    'unique': unique,
                    'foreign_key': None,
                    'check': False,
                    'index': True,
                }
            constraints[index]['columns'].append(column)
        
        return constraints