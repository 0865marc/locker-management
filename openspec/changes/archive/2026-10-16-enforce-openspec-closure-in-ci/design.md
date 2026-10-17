# Design

## Context

Ver la motivación en `proposal.md`. `.github/workflows/backend-ci.yml` ya ejecuta cinco checks independientes en PR a `main` y pushes a `main`, sin filtros de rutas, con `ubuntu-24.04`, `actions/checkout@v7.0.1` y permisos de lectura.

La referencia remota inspeccionada es `main` en `1b8c4f0afbeb27063c0174be4f211f79ca4110e3`; el checkout inicial `a94ae06` está seis commits por detrás. Los dos cambios activos de esa referencia son `add-asynchronous-shipping-quotations` (12/12 tareas) y `add-backend-ci` (8/8), con evidencia y revisión registradas. Un snapshot de sus artefactos actuales y las ocho specs principales supera `openspec validate --all --strict` (10 elementos). La implementación debe partir de esa versión actual, conservando estos artefactos de planificación.

El delta asíncrono actual ya conserva los escenarios de identidad de Compose y contiene los perfiles internos fijos de los simuladores; no se debe sincronizar la versión antigua del checkout. Su contrato de tarifas renombra `Supply three deterministic example adapters` a `Supply three example adapters with deterministic tariffs`.

La implementación inicial y el cierre del 2026-10-16 se conservan como historia en `tasks.md`. El 2026-10-17 el usuario precisó el alcance de la PR #7: comprobar el cierre solo en PR a `main`. Esta corrección retira el evento `push` del workflow OpenSpec y ajusta README; el script y la política de directorios activos permanecen iguales.

## Goals / Non-Goals

**Goals:** comprobar la estructura del checkout con un comando local y CI idénticos; sincronizar contratos implementados conservando la historia reciente; dejar el resultado final sin cambios activos.

**Non-Goals:** modificar la arquitectura hexagonal, aplicación, dependencias o migraciones; reejecutar suites de infraestructura sin cambios que lo justifiquen; configurar protección remota, publicar o archivar automáticamente desde CI.

## Decisions

### 1. Directorios activos como criterio de cierre

`scripts/ci/check-openspec-closed.sh` usará Bash y resolverá la raíz desde su propia ubicación, con un argumento opcional de raíz para comprobar árboles temporales. Inspeccionará únicamente hijos inmediatos de `openspec/changes`, incluyendo directorios ocultos y enlaces a directorios, y excluirá exactamente `archive`. Los archivos ordinarios no representan cambios. La ausencia o imposibilidad de leer el directorio devolverá un error explícito.

El script devolverá cero solo si no encuentra cambios activos, y un código no cero con todos los nombres ordenados en caso contrario. El diagnóstico indicará completar y validar la implementación, sincronizar specs y archivar localmente antes del merge. Será de solo lectura y no necesitará Node, OpenSpec, Python ni servicios. Consultar casillas de tareas o usar `openspec validate --archived` no prueba esta política: pueden existir cambios completos sin archivar o propuestas sin tareas.

### 2. Workflow pequeño e independiente

`.github/workflows/openspec-ci.yml` tendrá nombre `OpenSpec CI` y un job `openspec-closure` con nombre visible `OpenSpec closure`. Seguirá las convenciones existentes: runner `ubuntu-24.04`, checkout `v7.0.1`, permisos `contents: read`, timeout de cinco minutos y concurrencia por workflow/PR o referencia que cancele ejecuciones reemplazadas. Ejecutará el script desde la raíz únicamente para `pull_request` con base `main`, sin filtros por rutas.

Se conservarán los tipos predeterminados de `pull_request`: `opened`, `reopened` y `synchronize`. No habrá disparador `push` ni hooks locales: crear un commit o subir una rama sin PR no ejecuta este control. Un push a una rama con PR abierta hacia `main` sí genera `synchronize` y vuelve a verificarla; un push directo a `main` no dispara este workflow. Los eventos del workflow del backend se mantienen.

No requiere instalar herramientas ni depender de los jobs del backend. README documentará el comando local y que, para impedir merges, hay que exigir `OpenSpec closure` en las reglas de protección de `main`; un workflow por sí solo no configura ese bloqueo.

