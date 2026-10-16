# Tasks

## 1. Reorganización y consumidores

- [x] 1.1 Reorganizar el código de producción conforme al mapa de `design.md`: paquetes de aplicación, modelos/errores de cotizaciones, todos los puertos en su área consumidora y `ShippingQuoteComparator`; actualizar composición y adaptadores y retirar módulos sustituidos sin wrappers. Verificar por diff e imports que las firmas y cuerpos conservan su comportamiento, los `__init__.py` están vacíos, dominio no depende de aplicación y los modelos no dependen del comparador.
- [x] 1.2 Actualizar imports y destinos de parches en las pruebas, y el árbol, ejemplos y explicación de puertos en README. Verificar que no quedan referencias ejecutables a rutas retiradas y ejecutar desde `backend/` `env -u TEST_DATABASE_URL -u TEST_RABBITMQ_URL uv run --extra dev python -m unittest discover -s tests/unit -t . -v`, conservando las 77 pruebas actuales sin omisiones y los dobles deterministas existentes.

## 2. Verificación integrada y revisión

- [x] 2.1 Comparar OpenAPI y DDL/metadatos con la captura previa de `10ee425`; confirmar migraciones `0001`–`0005` intactas. Con URLs de prueba explícitas, ejecutar desde `backend/` `uv run --extra dev python -m unittest discover -s tests/integration -t . -v -f` (50 pruebas) y `uv run --extra dev python -m unittest discover -s tests/messaging -t . -v -f` (1 prueba), y `uv run --extra dev pyright --project .. --warnings` con cero errores y cero advertencias. Registrar resultados reales, igualdad de contratos y ausencia de cambios en colas, reglas y perfiles.
- [x] 2.2 Obtener revisión independiente de fronteras hexagonales, regresiones y evidencia; resolver hallazgos dentro del alcance y repetir las comprobaciones afectadas, incluido Pyright tras correcciones. Validar `openspec validate refactor-application-feature-boundaries --strict` y cerrar las tareas solo con evidencia satisfactoria, manteniendo intacto `add-asynchronous-shipping-quotations` y sin sincronizar ni archivar.

## Coordination

El coordinador ha capturado la base de OpenAPI y los metadatos/DDL de ocho tablas antes de la implementación. Un builder es propietario de producción; otro, de pruebas y README. El coordinador integra, verifica la comparación y mantiene este seguimiento como único escritor tras el traspaso. Las cuatro tareas se completaron tras la verificación y la revisión independiente.


## Verification evidence

- Base comparada: `10ee425`. Las 26 definiciones trasladadas conservan sus firmas y cuerpos AST, normalizando únicamente `ShippingQuoteService` a `ShippingQuoteComparator`; los consumidores de producción conservan su lógica.
- OpenAPI completo idéntico (12 rutas) y DDL/índices PostgreSQL idénticos (8 tablas) frente a la captura previa. Migraciones `0001`–`0005`, dependencias, configuración de Pyright y cambio asíncrono anterior intactos.
- Las 77 pruebas unitarias pasan sin configuración de servicios (3.439 s); las 50 de PostgreSQL pasan (27.671 s); el smoke PostgreSQL/RabbitMQ pasa (1 prueba, 0.469 s). Sin omisiones. Logs: `/tmp/refactor-feature-unit.log`, `/tmp/refactor-feature-postgresql.log`, `/tmp/refactor-feature-messaging.log`.
- `uv run --extra dev pyright --project .. --warnings` ejecutado desde backend: cero errores y cero advertencias, confirmado también por el revisor independiente.
- Revisión independiente sin hallazgos: seis puertos en aplicación, modelos independientes de ejecutores, paquetes sin efectos laterales, sin ciclos ni imports obsoletos o dependencias de dominio hacia aplicación.
- `openspec validate refactor-application-feature-boundaries --strict` y `git diff --check` correctos. Implementación completa; sincronización y archivado no realizados.
