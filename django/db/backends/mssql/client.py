from django.db.backends.base.client import BaseDatabaseClient

class DatabaseClient(BaseDatabaseClient):
    executable_name = "sqlcmd"

    @classmethod
    def settings_to_cmd_args_env(cls, settings_dict, parameters):
        args = [cls.executable_name]
        db = settings_dict['OPTIONS'].get('database', settings_dict['NAME'])
        server = settings_dict['OPTIONS'].get('server', settings_dict['HOST'])
        user = settings_dict['OPTIONS'].get('user', settings_dict['USER'])
        password = settings_dict['OPTIONS'].get('password', settings_dict['PASSWORD'])
        port = settings_dict['OPTIONS'].get('port', settings_dict['PORT'] or '1433')

        if user:
            args += ["-U", user]
            if password:
                args += ["-P", password]
        else:
            args += ["-E"]  # Use trusted connection

        if server:
            args += ["-S", f"{server},{port}" if port else server]
        if db:
            args += ["-d", db]

        args.extend(parameters)
        return args, None