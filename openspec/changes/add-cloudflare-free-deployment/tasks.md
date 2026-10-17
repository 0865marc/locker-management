# Tasks

El usuario ha aprobado la implementación de este plan. Partir del `main` integrado y sus especificaciones principales: cotizaciones/CI ya están sincronizados y archivados, y la aplicación usa paquetes por funcionalidad y simuladores autónomos. Conservar esa línea base sin modificar cambios archivados. Marcar las casillas únicamente después de verificar todos sus criterios.

Dependencias: 1.1–1.3 preceden a la implementación dependiente; después, 2 y 3 pueden avanzar con propiedad de archivos separada; 4 depende de ambas; 5 depende de 4.4; 6 integra 2–5; 7–8 cierran preparación y aceptación. Un fallo demostrado de viabilidad bloquea tareas dependientes. Si solo faltan cuenta/credenciales para 1.4, continuar trabajo local independiente y mantener 1.4/8.3 pendientes; no confundir esa ausencia con fallo ni con aceptación Free.

Estado de ejecución (2026-10-17): 1.1–1.3 iniciadas, todavía sin completar. Se han preparado la distribución aislada, el experimento nativo y su harness. La política de red activa bloquea `index.pyodide.org`, necesario para `pywrangler sync`; la ejecución nativa y sus mediciones siguen pendientes. Es un bloqueo del entorno, no un resultado técnico de incompatibilidad. No se ha iniciado la implementación dependiente ni el despliegue remoto. Las 77 pruebas unitarias y 50 pruebas PostgreSQL/Alembic del perfil existente pasan, al igual que Ruff y Pyright raíz (cero errores y advertencias); esta evidencia de base no acredita tareas de Cloudflare ni la verificación final 8.1. Consultar `cloudflare/FEASIBILITY.md` para comandos y límites de la evidencia.

## 1. Comprobar viabilidad del runtime y fijar herramientas

- [ ] 1.1 Crear la distribución aislada `cloudflare/pyproject.toml`, lock y configuración inicial con Python >=3.13, herramientas oficiales y fecha de compatibilidad fijadas; verificar instalación bloqueada, build y FastAPI/Pydantic con los esquemas reales en el runtime local, registrando versiones y comandos exactos.
- [ ] 1.2 Ejecutar un experimento acotado de ASGI con entorno de petición, ContextVar aislado, D1 prepare/bind/batch con fallo intermedio y json_each, más producer/handler Python Queues con ack previo; verificar resultados mediante tests del runtime oficial y registrar go/no-go técnico, sin depender de SQLModel/AMQP.
- [ ] 1.3 Medir localmente imports/snapshot y validación/serialización representativas de 1000/2000 celdas; resolver la estrategia de tipos del SDK compatible con el chequeo raíz y documentar límites de esta evidencia en `cloudflare/` y comandos de desarrollo en README. Verificar que no hay acceso a bindings al importar y que no se reconstruye FastAPI por petición.
- [ ] 1.4 Cuando exista un destino Free autorizado, ejecutar el experimento remoto mínimo y registrar CPU HTTP en frío/caliente, presupuesto efectivo de cola, arranque, tamaño y errores de límite. Verificar plan/cuota reales y resultado de las peticiones máximas; ante incompatibilidad observada, detener trabajo dependiente y presentar revisión del diseño. Si falta acceso, dejar esta casilla pendiente con el motivo.

## 2. Separar composición y distribuciones sin romper PostgreSQL

- [ ] 2.1 Extraer `backend/composition.py` y adaptar `main.py` usando los puertos y `use_cases.py` de cada paquete de aplicación, preservando `create_app`, URL precedence, app global CPython y lifecycle; añadir unidades de composición y ejecutar las existentes de main/HTTP, documentando los dos perfiles y su selección por entrypoint.
- [ ] 2.2 Incorporar `backend/cloudflare_worker.py`, contexto por evento y proveedores tipados de bindings; comprobar con tests concurrentes de dos entornos y excepciones que no se mezclan recursos, no hay I/O al importar ni tareas desprendidas y las rutas actuales siguen utilizándose.
- [ ] 2.3 Actualizar `backend/pyproject.toml` (`py-modules`) y `backend/Dockerfile` para incluir la composición compartida; construir e instalar el wheel fuera del árbol fuente y comprobar sus imports, después ejecutar el smoke Docker/PostgreSQL existente para detectar módulos omitidos.
- [ ] 2.4 Implementar `scripts/cloudflare/prepare.py` con lista explícita de fuentes y árbol generado ignorado; verificar preparación determinista y fresca, ausencia de secretos/infraestructura CPython y build desde checkout limpio. Documentar el procedimiento y actualizar `.gitignore` y la excepción acotada de raíces de composición en `AGENTS.md`.

