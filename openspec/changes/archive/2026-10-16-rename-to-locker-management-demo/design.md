# Design

## Context

Véase `proposal.md` para la motivación. La base actual es `main` en `021dfc216a87dbc23ca56b29e9ff63eb17726dd7`: incorpora cotizaciones asíncronas, API/worker con RabbitMQ, migración `0005` y Ruff/CI. La adaptación conserva esas incorporaciones y extiende la misma sustitución de identidad a sus referencias. Sin overrides, el proyecto anterior es `hexagonal_architecture` y sus volúmenes `hexagonal_architecture_postgres_data` y `hexagonal_architecture_rabbitmq_data`; debe verificarse el nombre real si se usó `-p` o `COMPOSE_PROJECT_NAME`. El delta de runtime del cambio de cotizaciones todavía no está sincronizado: este delta conserva su readiness y ambos volúmenes para evitar revertirlos al sincronizar.

El checkout es `/workspace/hexagonal_architecture`, con `.git` propio y sin `core.worktree`. El remoto verificado es `0865marc/hexagonal_architecture`, ID **1420522580**, con permiso de administración. El conector disponible no expone renombrado y `gh` informa de token inválido: el paso remoto requiere una capacidad autenticada o su ejecución por el usuario. No es una falta de permisos sobre el repositorio.

## Goals / Non-Goals

**Goals:** aplicar una identidad consistente y mantener una ruta explícita para instalaciones con datos, con verificaciones independientes de contenido, runtime y nombre remoto.

**Non-Goals:** cambiar dominio, casos de uso, contratos HTTP, versiones de dependencias o esquema; reescribir historia; migrar automáticamente datos, roles o volúmenes; modificar herramientas hermanas `/workspace/hexagonal-*` ajenas al repositorio.

## Decisions

1. **Representaciones según el contexto.**

   | Uso | Valor propuesto |
   | --- | --- |
   | README y título OpenAPI | `Locker Management Demo` |
   | Paquete Python, repositorio, carpeta y proyecto Compose | `locker-management-demo` |
   | Base/usuario/contraseña PostgreSQL y usuario/contraseña RabbitMQ de Compose | `locker_management_demo` |
   | Base dedicada y vhost RabbitMQ en ejemplos de pruebas | `locker_management_demo_test` |

   README describirá una demo de backend para gestionar lockers y puntos de entrega/recogida. La descripción del paquete reflejará ese propósito. Mantener espacios en identificadores técnicos dificultaría instalación y comandos; estos formatos conservan el nombre legible sin cambiar imports ni estructura de módulos.

2. **Cambios localizados.** Editar los seis archivos de implementación identificados en la propuesta. Regenerar el metadato del proyecto en `uv.lock` con uv conservando todas las dependencias, versiones y fuentes de `main`, incluidas `aio-pika` y Ruff; conservar también el módulo `worker` y la configuración de herramientas. El título se cambia en la composición, y la URL por defecto en el adaptador de base de datos. La arquitectura hexagonal continúa vigente; un reemplazo global de `hexagonal` alteraría instrucciones técnicas e historia válidas.

3. **Compose predecible y configurable.** Añadir `name: locker-management-demo`. Usar `${POSTGRES_USER:-locker_management_demo}`, `${POSTGRES_PASSWORD:-locker_management_demo}` y `${POSTGRES_DB:-locker_management_demo}` en PostgreSQL y las URLs de API, migrador y worker con host `db`. Usar `${RABBITMQ_DEFAULT_USER:-locker_management_demo}` y `${RABBITMQ_DEFAULT_PASS:-locker_management_demo}` en RabbitMQ y las URLs AMQP de API/worker con host `rabbitmq` y vhost `/`. Conservar servicios, healthchecks, readiness, puertos, simulación, semántica de cola y claves `postgres_data`/`rabbitmq_data`. El fallback local convencional `amqp://guest:guest@localhost/` no identifica al proyecto y permanece intacto. No añadir migraciones ni cambiar hostname/topología del broker.

4. **Auditoría contextual de referencias.** Revisar archivos versionados actuales buscando `hexagonal_architecture`, `hexagonal-fastapi`, `hexagonal_fastapi`, títulos anteriores y variantes de base/credenciales `hexagonal`. Tras el cambio no deben quedar como identidad activa. Excepciones documentadas: lenguaje arquitectónico; `openspec/changes/archive/` y evidencias históricas; explicación de transición en README; artefactos del cambio que describen el estado anterior. El spec principal conserva el valor antiguo hasta sincronizar el delta autorizado. `.git` y metadatos locales generados se gestionan mediante sus herramientas, sin sustitución textual. Las evidencias con rutas antiguas no se falsifican.

5. **Identidad remota y carpeta como operaciones verificadas.** Comprobar disponibilidad de `0865marc/locker-management-demo` y acceso autenticado; renombrar el repositorio existente, nunca crear otro para sustituirlo. Verificar ID **1420522580** en la nueva ruta antes de ejecutar `git remote set-url origin https://github.com/0865marc/locker-management-demo.git`. No cambiar `origin` si el renombrado falla o está bloqueado. Tras verificar los archivos, trasladar el checkout a `/workspace/locker-management-demo` solo si el gestor del espacio de trabajo permite volver a vincularlo sin perder el proyecto; comprobar destino libre, estado Git y raíz OpenSpec. Un `mv` aislado puede dejar referencias de la aplicación rotas: si no se dispone de esa capacidad, comunicar el paso pendiente y conservar la ubicación física actual.

