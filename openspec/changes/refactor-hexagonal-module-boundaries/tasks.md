# Tasks

Implementación aprobada por el usuario el 2026-10-15 con «adelante, sí», después de presentar el plan. Marcar las tareas solo tras verificarlas; specs se omite porque los contratos funcionales no cambian.

## 1. Reorganización y contratos internos

- [x] 1.1 Registrar HEAD y capturar OpenAPI completo y DDL/índices antes de editar código. Localizar validadores y DeliveryConflictError/ReturnConflictError en sus entidades, eliminar domain/validation.py; mover servicios a application/deliveries.py, returns.py y lockers.py con errores NotFound específicos y reloj explícito para Delivery/Return. Eliminar application/clock.py y errors.py, suministrar utc_now desde main y actualizar consumidores/imports/README. Adaptar test_domain, test_application y test_main: mensajes/normalización/orden intactos, excepciones exactas por flujo, reloj fijo y cobertura del reloj UTC real en composición; ejecutar estas pruebas antes de cerrar la tarea.
- [x] 1.2 Mover el comparador a application/shipping_quotes.py como ShippingQuoteService y trasladar allí ProviderResult/ProviderStatus/ProviderErrorCode según el diseño, reutilizando QuoteOffers sin imports privados ni dominio hacia aplicación. Actualizar test_shipping_quotes, consumidores y ejemplo README; verificar invariantes, ofertas mal formadas, proveedores abiertos, resultados parciales, timeout y cancelación con la suite unitaria del comparador.
- [x] 1.3 Mover rutas/esquemas HTTP a deliveries/returns/lockers con __init__.py, conservar los helpers en sus ubicaciones acordadas y añadir http/routes.py únicamente como agregador. Adaptar main, todas las importaciones HTTP unitarias/de integración y README; retirar los seis módulos planos antiguos. Verificar tests HTTP/lifespan, 422/404/409 y sus cuerpos, instancias por aplicación y OpenAPI idéntico al baseline.

## 2. Verificación integral y revisión

- [x] 2.1 Desde backend ejecutar `uv run --extra dev pyright --project .. --warnings` con 0 errores/0 advertencias y configuración intacta, unitarias sin BD y suite completa con TEST_DATABASE_URL PostgreSQL mediante los comandos del diseño, sin skips. Preservar los escenarios de las 95 pruebas de referencia, comparar OpenAPI y DDL/índices completos, comprobar migraciones 0001–0004 intactas y ausencia de imports/nombres retirados en código y documentación vigente. Validar `openspec validate refactor-hexagonal-module-boundaries --strict`. Obtener revisión independiente sdd_reviewer, resolver hallazgos y repetir verificaciones afectadas antes de marcar implementación completa.

## Evidencia de verificación (2026-10-15)

- Base capturada antes de editar código: `02b932c03ee188c8cf3d60447a680a1c1351480b`. OpenAPI completo (10 rutas), DDL/índices de las cinco tablas y versiones de dependencias idénticos tras el refactor. Sin cambios en persistencia, migraciones 0001–0004, dependencias o configuración de Pyright.
- Desde `backend/`, `UV_CACHE_DIR=/tmp/uv-cache uv run --offline --extra dev pyright --project .. --warnings`: **0 errores y 0 advertencias**, comprobado tras los últimos cambios y ejecutado también por el revisor independiente.
- Desde `backend/`, sin `TEST_DATABASE_URL`, `UV_CACHE_DIR=/tmp/uv-cache uv run --offline --extra dev python -m unittest discover -s tests/unit -t . -v`: **52 pruebas aprobadas** en 2,904 s.
- Desde `backend/`, con `TEST_DATABASE_URL` apuntando a PostgreSQL 17.11 y esquemas aislados, `UV_CACHE_DIR=/tmp/uv-cache uv run --offline --extra dev python -m unittest discover -s tests -t . -v -f`: **95 pruebas aprobadas** en 21,318 s, sin omisiones. Siete comprobaciones Alembic indicaron `No new upgrade operations detected.`.
- Se conservan los 95 escenarios. La prueba del reloj por defecto se traslada de aplicación a composición: ambas recepciones HTTP usan la hora UTC real proporcionada por `main.py`. Los tests de errores comprueban la clase específica de cada flujo.
- Ejemplo literal del README ejecutado con `ShippingQuoteService`: ofertas de 330/830/520 céntimos para economy/express/standard, con sus plazos originales.
- Sin imports/nombres retirados en código o README; dependencias acíclicas y sin imports del dominio hacia aplicación ni reutilización externa de helpers privados. `git diff --check` y validación OpenSpec estricta correctos.
- Revisión independiente de `sdd_reviewer`: sin hallazgos pendientes.

Implementación completa. El cambio permanece sin sincronizar ni archivar.