## 3. Preparar esquema D1 y frontera de persistencia

- [ ] 3.1 Crear migración inicial D1 de las ocho tablas actuales, índices, constraints y revisión/token internos; probar apply/reapply, esquema vacío y populated reopen mediante D1 oficial, más rechazo de FK, XOR, doble ocupación, geografía y estados/fechas inválidos. Mantener revisiones Alembic 0001–0005 byte a byte.
- [ ] 3.2 Implementar frontera tipada D1 y conversión de UUID, UTC con microsegundos, opcionales y números; verificar round trips y entradas inválidas con pruebas unitarias y nativas, sin pérdidas por float/proxies JS. Añadir errores de persistencia y mapeo HTTP 503 con pruebas que descarten filtración de SQL, tokens o credenciales.
- [ ] 3.3 Documentar migraciones locales/remotas D1, compatibilidad de versión y reversión no destructiva; actualizar únicamente la excepción D1/Alembic de `AGENTS.md`. Verificar los comandos sobre base local nueva y confirmar que API/consumidor no migran al arrancar y que una reversión incompatible se rechaza sin alterar datos.

## 4. Implementar repositorios y demostrar atomicidad

- [ ] 4.1 Implementar creación/lectura/disponibilidad de lockers y recepción/consulta/salida de paquetes sin locker; verificar contratos HTTP y persistencia, UUID/UTC, orden y lectura coherente. Probar alta de 1000 celdas con json_each atómico y rechazo de 1001, sin consultas por celda ni truncar listas.
- [ ] 4.2 Implementar snapshot y CAS con token para todas las modificaciones de configuración y recepciones de entregas/devoluciones; reutilizar selección exacta del dominio. Verificar última celda compartida, configuración contra recepción, relectura tras CAS perdido, tres intentos totales y 503 por contención agotada, incluyendo valores de dimensiones máximos y volúmenes casi iguales.
- [ ] 4.3 Implementar salidas asignadas con transición/liberación específica en el mismo batch; verificar todos los tipos de salida, rollback interior con revisión/token revertidos, doble salida y reocupación segura. Probar que una respuesta de commit desconocida no causa retry automático y que ningún writer de capacidad omite el protocolo; documentar la distinción entre 409 y 503.
- [ ] 4.4 Implementar repositorio de cotizaciones con start condicional, complete atómico, fail por estado y lectura coherente; verificar duplicados, resultados mixtos, rollback de lote, lectura concurrente y rechazo sin cambios cuando complete no parte de PROCESSING. Mantener precios, orden y errores del contrato actual.
- [ ] 4.5 Instrumentar el presupuesto de D1 en pruebas de todos los endpoints, incluidos tres intentos CAS y lotes de 1000 celdas; verificar como máximo 24 sentencias por invocación HTTP, 100 parámetros por sentencia y tamaños admitidos, contando sentencias individuales de batch. Documentar resultados y fallar si las optimizaciones alteran atomicidad o límites públicos.

## 5. Conectar Queues y el flujo completo de cotizaciones

- [ ] 5.1 Implementar el publicador Cloudflare que espera send confirmado y el handler que solicita ack antes de procesar; comprobar publicación única, 202/Location, fallo inicial sin publish, 503/PUBLISH_ERROR, ack fallido sin ejecución y mensaje inválido con unidades y smoke nativo. Documentar la diferencia entre ack síncrono Queues y confirmación AMQP.
- [ ] 5.2 Configurar lote uno, concurrencia uno, cero retries y retención Free, reutilizando `ShippingQuoteComparator` y los simuladores de construcción sin argumentos/perfiles privados fijos; verificar procesamiento secuencial, duplicados ignorados, timeout sin retry, ausencia de requeue/recuperación y que las antiguas variables `SHIPPING_*` no alteran proveedores. Registrar la configuración de cola y las limitaciones ante caída/retención.
- [ ] 5.3 Ejecutar recorrido HTTP/Queues/D1 completo con éxito, resultados mixtos y fallos de publicación/procesamiento; verificar lectura desde otra instancia y ningún resultado parcial. Mantener y ejecutar el smoke RabbitMQ existente para demostrar compatibilidad del otro perfil.

