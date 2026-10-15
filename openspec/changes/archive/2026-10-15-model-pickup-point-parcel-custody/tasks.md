# Tasks

Plan aprobado por el usuario. Las tareas se marcan completas únicamente tras implementar y verificar su comportamiento.

## 1. Modelo de custodia

- [x] 1.1 Actualizar `backend/domain/models.py` con los campos, estados y normalizaciones de ambas entidades, eliminando address/reason; verificar con pruebas de dominio los campos obligatorios, opcionales nulos, independencia y recepción en UTC.
- [x] 1.2 Implementar transiciones inmutables y sus invariantes; verificar recogida, devolución al transportista, entrega de Return, repetición, fechas anteriores a recepción y recogida con plazo vencido mediante pruebas con instantes explícitos.

## 2. Aplicación y puertos

- [x] 2.1 Ampliar `backend/domain/ports.py` con consulta por UUID y persistencia condicional de salida; adaptar `backend/application/use_cases.py` a creación enriquecida, reloj inyectable y las tres operaciones; verificar en `backend/tests/test_application.py` que ausencia, validación y conflicto no producen escrituras indebidas y que un conflicto de persistencia se propaga correctamente.
- [x] 2.2 Actualizar la explicación de entidades y responsabilidades en `README.md`, manteniendo la composición en `backend/main.py` solo si requiere cambios de inyección; verificar las pruebas de composición y ciclo de vida existentes con las nuevas firmas.

## 3. Persistencia y evolución de esquema

- [x] 3.1 Adaptar `backend/adapters/database/sqlmodel_repositories.py` a todos los campos, timestamps con zona, restricciones de estado y UPDATE condicional; mantener las pruebas SQLite de `backend/tests/test_repositories.py` y verificar round trip completo desde otra instancia, instantes UTC rehidratados, UUID duplicado, rollback y conservación de datos tras errores.
- [x] 3.2 Crear la revisión Alembic `0002` sin modificar `0001`, con comprobaciones y bloqueos previos a DDL en upgrade/downgrade; verificar en `backend/tests/test_migrations.py` upgrade limpio, recorrido vacío entre revisiones y rechazo íntegro ante filas en cualquiera de las dos tablas, incluidas columnas y revisión registrada.
- [x] 3.3 Añadir pruebas PostgreSQL con sesiones independientes para salidas Delivery incompatibles y handovers Return repetidos en concurrencia; verificar que exactamente una escritura confirma y que el estado y fecha ganadores permanecen intactos.
- [x] 3.4 Actualizar en `README.md` preparación, nuevo head, incompatibilidad legacy y procedimiento de rechazo seguro sin reset; verificar que los comandos de migración documentados coinciden con los escenarios probados y que el arranque de API sigue sin migrar el esquema.

## 4. Contrato HTTP

- [x] 4.1 Actualizar `backend/adapters/http/schemas.py` y `routes.py` con creación/listado completos y tres acciones explícitas; verificar en `backend/tests/test_http.py` respuestas `201/200/404/409/422`, rechazo de campos retirados o de sistema, UUID inválidos, fechas sin zona y cuerpos de acción distintos de ausencia o `{}`.
- [x] 4.2 Sustituir ejemplos curl de `README.md` por recepción y salida de paquetes; verificar con pruebas HTTP equivalentes que esos payloads son válidos y que ejemplos de estados y fechas reflejan respuestas del sistema.

## 5. Verificación integrada y revisión

- [x] 5.1 Ejecutar desde `backend/` `uv run --extra dev python -m unittest discover -s tests -v`, conservando la ejecución local SQLite sin servidor, y las comprobaciones PostgreSQL con `TEST_DATABASE_URL` según README; registrar resultados y cualquier check omitido, y comprobar el flujo recepción-salida-listado con persistencia real, incluidos conflictos concurrentes observables como `409` en PostgreSQL.
- [x] 5.2 Ejecutar `openspec validate model-pickup-point-parcel-custody --strict` y obtener revisión independiente de `sdd_reviewer` frente a escenarios, arquitectura y evidencia; corregir hallazgos mediante `sdd_builder` y repetir las comprobaciones afectadas antes de marcar el trabajo completo.

## Workflow follow-up

- La sincronización de main specs y el archivado quedan fuera de esta planificación/implementación hasta que se autoricen. Al sincronizar, actualizar también los propósitos descriptivos antiguos de Delivery y Return; las delta specs no sustituyen esos textos automáticamente.
