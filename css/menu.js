document.querySelectorAll('.modulo-cabecera').forEach(function(boton) {
    boton.addEventListener('click', function() {
        const modulo = this.closest('.modulo');

        document.querySelectorAll('.modulo').forEach(function(otroModulo) {
            if (otroModulo !== modulo) {
                otroModulo.classList.remove('abierto');
            }
        });

        modulo.classList.toggle('abierto');
    });
});

document.querySelectorAll('.modulo.activo').forEach(function(modulo) {
    modulo.classList.add('abierto');
});