from django.db.backends.base.operations import BaseDatabaseOperations

class DatabaseOperations(BaseDatabaseOperations):
    compiler_module = "django.db.backends.mssql.compiler"

    def quote_name(self, name):
        if name.startswith('[') and name.endswith(']'):
            return name  # Quoting once is enough
        return '[%s]' % name

    def sql_flush(self, style, tables, *, reset_sequences=False, allow_cascade=False):
        if not tables:
            return []

        sql = []
        if reset_sequences:
            sql.extend(self.sequence_reset_by_name_sql(style, tables))
        
        # Disable all constraints
        sql.append('EXEC sp_MSforeachtable "ALTER TABLE ? NOCHECK CONSTRAINT ALL"')
        
        # Delete data from all tables
        for table in tables:
            sql.append('%s %s %s;' % (
                style.SQL_KEYWORD('DELETE FROM'),
                style.SQL_FIELD(self.quote_name(table)),
                style.SQL_KEYWORD('WHERE 1=1'),
            ))
        
        # Re-enable constraints
        sql.append('EXEC sp_MSforeachtable "ALTER TABLE ? CHECK CONSTRAINT ALL"')
        
        return sql

    def sequence_reset_by_name_sql(self, style, sequences):
        sql = []
        for sequence in sequences:
            table_name = sequence['table']
            column_name = sequence['column']
            sql.append("%s %s %s %s %s %s %s;" % (
                style.SQL_KEYWORD('DBCC'),
                style.SQL_KEYWORD('CHECKIDENT'),
                style.SQL_FIELD(self.quote_name(table_name)),
                style.SQL_KEYWORD('RESEED'),
                style.SQL_KEYWORD('WITH'),
                style.SQL_KEYWORD('NO_INFOMSGS'),
                style.SQL_KEYWORD(',')
            ))
        return sql

    def limit_offset_sql(self, low_mark, high_mark):
        limit, offset = self._get_limit_offset_params(low_mark, high_mark)
        if offset:
            return " OFFSET %d ROWS FETCH NEXT %d ROWS ONLY" % (offset, limit)
        elif limit:
            return " TOP %d" % limit
        return ""

    def last_executed_query(self, cursor, sql, params):
        if params:
            return sql % tuple(params)
        return sql

    def no_limit_value(self):
        return None

    def prepare_sql_script(self, sql):
        return [sql]

    def adapt_datetimefield_value(self, value):
        return value

    def adapt_timefield_value(self, value):
        return value

    def regex_lookup(self, lookup_type):
        raise NotImplementedError("Regex lookups are not supported by SQL Server")

    def date_extract_sql(self, lookup_type, field_name):
        if lookup_type == 'week_day':
            return "DATEPART(weekday, %s)" % field_name
        elif lookup_type == 'iso_week_day':
            return "DATEPART(isowk, %s)" % field_name
        elif lookup_type == 'iso_year':
            return "DATEPART(isoyear, %s)" % field_name
        else:
            return "DATEPART(%s, %s)" % (lookup_type, field_name)

    def datetime_cast_date_sql(self, field_name, tzname):
        return "CONVERT(date, %s)" % field_name

    def datetime_cast_time_sql(self, field_name, tzname):
        return "CONVERT(time, %s)" % field_name

    def datetime_extract_sql(self, lookup_type, field_name, tzname):
        return self.date_extract_sql(lookup_type, field_name)

    def combine_expression(self, connector, sub_expressions):
        if connector == '^':
            return 'POWER(%s)' % ','.join(sub_expressions)
        elif connector == '#':
            return '%s ^ %s' % tuple(sub_expressions)
        return super().combine_expression(connector, sub_expressions)

    def subtract_temporals(self, internal_type, lhs, rhs):
        if internal_type == 'DateField':
            return "DATEDIFF(day, %s, %s)" % (rhs, lhs)
        elif internal_type == 'DateTimeField':
            return "DATEDIFF(second, %s, %s)" % (rhs, lhs)
        elif internal_type == 'TimeField':
            return "DATEDIFF(second, %s, %s)" % (rhs, lhs)