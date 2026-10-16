# Tasks

Primera fase simplificada aprobada por el usuario e implementada; verificación y revisión independiente completadas.

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
- Verificación: 76 pruebas unitarias iniciales, 50 de integración PostgreSQL y un smoke real PostgreSQL/RabbitMQ correctos. Tras corregir el único hallazgo de revisión (JSON excesivamente anidado), las 15 pruebas de quotations, incluida la nueva regresión, pasan; Pyright devuelve cero errores y cero warnings. Revisión independiente sin hallazgos pendientes y validación estricta de OpenSpec correcta.
- API y worker verificados como procesos separados: POST devuelve 202 y GET alcanza COMPLETED con las tres ofertas; apagado limpio de ambos procesos.
- Sincronización y archivado quedan fuera de esta revisión.
