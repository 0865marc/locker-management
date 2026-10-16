# Tasks

La primera fase simplificada está implementada y verificada; las tareas 1–5 y su evidencia se conservan como historial de esa versión. La revisión de proveedores autónomos aprobada después por el usuario también está implementada y verificada en las tareas 6.1–6.3, con evidencia propia.

## 1. Contratos y simuladores

- [x] 1.1 Añadir modelos/puertos de solicitud persistente en aplicación y configuración de simuladores solo en el worker; probar validación, éxito/error/no respuesta, timeout sin retry y tarifas actuales con azar/esperas controlados; documentar el uso directo determinista.

## 2. PostgreSQL

- [x] 2.1 Implementar repositorio de solicitudes/resultados/ofertas y lote final atómico; verificar con PostgreSQL aislado estados, errores de proceso, resultados mixtos, rollback y lectura desde otra instancia, sin metadatos de recuperación.
- [x] 2.2 Añadir migración 0005 e importar metadata, preservando 0001–0004; probar upgrade poblado, metadata y downgrade estándar permitido/rechazado; actualizar la documentación de migraciones.

## 3. Encolado y ejecución

- [x] 3.1 Implementar submit/get y HTTP en `adapters/http/quotations/`, router agregado y `main.py`; probar publicación única, 202 tras confirmación, 503/PUBLISH_ERROR, validación y consulta persistente; documentar POST/GET.
- [x] 3.2 Añadir adaptador RabbitMQ y `worker.py` secuencial con ack temprano y llamada única a compare; probar orden ack/ejecución, resultados por proveedor y ausencia de requeue mediante unidades y un smoke aislado PostgreSQL/RabbitMQ; documentar el límite ante caída del proceso.

## 4. Runtime

- [x] 4.1 Incorporar aio-pika y lockfile, empaquetado/Docker del worker, Compose con broker y un worker, configuración de conexiones y simulación, y Pyright estricto para el nuevo entrypoint; verificar instalación/configuración y cleanup con pruebas de composición; documentar arranque y variables.

## 5. Verificación y revisión

- [x] 5.1 Ejecutar unidades sin servicios, integración PostgreSQL, smoke de mensajería y las regresiones aplicables; ejecutar `uv run --extra dev pyright --project .. --warnings` con cero errores/warnings y registrar la evidencia real, corrigiendo causas sin relajar reglas.
- [x] 5.2 Validar `openspec validate add-asynchronous-shipping-quotations --strict` y obtener revisión independiente de `sdd_reviewer` sobre el flujo simple, arquitectura y evidencia; corregir hallazgos y repetir solo comprobaciones afectadas.

## 6. Revisión aprobada: proveedores autónomos

- [x] 6.1 Dar a cada simulador su perfil privado/inmutable aprobado y constructor sin argumentos, compartiendo el comportamiento; retirar configuración pública profile/rng/sleep y tipos SimulationProfile/SimulationRandom. Actualizar pruebas de simulación/comparación para controlar funciones privadas de azar/espera al ejecutar y verificar perfiles, umbrales, tarifas, error/timeout y cancelación; documentar en README que el uso directo es estocástico.
- [x] 6.2 Simplificar worker a instancias sin argumentos; eliminar simulation_profile() y las cuatro variables SHIPPING de simulación de worker/Compose/README. Actualizar pruebas de composición y sustituir el éxito del smoke por una oferta fija del doble; verificar que no quedan consumidores de configuración eliminada y que las variables antiguas no alteran los perfiles.
- [x] 6.3 Ejecutar unidades sin servicios y smoke PostgreSQL/RabbitMQ con sus URLs de prueba; exigir cero errores/warnings en `uv run --extra dev pyright --project .. --warnings`, validar OpenSpec strict y obtener revisión independiente de sdd_reviewer. Registrar evidencia nueva y corregir hallazgos sin modificar contratos de cola/API/persistencia ni añadir migraciones.

## Verification commands

Desde `backend/`, con TEST_DATABASE_URL y TEST_RABBITMQ_URL de prueba cuando la suite los requiera:

```bash
env -u TEST_DATABASE_URL -u TEST_RABBITMQ_URL uv run --extra dev python -m unittest discover -s tests/unit -t . -v
uv run --extra dev python -m unittest discover -s tests/integration -t . -v -f
uv run --extra dev python -m unittest discover -s tests/messaging -t . -v -f
uv run --extra dev pyright --project .. --warnings
```

No se añaden pruebas de recuperación, múltiples workers, leases o reinicios distribuidos. La suite completa documentada sigue disponible cuando se requiera comprobar el conjunto.

## Workflow follow-up

- Plan actualizado aprobado antes de implementar.
- Evidencia histórica anterior a la revisión de perfiles: 76 pruebas unitarias iniciales, 50 de integración PostgreSQL y un smoke real PostgreSQL/RabbitMQ correctos. Tras corregir el único hallazgo de revisión (JSON excesivamente anidado), las 15 pruebas de quotations, incluida la nueva regresión, pasaron; Pyright devolvió cero errores y cero warnings. Revisión independiente sin hallazgos pendientes y validación estricta de OpenSpec correcta para esa versión.
- Evidencia histórica: API y worker verificados como procesos separados; POST devolvió 202 y GET alcanzó COMPLETED con las tres ofertas, con apagado limpio de ambos procesos.
- Evidencia actual de perfiles autónomos: 77 pruebas unitarias sin variables de servicios correctas (3.296 s), un smoke PostgreSQL/RabbitMQ aislado correcto (0.372 s) y `uv run --extra dev pyright --project .. --warnings` con cero errores y cero warnings. Logs: `/tmp/quotation-fixed-unit.log` y `/tmp/quotation-fixed-messaging.log`. Búsqueda de consumidores confirma que worker/Compose/README ya no usan la configuración eliminada; las únicas menciones de las variables antiguas en código están en las regresiones que verifican su falta de efecto. No se repite integración PostgreSQL ajena al ajuste porque no cambian API, repositorios ni migraciones.
- Validación estricta de OpenSpec y configuración de Compose correctas. Revisión independiente sin hallazgos: 24 pruebas de simuladores/comparador y la regresión de composición del worker verificadas de nuevo; Pyright independiente con cero errores y cero warnings.
- Sincronización y archivado quedan fuera de esta revisión.
