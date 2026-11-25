# Sistema de Parqueadero con Reconocimiento de Placas: contexto del problema

## 1. Descripción general

Un parqueadero quiere automatizar el ingreso y la salida de vehículos. Cuando un vehículo llega, una **cámara lee la placa** (reconocimiento automático de placas, LPR por sus siglas en inglés), el sistema identifica el tipo de vehículo y, según las reglas del negocio, **genera un cobro** o deja pasar al vehículo sin costo. La barrera de salida solo abre si el vehículo no tiene cobros pendientes.

Hoy el proceso es manual: tiquete de papel, digitación de placas y cálculo del valor a mano. Esto produce filas en la entrada, errores de cobro, tiquetes perdidos y poca trazabilidad.

## 2. Objetivo

Construir un sistema que:

1. Registre cada ingreso y salida a partir de la lectura de la placa, sin intervención humana en el caso normal.
2. Aplique las reglas de tarifa de forma automática y consistente.
3. Permita pagar por varios medios y deje pasar al vehículo con pago vigente sin cobrarle de nuevo.
4. Siga operando aunque falle internet o la cámara.
5. Pueda crecer de un parqueadero (una sede) a varios sin rediseñarse.

## 3. Actores

| Actor | Rol en el sistema |
|---|---|
| **Conductor** | Ingresa, sale y paga (en caja, kiosko o app). |
| **Operador / cajero** | Recibe pagos en efectivo, corrige lecturas de placa dudosas, abre la barrera manualmente en una contingencia. |
| **Administrador** | Configura tarifas, franjas horarias y cupos. Consulta reportes y auditoría. |
| **Sistema LPR (cámara y software)** | Detecta el vehículo, lee la placa y reporta la confianza de la lectura. |
| **Pasarela de pagos** (externo) | Procesa pagos con tarjeta, PSE, Nequi, etc. |
| **Proveedor de facturación electrónica** (externo) | Emite la factura o el documento soporte ante la DIAN. |

## 4. Flujo general

```
Llega el vehículo → la cámara lee la placa → se identifica el tipo (moto / carro)
   → ¿es moto?                  → registra el ingreso, sin cobro, abre la barrera
   → ¿carro con pago vigente?   → registra el reingreso, sin cobro, abre la barrera
   → ¿carro sin pago vigente?   → genera el cobro (diurno o nocturno), abre la barrera
… permanencia …
El conductor paga → el pago queda vigente hasta el fin del día operativo
Llega a la salida → la cámara lee la placa → ¿cobro pagado o sin cobro? → abre la barrera
```

## 5. Reglas de negocio

| ID | Regla | Detalle |
|---|---|---|
| **RN-01** | **Las motos no pagan.** | Las motos se registran igual (por seguridad, cupos y trazabilidad), pero no generan cobro. Se recomienda modelarlo como una tarifa de $0 configurable y no como una excepción en el código, para que si mañana el negocio decide cobrarles solo haya que cambiar la configuración. |
| **RN-02** | **Tarifa diurna y nocturna.** | Hay dos franjas, cada una con su tarifa. **La tarifa nocturna siempre es menor que la diurna.** El sistema debe impedir que un administrador guarde una configuración que lo incumpla. |
| **RN-03** | **Un pago cubre todo el día vigente.** | Una vez pagado, el vehículo puede salir y volver a entrar cuantas veces quiera durante el día vigente sin generar cobros nuevos. |
| **RN-04** | **Un solo cobro por vehículo por día.** | Consecuencia de RN-03: nunca puede haber dos cobros para la misma placa en el mismo día operativo. Esto se garantiza con una restricción única en la base de datos (`placa + sede + día operativo`), no solo con lógica de aplicación. |
| **RN-05** | **La tarifa la define la franja del primer ingreso del día.** | Un carro que entra por primera vez a las 08:00 paga tarifa diurna. Uno que entra por primera vez a las 19:00 paga tarifa nocturna. |
| **RN-06** | **No hay salida con deuda.** | La barrera de salida no abre si el vehículo tiene un cobro pendiente. |
| **RN-07** | **Las tarifas se versionan.** | Un cambio de tarifa aplica solo a los cobros nuevos. Cada cobro guarda la tarifa con la que se calculó. |

