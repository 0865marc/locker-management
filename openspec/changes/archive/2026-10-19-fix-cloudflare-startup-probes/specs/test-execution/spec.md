# Spec Delta

## ADDED Requirements

### Requirement: Report startup clock limitations honestly

El spike SHALL arrancar sin exigir un origen positivo del reloj y conservar la medición iniciada antes de importar la aplicación. Sus medidas internas sin avance SHALL indicarse como no disponibles con motivo explícito. Las medidas internas y de pared del host SHALL distinguirse de CPU y no acreditar cuotas Free.

#### Scenario: A zero clock origin is valid
- **WHEN** el reloj inicial devuelve cero durante la importación del spike
- **THEN** la aplicación se carga después de tomar esa muestra sin abortar por el origen del reloj

#### Scenario: The runtime clock does not advance
- **WHEN** el reloj no avanza entre las muestras de importación, validación, construcción o serialización
- **THEN** la medida correspondiente se informa como no disponible, sin presentarla como cero tiempo consumido ni como CPU

#### Scenario: Distinguish a clock delta from CPU evidence
- **WHEN** una medida interna tiene un delta positivo y el host mide una petición
- **THEN** se conservan ambas medidas con su procedencia y ninguna se presenta como consumo CPU o aceptación Free

### Requirement: Bound and diagnose native startup probes

Los ejecutores del spike y del perfil Cloudflare SHALL tolerar desconexiones HTTP transitorias durante su plazo de arranque sin ampliarlo. SHALL fallar ante plazo agotado, salida del proceso o error inesperado, mostrando causa, estado previo a la limpieza y un extracto acotado del log. SHALL limpiar sus procesos y recursos aislados tanto en éxito como en fallo.

#### Scenario: Recover from a transient disconnect
- **WHEN** el servidor cierra una conexión de sondeo sin respuesta y luego responde correctamente dentro del plazo
- **THEN** el ejecutor continúa esperando y solo inicia las pruebas nativas tras la respuesta válida

#### Scenario: Exhaust the startup deadline
- **WHEN** las desconexiones continúan hasta agotar el plazo de arranque
- **THEN** el ejecutor termina con fallo, identifica el plazo y el último error y muestra el estado y extracto del log antes de limpiar sus recursos

#### Scenario: Report a process exit accurately
- **WHEN** el proceso termina antes de estar listo
- **THEN** el diagnóstico muestra su código de salida observado y el log disponible, sin atribuirle el código de una señal enviada después para limpiar

#### Scenario: Preserve unexpected failures
- **WHEN** aparece un error de decodificación o un fallo inesperado durante el sondeo
- **THEN** no se convierte en un reintento transitorio ni en éxito; se conserva su causa y se ejecuta la limpieza aunque el log no esté disponible

### Requirement: Verify startup probes without the native runtime

Las regresiones de reloj y sondeo SHALL ejecutarse sin descargar Python Workers ni usar servicios o datos reales. El ejecutor del spike SHALL incluirlas automáticamente antes de sincronizar el runtime. Su éxito SHALL informarse como evidencia unitaria y no completar comprobaciones nativas o remotas ausentes.

#### Scenario: Exercise failure paths before native synchronization
- **WHEN** se ejecutan las unidades o el ejecutor del spike con el runtime nativo aún ausente
- **THEN** se comprueban reloj cero/congelado, recuperación de desconexión, plazo agotado, salida del proceso y errores inesperados con recursos controlados
- **AND** superar esas unidades no presenta Python/WASM, Queues ni Free como verificados
