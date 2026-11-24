# Día operativo y franjas

`OperatingDayService` centraliza la decisión del día operativo y la franja. El
servicio recibe un `Clock` y una `OperatingDayConfiguration`; sus métodos aceptan
un instante explícito o, si se omite, consultan el reloj inyectado.

Los instantes deben incluir zona horaria. El servicio los convierte a la zona
configurada (por defecto, `America/Bogota`) antes de aplicar las reglas y
conserva los instantes como `datetime` conscientes de zona, normalmente en UTC.
El día operativo comienza a la hora configurada (06:00 por defecto): desde esa
hora hasta las 05:59 del día siguiente pertenece al mismo día operativo.
`DIURNA` cubre de 06:00 a 18:00 (fin exclusivo) y `NOCTURNA` de 18:00 a 06:00
(fin exclusivo), según los límites configurados.

La configuración se construye en un solo lugar desde `Settings`, usando las
variables descritas en `.env.example`. `OperatingDayConfiguration` valida que
las franjas cubran las 24 horas sin huecos ni solapes, que sus códigos no se
repitan y que sean exactamente `DIURNA` y `NOCTURNA`. La misma configuración
se construye desde `Settings`, que también valida
`LPR_CONFIDENCE_THRESHOLD` entre 0 y 1; su uso se reserva para HU-12.

`SystemClock` proporciona la hora real en UTC. `FixedClock` permite fijar un
instante para pruebas sin depender del reloj del sistema.

Ejecuta las pruebas desde `backend/` con:

```powershell
pytest -v tests/unit/test_operating_day.py
```

`POST /accesos/entrada` usa el instante con zona horaria del evento del gateway
para resolver tanto el día operativo como la franja. El cobro se aplica una
sola vez por placa, sede y día operativo; un pase vigente o un cobro existente
evitan la creación de otro. La tarifa y su identificador de versión quedan
persistidos en el cobro.

Para pruebas manuales, usa el backend directamente en
`http://localhost:8000` y Swagger en `http://localhost:8000/docs`. Nginx aún
solo reenvía `/health`; las rutas de acceso y tarifas no están conectadas al
frontend.
