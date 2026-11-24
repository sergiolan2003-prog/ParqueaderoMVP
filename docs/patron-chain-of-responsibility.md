# Cadena de responsabilidad para validar ingresos

## Problema que resuelve

El ingreso de un vehículo requiere ejecutar varias validaciones en orden y
detenerse ante el primer rechazo. La cadena permite agregar, quitar o
reordenar validadores sin introducir sus reglas en el caso de uso ni modificar
los validadores existentes.

## Ubicación en el código

- `backend/app/modules/accesos/domain/validaciones_ingreso.py` define
  `ContextoValidacionIngreso`, el protocolo `ValidadorIngreso`, la cadena
  `CadenaValidacionIngreso` y los validadores concretos.
- `backend/app/modules/accesos/application/entry.py` construye la cadena por
  defecto y la ejecuta durante el ingreso.
- `backend/app/modules/accesos/domain/exceptions.py` contiene los rechazos del
  dominio.
- `backend/app/modules/accesos/api/v1/router.py` traduce esos rechazos a
  respuestas HTTP.

La cadena predeterminada ejecuta:

1. `ValidadorConfianza`: rechaza la lectura si su confianza es menor al umbral
   configurado y no es una lectura manual.
2. `ValidadorCupo`: no rechaza ingresos; la validación real corresponde a
   HU-13.
3. `ValidadorPaseVigente`: recibe el estado del pase en el contexto, pero no
   rechaza ingresos en HU-06.

## Cómo agregar un validador

1. Implementa `ValidadorIngreso` en el dominio. Su método `validar` recibe un
   `ContextoValidacionIngreso`; si la regla rechaza el ingreso, lanza una
   excepción de dominio.
2. Agrega pruebas unitarias para el resultado de la regla y para su posición
   en la cadena.
3. Registra una instancia del validador en la tupla que construye
   `RegistrarEntradaUseCase`, en el orden de negocio requerido.

La cadena se detiene automáticamente cuando un validador lanza una excepción.
Para quitar una regla, retira su instancia de esa tupla; los demás validadores
no necesitan cambios.
