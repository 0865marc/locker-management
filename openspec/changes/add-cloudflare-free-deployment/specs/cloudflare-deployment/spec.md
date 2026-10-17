# Spec Delta

## Purpose

Permitir desplegar y verificar la demo completa en servicios gratuitos de Cloudflare, con un procedimiento reproducible y límites operativos respaldados por mediciones.

## ADDED Requirements

### Requirement: Operate the complete backend on Cloudflare Free

El perfil Cloudflare SHALL ofrecer la API y el procesamiento asíncrono usando únicamente Workers, D1 y Queues disponibles en Free y una dirección workers.dev. SHALL conservar todos los endpoints, esquemas, estados y reglas de negocio existentes, incluidos documentación HTTP y transportistas simulados, sin requerir PostgreSQL, RabbitMQ ni servicios de pago externos.

#### Scenario: Complete a deployed business journey
- **WHEN** una instalación Cloudflare nueva recibe creación/configuración de locker, entrega y devolución con ocupación, consultas, salidas, reocupación y una cotización
- **THEN** responde con los mismos contratos públicos del perfil original y la cotización se consulta con sus resultados persistidos tras su procesamiento asíncrono
- **AND** `/docs` y `/openapi.json` siguen disponibles con la identidad actual

### Requirement: Preserve existing public capacity contracts

El perfil Cloudflare SHALL conservar el máximo de 1000 celdas nuevas por petición, la posibilidad de ampliaciones sucesivas y las listas completas sin truncarlas. La documentación SHALL distinguir el volumen comprobado en Free de los límites de negocio; exceder una cuota no autoriza reducir silenciosamente respuestas, introducir un máximo nuevo o activar pago.

#### Scenario: Exercise maximum creation and accumulated capacity
- **WHEN** se crea un locker con 1000 celdas y después se añaden otras 1000 en una petición válida
- **THEN** ambas operaciones conservan atomicidad y las consultas muestran las 2000 celdas y su disponibilidad correcta
- **AND** 1001 celdas nuevas en una sola petición siguen devolviendo 422 sin escrituras

### Requirement: Verify platform feasibility before claiming completion

La aceptación SHALL verificar runtime/dependencias, D1/rollback y Queues con herramientas oficiales. Una incompatibilidad o exceso Free demostrados SHALL bloquear la solución dependiente hasta revisar el diseño. Si faltan descarga del runtime o cuenta, SHALL permitirse implementación/pruebas locales, manteniendo pendiente la evidencia nativa/remota ausente y sin declarar viabilidad Free.

#### Scenario: Detect an incompatible runtime or budget
- **WHEN** la prueba inicial demuestra que el paquete no se ejecuta o una petición obligatoria excede el presupuesto de una cuenta Free
- **THEN** se registra el caso y la medición y no se continúa presentando esa solución como viable ni se sustituye por otro lenguaje o plan de pago sin revisar el alcance

#### Scenario: No remote account is available
- **WHEN** se pueden ejecutar pruebas locales pero no medir un despliegue Free autorizado
- **THEN** la evidencia local se informa por separado y la aceptación gratuita permanece pendiente

#### Scenario: Runtime download is blocked by the environment
- **WHEN** la política de red impide descargar dependencias Python Workers sin demostrar incompatibilidad del paquete
- **THEN** se permite implementar adaptadores/composición y ejecutar pruebas locales disponibles, registrando el bloqueo y dejando pendientes las comprobaciones Python Workers/Queues y Free que no se ejecutaron
- **AND** aprobar pruebas CPython o D1 mediante un puente local no completa esas comprobaciones ausentes

### Requirement: Publish reproducible Free acceptance evidence

La aceptación Free SHALL registrar cuenta/plan, versiones, fixtures, carga, CPU, errores, consultas D1, filas leídas/escritas, operaciones de cola y almacenamiento. SHALL ejecutar todos los endpoints y casos máximos definidos en el diseño dentro de las cuotas vigentes, sin degradar contratos. La emulación local y el tiempo HTTP de pared no sustituyen mediciones de CPU remotas.

#### Scenario: Measure the agreed acceptance workload
- **WHEN** se ejecuta la campaña definida con diez lockers, uno de 2000 celdas, cien entregas, cien devoluciones y treinta cotizaciones, además de casos máximos y concurrencia controlada
- **THEN** se publica un resultado reproducible con CPU en frío/caliente, p95/máximo, consultas, consumo y errores por operación
- **AND** todos los escenarios obligatorios deben pasar dentro de Free para declarar aceptado el objetivo

#### Scenario: A large valid request exceeds Free
- **WHEN** una petición válida de 1000 celdas o una consulta obligatoria agota CPU u otro límite aunque las peticiones pequeñas funcionen
- **THEN** la aceptación falla explícitamente y no se anuncia despliegue completo Free ni se oculta el caso mediante promedios

### Requirement: Prepare and deploy an explicit fresh environment

El procedimiento SHALL identificar los recursos de destino, usar una base D1 nueva, preparar su esquema antes de publicar el Worker y comprobar bindings, cola y contratos HTTP. SHALL usar placeholders y credenciales fuera del repositorio, separar ejecución local/remota y no crear recursos ni desplegar desde los checks ordinarios de CI.

#### Scenario: Install from a clean checkout
- **WHEN** el operador configura un destino Free autorizado y sigue el procedimiento con dependencias bloqueadas
- **THEN** crea D1/Queues, aplica migraciones, publica el Worker y verifica persistencia y cotizaciones sin pasos de esquema al arrancar ni infraestructura PostgreSQL/RabbitMQ

### Requirement: Preserve data on rollback and profile changes

La reversión SHALL conservar datos D1 y trabajos de la cola, restaurando solo código compatible con el esquema existente o deteniendo el servicio con diagnóstico. Cambiar al perfil PostgreSQL SHALL usar su almacenamiento independiente sin afirmar que copia, recupera o sincroniza los datos Cloudflare. Ninguna operación ordinaria SHALL activar pago o destruir recursos para resolver un fallo.

#### Scenario: A deployed release fails verification
- **WHEN** falla la comprobación posterior al despliegue
- **THEN** el procedimiento detiene nuevos trabajos y el consumidor afectado antes de revertir a código compatible, sin resetear D1, purgar la cola ni eliminar tablas con datos

#### Scenario: A free quota is exhausted
- **WHEN** la cuenta alcanza una cuota que impide la operación
- **THEN** se informa del fallo disponible de plataforma o aplicación sin activar una suscripción ni presentar un conflicto de capacidad de locker ficticio
