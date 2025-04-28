from django.contrib.auth import get_user_model

UserModel = get_user_model()

class AuthBackend:
    def __init__(self, backend_type='model', create_unknown_user=True):
        self.backend_type = backend_type  # 'model' or 'remote'
        self.create_unknown_user = create_unknown_user

    def authenticate(self, request, username=None, password=None, remote_user=None, **kwargs):
        if self.backend_type == 'model':
            return self._model_authenticate(request, username, password, **kwargs)
        elif self.backend_type == 'remote':
            return self._remote_authenticate(request, remote_user)
        return None

    def user_can_authenticate(self, user):
        """Can be overridden if needed, default checks is_active"""
        return getattr(user, "is_active", True)

    def clean_username(self, username):
        """Override to clean remote usernames if needed"""
        return username

    def configure_user(self, request, user, created=True):
        """Override to configure new users if needed"""
        return user