## 6. Supuestos adoptados para cerrar ambigüedades

Las reglas del enunciado dejan huecos que el software tiene que resolver de alguna forma. Estos son los supuestos que adopta la propuesta; **deben validarse con el cliente** (ver la sección 10).

| ID | Supuesto | Por qué |
|---|---|---|
| **S-01** | **Franjas:** diurna de 06:00 a 17:59 y nocturna de 18:00 a 05:59, configurables. | Es un valor típico. Se deja configurable porque cada sede puede tener horarios distintos. |
| **S-02** | **"Día vigente" = día operativo de 06:00 a 05:59 del día siguiente**, no el día calendario (00:00 a 23:59). | Con el día calendario, un carro que entra a las 23:00 y sale a la 01:00 cruzaría la medianoche y quedaría en dos días distintos. Además se abre un **hueco tarifario**: entrar a las 05:50, pagar la tarifa nocturna (más barata) y quedarse todo el día. Si el día empieza a las 06:00, la noche queda completa dentro de un mismo día y el hueco se cierra. |
| **S-03** | **Cobro por pase diario, no por tiempo.** El valor es fijo según la franja (RN-05), no depende de cuántas horas se quede. | Es el modelo que mejor encaja con RN-03 ("una vez pago puede ingresar todo el día"). El cobro por minutos u horas es una alternativa (ver P-01). |
| **S-04** | **El cobro se genera al ingreso y se paga antes de salir.** | La salida solo verifica el estado del cobro, lo que la mantiene rápida. |
| **S-05** | **Si el vehículo sigue adentro cuando empieza un nuevo día operativo (06:00), se genera el cobro diurno del día nuevo**, que debe pagar antes de salir. | Evita que un pago cubra estadías de varios días. |
| **S-06** | **El pago vale solo en la sede donde se hizo.** | Es lo más simple. Que valga en todas las sedes es una decisión comercial (ver P-04). |
| **S-07** | **La zona horaria es la de la sede** (Colombia: `America/Bogota`, UTC-5, sin horario de verano). | Todas las reglas de franja y de día dependen de la hora local. Internamente se guarda en UTC y se convierte. |

### Escenarios de ejemplo (con los supuestos anteriores)

| # | Escenario | Resultado |
|---|---|---|
| 1 | Moto entra a las 10:00 y sale a las 14:00 | Se registran el ingreso y la salida. Sin cobro. |
| 2 | Carro entra por primera vez a las 08:00 | Cobro **diurno** pendiente. Debe pagar antes de salir. |
| 3 | El mismo carro pagó, sale a las 12:00 y vuelve a las 15:00 | Reingreso **sin cobro** (RN-03). |
| 4 | El mismo carro vuelve a las 22:00 | Sin cobro: sigue dentro del mismo día operativo. |
| 5 | Carro entra por primera vez a las 19:00 | Cobro **nocturno** (menor que el diurno). |
| 6 | Carro entra a las 23:00 y sale a la 01:00 | Un solo cobro nocturno: es el mismo día operativo (S-02). |
| 7 | Carro entra a las 05:50, paga la nocturna y se queda hasta las 09:00 | Al pasar las 06:00 empieza un día nuevo: se genera el cobro **diurno** del nuevo día (S-05). |
| 8 | Carro pagó el lunes y vuelve el martes a las 07:00 | Cobro **diurno** nuevo: el pago del lunes ya venció. |
| 9 | La cámara no logra leer la placa | El operador valida o digita la placa. El evento queda marcado como "lectura manual". |

## 7. Consideraciones y casos borde

### 7.1 Lectura de placas (LPR)