## 6. Integrar verificación reproducible de los dos perfiles

- [ ] 6.1 Consolidar harness aislado `cloudflare/tests/` y comando `scripts/cloudflare/check.sh` para preparación, build, migraciones locales y contratos nativos, con cleanup y fallos claros; ejecutarlo desde checkout limpio y documentar su diferencia respecto de las suites PostgreSQL/RabbitMQ y la medición remota.
- [ ] 6.2 Añadir el check independiente `Cloudflare local` conservando los cinco checks del backend, permisos de lectura, cancelación y límites, sin alterar el workflow separado `OpenSpec closure`; verificar su ejecución sin secretos/cuenta, la instalación bloqueada, detección de staging obsoleto y ausencia de operaciones remotas. Documentar comandos locales equivalentes.
- [ ] 6.3 Ampliar análisis estricto a fuentes nuevas, con entorno 3.13 solo donde proceda y tipos precisos del SDK verificados contra el runtime; ejecutar desde backend `uv run --extra dev pyright --project .. --warnings` con cero errores/advertencias y Ruff lint/formato para todas las fuentes nuevas, sin relajar reglas ni ampliar exclusiones de producción.

## 7. Preparar despliegue y operación verificables

- [ ] 7.1 Completar manifiesto y runbook con placeholders, configuración local/remota, recursos Free, credenciales fuera de Git, creación D1/Queues, migración previa y deploy Workers sobre workers.dev; comprobar configuración/build y ensayar el procedimiento local, sin desplegar desde CI ni activar pago.
- [ ] 7.2 Preparar script/fixtures de aceptación remota con diez lockers, uno ampliado a 2000 celdas, cien entregas, cien devoluciones y treinta cotizaciones; verificar localmente todos los endpoints, carga máxima, carreras y recolección de contadores. Documentar presupuesto de campaña, métricas de CPU y cómo detener cargas auxiliares antes de agotar cuotas.
- [ ] 7.3 Documentar y ensayar la reversión a código compatible, parada de nuevas recepciones/consumidor y rechazo de esquemas incompatibles; verificar que no se borran datos/colas, no se alteran recursos PostgreSQL y cambiar de perfil no implica transferir datos.

## 8. Verificación final y aceptación

- [ ] 8.1 Ejecutar regresión completa aplicable: unidades sin servicios, integración PostgreSQL/Alembic, mensajería RabbitMQ, wheel instalado, Docker smoke y Cloudflare local; repetir Ruff y el Pyright obligatorio con cero errores/advertencias tras correcciones y registrar comandos/resultados reales. No presentar suites ausentes como omitidas con éxito.
- [ ] 8.2 Obtener revisión independiente `sdd_reviewer` de contratos, fronteras hexagonales, CAS y todos sus writers, batch/rollback, cola, empaquetado y evidencias; resolver hallazgos y repetir solo comprobaciones afectadas. Ejecutar `openspec validate add-cloudflare-free-deployment --strict` y separar validación documental de pruebas funcionales.
- [ ] 8.3 En el destino Free autorizado, aplicar migraciones, desplegar el paquete revisado y ejecutar smoke/campaña completa: CPU por operación en frío/caliente, memoria/arranque, consultas/filas D1, operaciones Queues, almacenamiento y errores. Registrar resultado verificable dentro de las cuotas actuales, incluido el máximo de 1000 celdas; dejar pendiente si no existe acceso y bloquear aceptación si falla un caso obligatorio, sin reducir contratos ni activar pago.

## Workflow follow-up

- Presentar al usuario el resultado como planificación lista; no iniciar estas tareas durante el turno de propuesta.
- El coordinador gestiona cualquier sincronización/archivo posterior solo cuando corresponda y esté autorizado. Cotizaciones/CI ya están sincronizados y archivados; conservar sus requisitos principales y los de identidad/runtime existentes. La actualización de la rama no cierra este cambio incompleto: `OpenSpec closure` seguirá fallando en una PR a main mientras permanezca activo, sin excepciones ni bypass.
- Diferenciar implementación local verificada, despliegue remoto y aceptación Free. La falta de evidencia remota impide afirmar el último estado, aunque el trabajo local esté terminado.