## Risks / Trade-offs

- [Volumen inicializado con credenciales antiguas] → PostgreSQL no reaplica `POSTGRES_*` sobre datos existentes. La guía conservará sus valores reales; cambiarlos en Compose no constituye una migración.
- [Proyecto Compose nuevo muestra una base vacía] → Seleccionar explícitamente el proyecto anterior verificado antes del primer arranque; no borrar, copiar ni renombrar el volumen existente.
- [Estado RabbitMQ existente] → Conservar volumen físico, credenciales y el contenedor/nodo existente; cambiar defaults no cambia usuarios existentes. Detener solo API/worker y no recrear el broker por este cambio de nombre. Se mantiene el comportamiento de identidad de nodo de `main`: este renombrado no garantiza una migración de mensajes ni añade recuperación del broker.
- [Renombrado remoto o vinculación local bloqueados] → Completar los cambios revisables y verificaciones independientes, dejando esas tareas pendientes con su causa; no declarar el renombrado total completado.

## Migration Plan

1. El plan ya fue aprobado e implementado sobre la base anterior; la solicitud posterior de PR autoriza publicar y resolver los conflictos habituales contra `main`. Reconciliar los mismos seis archivos conservando íntegramente las nuevas funciones y ejemplos de CI/cotizaciones; extender los ejemplos y la transición a RabbitMQ.
2. Para una instalación en ejecución, documentar copia de seguridad y detener solo escritores mediante `docker compose stop api worker`, con el proyecto anterior verificado; mantener `db` y `rabbitmq` en ejecución. Conservar en el `.env` ignorado `COMPOSE_PROJECT_NAME`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`, `RABBITMQ_DEFAULT_USER` y `RABBITMQ_DEFAULT_PASS` con sus valores reales (credenciales originales: `hexagonal`). `-p` puede fijar el mismo proyecto en cada comando. Verificar `docker compose config` y ambos volúmenes antes de `up --build`, y comprobar después que el contenedor/nodo RabbitMQ sigue siendo el mismo. No usar `down`, `--force-recreate` ni borrar volúmenes durante esta transición de identidad; no recrear el broker para aplicar el nombre. Fuera de Compose, configurar también las URLs anteriores `DATABASE_URL` y `RABBITMQ_URL` cuando proceda.
3. Verificar continuidad de registros y revisión Alembic con la configuración conservada; una instalación nueva usará los valores nuevos. El rollback de contenido mantendrá la selección explícita del mismo proyecto y credenciales: volver a un valor predeterminado diferente no recupera ni mueve datos.
4. Repetir las verificaciones sobre la base actual y la revisión independiente antes de publicar el PR autorizado contra `main`. El renombrado remoto y el traslado local mantienen sus condiciones y bloqueos independientes. Sincronizar y archivar siguen pendientes de autorización específica.

## Verification

- Auditar referencias actuales con `git grep -n -i hexagonal` y clasificar las excepciones anteriores. Comprobar README, TOML y lockfile con el mapa de nombres; `uv lock --check` y `uv sync --locked --extra dev` deben aceptar el paquete nuevo sin actualizar dependencias.
- Comparar OpenAPI con `main` actual, incluidas cotizaciones: solo cambia `info.title`; `/docs` muestra el nombre nuevo. Comprobar la URL por defecto y precedencia de URL explícita/`DATABASE_URL`, también con una URL antigua configurada, y que el fallback AMQP guest sigue intacto. No añadir tests permanentes que solo repitan literales renombrados.
- Validar `docker compose config` sin overrides y con proyecto/credenciales antiguos: API/migrador/worker comparten PostgreSQL y API/worker usan las credenciales del broker; se resuelven ambos volúmenes previos. Ensayar arranque y una cotización completa API→broker→worker→PostgreSQL con ambas configuraciones aisladas. En la transición, detener solo API/worker y comprobar contenedor/nodo RabbitMQ idénticos, registros y revisión `0005` conservados y ambos volúmenes físicos intactos. Ejecutar también `scripts/ci/smoke.sh` cuando haya Docker. No tocar datos del usuario ni afirmar migración de mensajes.
- Desde `backend/`, con dependencias bloqueadas: `uv run --extra dev ruff check .`, `uv run --extra dev ruff format --check .`, `uv run --extra dev pyright --project .. --warnings` (**0 errores y 0 advertencias**) y unitarias sin `TEST_DATABASE_URL`/`TEST_RABBITMQ_URL`. Ejecutar integración PostgreSQL sin broker y mensajería con ambas URLs explícitas, mediante `python -m unittest discover -s tests/integration -t . -v -f` y `-s tests/messaging`; la suite completa requiere ambas URLs. Registrar resultados nuevos y limitaciones reales: las 95 pruebas/revisión `0004` anteriores no prueban esta base.
- Validar `openspec validate rename-to-locker-management-demo --strict`. La revisión independiente comprobará escenarios, excepciones, continuidad de datos y evidencias. Tras un traslado, resolver de nuevo la raíz OpenSpec y comprobar estado Git y remoto; la sincronización del spec y el archivo del cambio son operaciones posteriores del coordinador.
