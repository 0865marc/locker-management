# Spec Delta

## MODIFIED Requirements

### Requirement: Report five independent CI checks

GitHub Actions SHALL conservar cinco checks del backend para PR a main y pushes a main: Ruff, Pyright, unidades, PostgreSQL/migraciones y Docker/API. SHALL añadir Cloudflare local como sexto resultado del backend, sin alterar el check separado OpenSpec closure. Cada fallo SHALL fallar su check, con ejecución acotada, permisos de lectura y sin credenciales de despliegue. Nuevas actualizaciones de una PR SHALL cancelar su ejecución obsoleta sin cancelar otras PR.

#### Scenario: Verify a pull request and its merge
- **WHEN** se abre/actualiza una PR a main o llega un commit a main
- **THEN** se ejecutan los cinco checks existentes y Cloudflare local con nombres estables, incluso para cambios fuera de backend, informando sus resultados sin ocultar fallos

#### Scenario: Replace obsolete pull request work
- **WHEN** una PR recibe otro commit mientras se verifica
- **THEN** se cancela la ejecución anterior de esa PR, se verifica la revisión nueva y las otras PR no se afectan

## ADDED Requirements

### Requirement: Verify Cloudflare locally without deployment credentials

Cloudflare local SHALL preparar el paquete bloqueado, construir Workers, aplicar migraciones D1 locales y ejecutar los contratos nativos seleccionados, incluidos concurrencia, rollback y cola. SHALL fallar ante instalación, build, migración, runtime o test incorrecto y limpiar únicamente sus recursos. SHALL no necesitar cuenta Cloudflare, escribir recursos remotos ni desplegar al integrar una PR.

#### Scenario: Reproduce the Cloudflare check
- **WHEN** un runner limpio ejecuta el check con las versiones declaradas y sin secretos Cloudflare
- **THEN** prepara fuentes compartidas, verifica el paquete y ejecuta pruebas sobre los bindings locales oficiales con resultado independiente

#### Scenario: Do not confuse local CI with Free acceptance
- **WHEN** todos los checks locales pasan
- **THEN** el resultado se identifica como verificación local y no sustituye la campaña remota de límites Free

### Requirement: Verify both distributable source sets

La verificación SHALL comprobar que el paquete CPython y la imagen existente incluyen la composición compartida, y que Workers se genera desde las fuentes vigentes declaradas. Resoluciones inconsistentes SHALL fallar sin modificar lockfiles o fuentes. El paquete Workers SHALL excluir infraestructura CPython incompatible y secretos, sin mantener copias manuales divergentes de lógica de negocio.

#### Scenario: Install the CPython distribution and run the image
- **WHEN** se instala el paquete construido en un entorno limpio y se ejecuta el smoke Docker actual
- **THEN** la composición se puede importar desde el paquete instalado y la imagen arranca y consulta PostgreSQL sin módulos ausentes

#### Scenario: Reject stale staging or dependency drift
- **WHEN** el árbol preparado no corresponde a las fuentes actuales o un lockfile no concuerda con sus dependencias
- **THEN** el check falla antes de publicar artefactos, sin resolver versiones nuevas ni usar una copia obsoleta
