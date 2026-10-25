(function () {
    const reglas = {
        numeros: /^[0-9]*$/,
        decimal: /^[0-9]*[.,]?[0-9]{0,2}$/,
        letras: /^[A-Za-zÁÉÍÓÚáéíóúÑñÜü ]*$/,
        usuario: /^[A-Za-z0-9._-]*$/,
        texto: /^[A-Za-zÁÉÍÓÚáéíóúÑñÜü0-9 .,;:()¿?¡!/#-]*$/
    };
    const avisos = {
        numeros: 'Este campo solo admite números.',
        decimal: 'Este campo solo admite números con hasta 2 decimales.',
        letras: 'Este campo solo admite letras y espacios.',
        usuario: 'Usa solo letras, números, punto, guion o guion bajo, sin espacios.',
        texto: 'Ese carácter no está permitido en este campo.'
    };

    function limpiar(tipo, valor) {
        if (tipo === 'decimal') {
            let salida = valor.replace(/[^0-9.,]/g, '');
            const separador = salida.search(/[.,]/);
            if (separador !== -1) {
                salida = salida.slice(0, separador + 1) +
                    salida.slice(separador + 1).replace(/[.,]/g, '').slice(0, 2);
            }
            return salida;
        }
        const permitido = {
            numeros: /[^0-9]/g,
            letras: /[^A-Za-zÁÉÍÓÚáéíóúÑñÜü ]/g,
            usuario: /[^A-Za-z0-9._-]/g,
            texto: /[^A-Za-zÁÉÍÓÚáéíóúÑñÜü0-9 .,;:()¿?¡!/#-]/g
        }[tipo];
        return permitido ? valor.replace(permitido, '') : valor;
    }

    function aviso(campo, tipo) {
        campo.classList.add('campo-bloqueado');
        let mensaje = campo.nextElementSibling;
        if (!mensaje || !mensaje.classList.contains('aviso-campo')) {
            mensaje = document.createElement('small');
            mensaje.className = 'aviso-campo';
            mensaje.setAttribute('aria-live', 'polite');
            campo.insertAdjacentElement('afterend', mensaje);
        }
        mensaje.textContent = avisos[tipo];
        window.clearTimeout(campo._avisoTimer);
        campo._avisoTimer = window.setTimeout(function () {
            campo.classList.remove('campo-bloqueado');
            mensaje.textContent = '';
        }, 600);
    }

    document.querySelectorAll('input[data-solo], textarea[data-solo]').forEach(function (campo) {
        const tipo = campo.getAttribute('data-solo');
        if (!reglas[tipo]) return;

        campo.addEventListener('beforeinput', function (evento) {
            if (evento.inputType && evento.inputType.indexOf('delete') === 0) return;
            if (evento.inputType === 'insertLineBreak' || evento.inputType === 'insertParagraph') return;
            const datos = evento.dataTransfer ? evento.dataTransfer.getData('text') : evento.data;
            if (datos === null || datos === undefined) return;
            const inicio = campo.selectionStart === null ? campo.value.length : campo.selectionStart;
            const fin = campo.selectionEnd === null ? inicio : campo.selectionEnd;
            const valor = campo.value.slice(0, inicio) + datos + campo.value.slice(fin);
            const max = campo.maxLength;
            if (!reglas[tipo].test(valor) || (max >= 0 && valor.length > max)) {
                evento.preventDefault();
                aviso(campo, tipo);
            }
        });

        campo.addEventListener('input', function () {
            const valor = limpiar(tipo, campo.value);
            const limitado = campo.maxLength >= 0 ? valor.slice(0, campo.maxLength) : valor;
            if (limitado !== campo.value) {
                campo.value = limitado;
                aviso(campo, tipo);
            }
        });
    });
}());
