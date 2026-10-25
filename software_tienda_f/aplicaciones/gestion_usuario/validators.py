from django.core.exceptions import ValidationError


class ComplejidadContrasenaValidator:
    def validate(self, password, user=None):
        if not any(caracter.isdigit() for caracter in password):
            raise ValidationError(
                'La contraseña debe contener al menos un número.',
                code='sin_numero')
        if not any(not caracter.isalnum() for caracter in password):
            raise ValidationError(
                'La contraseña debe contener al menos un carácter especial '
                '(por ejemplo # $ % &).', code='sin_especial')

    def get_help_text(self):
        return ('La contraseña debe contener al menos un número y un carácter '
                'especial (por ejemplo # $ % &).')
