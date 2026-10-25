from django.core.exceptions import ValidationError


class ComplejidadContrasenaValidator:
    def validate(self, password, user=None):
        if len(password) < 8:
            raise ValidationError(
                'La contrase\u00f1a debe tener al menos 8 caracteres.',
                code='muy_corta')
        if not any(caracter.isupper() for caracter in password):
            raise ValidationError(
                'La contrase\u00f1a debe contener al menos una letra may\u00fascula.',
                code='sin_mayuscula')
        if not any(caracter.islower() for caracter in password):
            raise ValidationError(
                'La contrase\u00f1a debe contener al menos una letra min\u00fascula.',
                code='sin_minuscula')
        if not any(caracter.isdigit() for caracter in password):
            raise ValidationError(
                'La contrase\u00f1a debe contener al menos un n\u00famero.',
                code='sin_numero')

    def get_help_text(self):
        return 'M\u00ednimo 8 caracteres con may\u00fasculas, min\u00fasculas y n\u00fameros.'
