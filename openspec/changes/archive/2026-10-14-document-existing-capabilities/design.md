# Design

## Context

La motivación figura en `proposal.md`. El comportamiento está implementado y no existen specs principales. El diseño resuelve cómo convertir contratos de varias capas en una base documental sin confundir características existentes, decisiones internas y pruebas realmente ejecutadas.

Las cinco especificaciones se redactan en inglés, conservando literalmente los ejemplos JSON, comandos, valores y mensajes de error existentes, incluidos los textos en español.

## Goals / Non-Goals

**Goals:** documentar contratos observables y operativos en las cinco capacidades propuestas, conservar trazabilidad compacta y mantener cada `Purpose` utilizable al sincronizar.

**Non-Goals:** modificar la aplicación o completar su cobertura. No se añaden autenticación, relación entre entregas y devoluciones, operaciones de edición o borrado, paginación, orden público de resultados, idempotencia, reintentos ni transacciones entre varias escrituras. Tampoco se promete validación SQL de textos vacíos, formato postal o longitud máxima.

## Decisions

1. **Capturar capacidades existentes como requisitos añadidos al catálogo.** Los cinco deltas usan `ADDED Requirements` porque no hay specs previas, no porque se añadan funcionalidades. Se descarta omitir las specs por ser un cambio documental: su creación es el resultado solicitado.
2. **Separar por comportamiento y responsabilidad operativa.** Entregas y devoluciones tienen contratos propios; persistencia, migraciones y ejecución reúnen lo compartido. Se descarta crear una spec por archivo o endpoint. Las rutas destino exactas figuran en `proposal.md`.
3. **Mantener la arquitectura actual.** `domain/` contiene entidades Python y puertos `Protocol`; `application/` solo usa esos contratos. Los adaptadores contienen HTTP y SQLModel; `main.py` compone las dependencias. La fábrica de sesiones se comparte, cada operación abre su sesión y cada escritura su transacción. Alembic usa los metadatos del adaptador y un historial común. Estas decisiones se describen aquí sin trasladar nombres internos de clases a los contratos funcionales.
4. **Validar documentación sin intervenir en servicios.** La aceptación se basa en contrastar fuentes y validar OpenSpec. Se descarta exigir Docker, modificar datos o crear pruebas para este cambio. Las pruebas existentes pueden ejecutarse después de aprobar el plan si resultan útiles y están disponibles; cualquier ejecución u omisión debe informarse con precisión.

### Trazabilidad y evidencia disponible

Las referencias son relativas a la raíz del repositorio. La tabla describe código y pruebas leídos, no pruebas ejecutadas durante esta planificación.

| Capacidad y contratos | Fuentes de implementación o procedimiento | Pruebas existentes y límites |
| --- | --- | --- |
| `delivery-management`: creación, normalización, blancos, cuerpo inválido, listado | `backend/domain/models.py:5`; `backend/application/use_cases.py:9`; `backend/adapters/http/schemas.py:6`; `backend/adapters/http/routes.py:17` | `backend/tests/test_application.py:9` y `:21`; `backend/tests/test_http.py:25`, `:43`, `:56`. El listado vacío se deduce del contrato y el código; no tiene escenario de prueba dedicado. |
| `return-management`: creación independiente, normalización, blancos, cuerpo inválido, listado | `backend/domain/models.py:17`; `backend/application/use_cases.py:22`; `backend/adapters/http/schemas.py:15`; `backend/adapters/http/routes.py:28` | `backend/tests/test_application.py:15` y `:21`; casos compartidos de `backend/tests/test_http.py`. No se prueba aisladamente el listado vacío. |
| `record-persistence`: identidad, separación y recuperación tras fallo | `backend/adapters/database/sqlmodel_repositories.py:11`, `:25`, `:40` | `backend/tests/test_repositories.py:31` y `:43` usan SQLite. `backend/tests/test_main.py:10` comprueba persistencia entre aplicaciones solo con `TEST_DATABASE_URL`. |
| `database-migrations`: esquema, reversión, separación del arranque, adopción manual | `backend/adapters/database/migrations/versions/0001_create_delivery_and_return.py:17`; `backend/adapters/database/migrations/env.py:20`; `backend/main.py:14`; `README.md:198` | `backend/tests/test_migrations.py:15` comprueba migración y reversión con SQLite. La adopción manual y la ausencia de migraciones en el arranque se fundamentan en README y código. |
| `application-runtime`: conexión, reutilización, cierre, dependencias de arranque y volumen | `backend/adapters/database/connection.py:11`; `backend/main.py:14`; `compose.yaml:1`; `README.md:17` y `:38` | No hay pruebas dedicadas a precedencia de URL, liberación por excepción u orden de Compose; evidencia estática. La integración opcional usa una base previamente migrada. |

### Escenarios de aceptación documental

- **Correspondencia:** al revisar cada requisito y escenario, su comportamiento debe quedar respaldado por las fuentes anteriores; una prueba ausente se registra como límite de evidencia, no como funcionalidad pendiente.
- **Catálogo completo:** tras la sincronización aprobada, deben existir los cinco destinos de la propuesta, con `Purpose` útil, requisitos y escenarios conservados, sin marcadores pendientes.
- **Alcance preservado:** el diff de este trabajo debe contener únicamente los artefactos del cambio y las cinco specs principales; código, pruebas, README y configuración permanecen fuera del cambio.
- **Validez verificable:** el cambio debe pasar `openspec validate document-existing-capabilities --strict` y, tras sincronizar, las specs principales deben pasar la validación estricta correspondiente de la CLI.

## Risks / Trade-offs

- Fijar detalles accidentales como contrato público → no se especifica orden de listado por UUID ni la estructura completa de errores de Pydantic. El router captura cualquier `ValueError` de creación, aunque los escenarios documentan las validaciones del dominio existentes.
- Confundir pruebas con dobles o SQLite con integración PostgreSQL → se distingue su alcance; `TEST_DATABASE_URL` es opcional y requiere una base previamente migrada. No se ha ejecutado ninguna prueba durante esta planificación.
- Convertir toda descripción operativa en garantía probada → el ciclo de vida y Compose se contrastan estáticamente; la adopción de tablas es un procedimiento manual documentado, no detección automática.

## Migration Plan

No hay migración de aplicación ni de datos. Tras la aprobación explícita del plan, `sdd_builder` comprobará el contenido y la evidencia; el coordinador sincronizará mediante `openspec-sync-specs` los cinco deltas a sus destinos. `sdd_reviewer` revisará independientemente el resultado, y se corregirán los hallazgos documentales dentro del alcance aprobado. El coordinador registrará las verificaciones y mantendrá el cambio sin archivar salvo petición posterior. Si hubiera que retirar esta incorporación documental, se revertirían únicamente sus archivos, sin operaciones sobre la base de datos.