- **Ninguna lectura es 100 % confiable.** Hay placas sucias, dobladas, con reflejos, de noche, con lluvia, con portaplacas que tapan caracteres. Cada lectura trae un **nivel de confianza**. Por debajo de un umbral, el sistema reintenta con otros fotogramas y, si no mejora, pide validación del operador.
- **Confusiones típicas del OCR:** `0/O`, `1/I`, `8/B`, `5/S`, `2/Z`. Conviene normalizar contra el formato de placa esperado (por ejemplo, en una placa de carro colombiana las tres últimas posiciones son dígitos).
- **Vehículos sin placa o con placa no estándar:** placas provisionales, diplomáticas, extranjeras, en trámite. Para estos casos debe existir un flujo manual.
- **Evidencia:** se guarda la foto de cada lectura para resolver reclamos ("yo no entré a esa hora").
- **Placa clonada o salida no registrada:** si una placa intenta entrar y el sistema la tiene adentro, se genera una alerta (anti-passback) y el operador decide.

### 7.2 Clasificación moto o carro

- En Colombia el formato de placa ayuda: los carros usan `AAA123` y las motos `AAA12A` (o `AAA12` en placas antiguas). Pero **no basta por sí solo**: hay motocarros, cuatrimotos y formatos especiales.
- Opciones: (a) carriles separados para motos, (b) clasificación por formato de placa, (c) clasificación por imagen (el mismo modelo de visión detecta el tipo de vehículo), (d) una combinación. **Recomendado:** formato de placa más clasificación por imagen y, si no coinciden, decide el operador.
- Como las motos no pagan, **un carro mal clasificado como moto es una pérdida directa de ingresos**. Esa discrepancia debe alertarse y auditarse.

### 7.3 Tarifas y franjas

- Las franjas, las tarifas y el inicio del día operativo son **configuración**, no código.
- Validación obligatoria: `tarifa_nocturna < tarifa_diurna` (RN-02).
- Versionado de tarifas con fechas de vigencia (RN-07). Los cobros ya generados no cambian.
- A futuro podrían aparecer más tipos de vehículo (camionetas, bicicletas, vehículos eléctricos) o tarifas especiales (mensualidades, convenios). El modelo de tarifas debe admitir `tipo_vehiculo × franja` sin cambios de código.

### 7.4 Vigencia del pago

- El pago crea un **pase vigente** hasta el fin del día operativo. El carril lo consulta en cada reingreso.
- El pase vigente debe estar disponible **localmente en la sede** para que el reingreso funcione sin internet.
- El cambio de día (06:00) vence todos los pases del día anterior.

### 7.5 Pagos

- **Medios:** efectivo (caja), tarjeta y QR en kiosko, PSE/Nequi/Daviplata desde el celular.
- **Idempotencia:** un pago confirmado dos veces por la pasarela (reintentos o webhooks duplicados) no debe registrarse dos veces.
- **Conciliación:** reporte diario de lo cobrado en el sistema contra lo recibido en la pasarela y en la caja.
- **Facturación electrónica:** en Colombia, la venta debe soportarse con factura electrónica o documento equivalente ante la DIAN, normalmente a través de un proveedor tecnológico.
- **Anulaciones y cortesías:** solo las puede hacer el operador o el administrador, con motivo obligatorio y registro en auditoría.

### 7.6 Operación y fallas

| Falla | Comportamiento esperado |
|---|---|
| Se cae internet | El gateway de la sede decide con su caché local. Los eventos quedan en cola y se sincronizan cuando vuelve la conexión. Se puede pagar en efectivo en la caja local. |
| Falla la cámara | El operador digita la placa y la barrera se abre desde la consola. |
| Falla el gateway de la sede | La barrera pasa a modo manual (botón del operador) y se registra en contingencia. |
| Se va la energía | UPS para el gateway, la red y las barreras. Las barreras deben tener apertura manual. |
| Se llena el parqueadero | Antes de abrir se valida el cupo por tipo de vehículo y se muestra "LLENO" en pantalla. |

### 7.7 Seguridad y aspectos legales

- **Protección de datos (Ley 1581 de 2012, Habeas Data):** la placa y la foto del vehículo pueden asociarse a una persona. Se necesita un aviso de privacidad visible en la entrada, una política de retención de fotos (por ejemplo, 30 a 90 días) y control de acceso a esa información.
- **Estatuto del Consumidor (Ley 1480 de 2011):** el parqueadero debe entregar un comprobante del servicio y responde por la custodia del vehículo. El registro de ingreso y salida con foto sirve como evidencia.
- **Regulación local de tarifas:** algunas ciudades regulan cómo deben cobrar los parqueaderos (por ejemplo, por minuto). **Hay que verificarlo en el municipio** antes de fijar el modelo de cobro (S-03).
- **Seguridad técnica:** comunicación cifrada entre la sede y la nube (TLS o VPN), autenticación de cada dispositivo, roles (operador, administrador) y auditoría de las acciones manuales (aperturas manuales, anulaciones, cambios de tarifa).

