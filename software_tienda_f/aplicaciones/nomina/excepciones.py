class NominaError(Exception):
    def __init__(self, mensaje):
        self.mensaje = mensaje
        super().__init__(mensaje)


class NominaYaCalculadaError(NominaError):
    def __init__(self, periodo, estado):
        super().__init__(
            'La nómina de {0} ya fue calculada y está {1}. '
            'Solo se puede recalcular si el Auxiliar Administrativo la rechaza.'.format(
                periodo, estado)
        )


class SinEmpleadosActivosError(NominaError):
    def __init__(self, periodo):
        super().__init__('No hay empleados activos para calcular la nómina de {0}.'.format(periodo))


class PreNominaNoPendienteError(NominaError):
    def __init__(self, estado):
        super().__init__('Esta pre-nómina ya fue {0}; no se puede volver a procesar.'.format(estado))


class MotivoRechazoRequeridoError(NominaError):
    def __init__(self):
        super().__init__('Debes escribir el motivo del rechazo de la pre-nómina.')