### 3. Sincronización anterior al movimiento

El coordinador sincronizará primero los deltas vigentes, revisará y validará las specs principales, y después archivará cada cambio. Si la sincronización ya se hizo explícitamente, usará el modo de archivo que omite repetirla (`--skip-specs`), manteniendo validación y evidencia. No se sobrescribirá una carpeta de archivo existente.

- `add-asynchronous-shipping-quotations`: añadir `asynchronous-shipping-quotations`; actualizar `application-runtime`, `database-migrations`, `shipping-quotes` y `test-execution`. Conservar identidad `locker-management-demo`, credenciales `locker_management_demo`, transición de volúmenes/nodo RabbitMQ, defaults de conexión y título API. Aplicar el renombrado del requisito de tarifas y los perfiles fijos actuales; no reintroducir configuración `SHIPPING_*` ni construcción directa determinista.
- `add-backend-ci`: añadir `backend-ci` con los cinco checks actuales.
- `enforce-openspec-closure-in-ci`: añadir `openspec-closure` y archivar este cambio al terminar implementación y revisión, sin excepción en el checker.

Dos descripciones MODIFIED actuales exceden el límite de 500 caracteres que se aplica al materializarlas como specs principales: `Manage a shared and reversible history` (521) y `Supply three example adapters with deterministic tariffs` (550). La sincronización podrá condensar únicamente su redacción, conservando todas sus obligaciones, fórmulas y escenarios; la comparación del contenido y la validación estricta posterior deben demostrarlo. No se dividirán contratos ni se cambiará comportamiento para satisfacer el validador.

### 4. Archivos previstos

- Crear `.github/workflows/openspec-ci.yml`, `scripts/ci/check-openspec-closed.sh` y `openspec/specs/openspec-closure/spec.md`.
- Actualizar README y `openspec/specs/{application-runtime,database-migrations,shipping-quotes,test-execution}/spec.md`.
- Crear `openspec/specs/{asynchronous-shipping-quotations,backend-ci}/spec.md` por sincronización histórica.
- Mover íntegramente `openspec/changes/{add-asynchronous-shipping-quotations,add-backend-ci,enforce-openspec-closure-in-ci}/` a `openspec/changes/archive/<fecha>-<nombre>/`, conservando artefactos y evidencia.

No está previsto editar `.github/workflows/backend-ci.yml` ni archivos de aplicación. Los cambios que lleguen al actualizar la base pertenecen a `main` y no a esta implementación.

## Risks / Trade-offs

- Una PR con planificación activa tendrá el check rojo hasta cerrar su cambio → documentar que cerrar forma parte de preparar el merge; no añadir bypass para este cambio.
- Una sincronización desde el checkout obsoleto perdería comportamiento reciente → partir de la referencia remota comprobada y revisar explícitamente identidad, perfiles fijos y renombrado de tarifas.
- La validación de un delta no garantiza la validez de las specs resultantes → validar antes y después de sincronizar, conservando todos los escenarios y distinguiendo evidencia documental de pruebas de implementación.
- Un check aprobado solo demuestra ausencia de carpetas activas → conservar revisión y evidencia de los cambios; exigir el check en protección de rama para bloqueo efectivo.

## Migration Plan

Tras aprobar el plan, trabajar desde `main` actual, implementar el script/workflow/documentación y verificar los escenarios con árboles temporales. Sincronizar los cambios previos, validar las specs, ejecutar Pyright y obtener revisión independiente. Archivar los dos cambios previos y después sincronizar y archivar este cambio cuando sus tareas de implementación estén verificadas. Ejecutar el checker final, validar todas las specs y comprobar que `openspec list --json` no enumera cambios activos. La ejecución real de Actions se verificará al publicarse; las comprobaciones locales no se presentarán como ejecución remota.

Para la corrección del 2026-10-17, ajustar únicamente el evento del workflow y su explicación en README, comprobar la matriz de eventos con actionlint y aserciones sobre el YAML, ejecutar Pyright y obtener revisión independiente. El coordinador sincronizará el requisito actualizado de `openspec-closure` y devolverá los artefactos a su misma ruta de archivo fechada antes de actualizar la PR #7. No se repiten la sincronización ni el archivo de los otros dos cambios históricos.