## 8. Requisitos no funcionales

| Atributo | Meta sugerida |
|---|---|
| **Tiempo de respuesta en carril** | Menos de 3 s desde la detección del vehículo hasta la apertura de la barrera. |
| **Precisión LPR** | 95 % o más de lecturas correctas de día y 90 % o más de noche. Lo demás pasa a validación manual. |
| **Disponibilidad del carril** | 99,9 %. El carril debe seguir operando sin internet (modo degradado). |
| **Escalabilidad** | Agregar un carril o una sede sin cambiar el código: solo instalar hardware y registrarlo. |
| **Consistencia** | Cero cobros duplicados por vehículo y día (RN-04). |
| **Trazabilidad** | Todo evento (ingreso, salida, cobro, pago, acción manual) con fecha, hora, sede, carril, usuario y foto cuando aplique. |
| **Seguridad** | Cifrado en tránsito y en reposo, control de acceso por roles. |

## 9. Alcance

**Dentro del alcance:**

- Ingreso y salida automáticos por placa.
- Clasificación moto o carro.
- Cobro con tarifa diurna o nocturna, y pase vigente durante el día.
- Pago en caja, kiosko y app (o enlace de pago).
- Operación sin conexión en la sede.
- Portal de administración: tarifas, franjas, cupos, reportes y auditoría.

**Fuera del alcance (por ahora):**

- Mensualidades y abonados.
- Reservas de cupo.
- Guía de cupos libres dentro del parqueadero (sensores por cupo).
- Integración con sistemas de tránsito o con la policía.

## 10. Preguntas abiertas para el cliente

| ID | Pregunta | Supuesto actual |
|---|---|---|
| P-01 | ¿El cobro es un valor fijo por día (pase) o depende del tiempo de permanencia? | Pase diario (S-03). |
| P-02 | ¿"Día vigente" es el día calendario o un día operativo (06:00 a 05:59)? | Día operativo (S-02). |
| P-03 | ¿Cuáles son exactamente las franjas diurna y nocturna? | 06:00–17:59 y 18:00–05:59 (S-01). |
| P-04 | Si hay varias sedes, ¿el pago vale en todas? | Solo en la sede del pago (S-06). |
| P-05 | Si un carro paga la tarifa nocturna y se queda hasta el día siguiente, ¿qué se le cobra? | El cobro diurno del día nuevo (S-05). |
| P-06 | ¿Se cobra al entrar (prepago) o al salir? | Se genera al entrar y se paga antes de salir (S-04). |
| P-07 | ¿Hay cupos separados para motos y carros? | Sí, cupos por tipo de vehículo. |
| P-08 | ¿Existen otros tipos de vehículo o convenios con tarifa especial? | No por ahora; el modelo lo soporta por configuración. |
| P-09 | ¿Cuánto tiempo deben guardarse las fotos de las placas? | 30 días. |

## 11. Glosario

| Término | Significado |
|---|---|
| **LPR / ANPR** | *License / Automatic Number Plate Recognition*: reconocimiento automático de placas por cámara. |
| **Franja** | Rango horario con una tarifa asociada (diurna o nocturna). |
| **Día operativo** | Periodo de 24 h en el que vale un pago. En esta propuesta va de 06:00 a 05:59. |
| **Pase vigente** | Estado de un vehículo que pagó y puede reingresar sin cobro hasta el fin del día operativo. |
| **Edge / gateway de sede** | Computador local en el parqueadero que procesa las lecturas y controla las barreras sin depender de la nube. |
| **Anti-passback** | Control que impide registrar dos ingresos seguidos de la misma placa sin una salida entre ellos. |
| **Idempotencia** | Propiedad de una operación que, repetida varias veces, produce el mismo resultado que si se hiciera una sola vez. |
