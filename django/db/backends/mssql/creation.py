from django.db.backends.base.creation import BaseDatabaseCreation

class DatabaseCreation(BaseDatabaseCreation):
    def _execute_create_test_db(self, cursor, parameters, keepdb=False):
        try:
            super()._execute_create_test_db(cursor, parameters, keepdb)
        except Exception as e:
            if not keepdb:
                # If database creation failed and we're not keeping the db, try to remove it
                try:
                    self._execute_destroy_test_db(cursor, parameters, verbosity=0)
                except Exception:
                    pass
            raise

    def _destroy_test_db(self, test_database_name, verbosity):
        """
        Destroy a test database, prompting the user for confirmation if the
        database already exists.
        """
        with self.connection.cursor() as cursor:
            # Set the database to single user mode to drop it
            cursor.execute(f"""
                ALTER DATABASE [{test_database_name}]
                SET SINGLE_USER WITH ROLLBACK IMMEDIATE
            """)
            cursor.execute(f"DROP DATABASE [{test_database_name}]")