import re

from django.core.exceptions import ValidationError
from django.utils import timezone


_LETRAS = re.compile(r'^[A-Za-zÁÉÍÓÚáéíóúÑñÜü ]+$')
_USUARIO = re.compile(r'^[A-Za-z0-9._-]+$')
_TEXTO = re.compile(r'^[A-Za-zÁÉÍÓÚáéíóúÑñÜü0-9 .,;:()¿?¡!/#-]+$')
_DIGITOS = re.compile(r'^[0-9]+$')


def validar_solo_letras(valor, campo='Este campo'):
    if not _LETRAS.fullmatch(str(valor)):
        raise ValidationError(
            f'{campo} solo puede contener letras y espacios.', code='solo_letras')


def validar_usuario(valor):
    if not _USUARIO.fullmatch(str(valor)):
        raise ValidationError(
            'El nombre de usuario solo puede tener letras sin tilde, números, '
            'punto, guion y guion bajo, sin espacios.', code='usuario_invalido')


def validar_texto_seguro(valor, campo='Este campo'):
    if not _TEXTO.fullmatch(str(valor)):
        raise ValidationError(
            f'{campo} contiene caracteres no permitidos.', code='texto_invalido')


def validar_solo_digitos(valor, campo='Este campo'):
    if not _DIGITOS.fullmatch(str(valor)):
        raise ValidationError(
            f'{campo} solo puede contener números.', code='solo_digitos')


def validar_fecha_no_futura(fecha, campo='La fecha'):
    if fecha > timezone.localdate():
        raise ValidationError(
            f'{campo} no puede ser posterior a hoy.', code='fecha_futura')


def normalizar_espacios(valor):
    return ' '.join(valor.strip().split())
