# Design

## Context

Ver `proposal.md`. El log del usuario localiza el fallo en `bootstrap.py`: `assert import_clock.STARTED > 0`. Una reproducción CPython con módulos de plataforma doblados confirma que cero aborta y un origen positivo carga la entrada. Ambos ejecutores capturan `URLError` y `TimeoutError`, pero `http.client.RemoteDisconnected` no deriva de ellas. La causa del fallo observado en CI sigue sin confirmarse porque falta su log.

## Goals / Non-Goals

**Goals:** corregir las precondiciones del instrumento y obtener diagnósticos útiles conservando límites y limpieza.

**Non-Goals:** cambiar aplicación, transporte productivo, dependencias, CI, datos o cuotas; regenerar evidencia anterior; resolver la restricción de red del entorno.

## Decisions

1. **Reloj como instrumento, no condición de arranque.** Mantener la inicialización de `import_clock` antes de importar `worker`, eliminando la aserción sin reemplazarla por otro requisito sobre el origen. Para importación y las tres fases del benchmark, conservar los campos de medida, usando `null` y un motivo explícito por medida cuando no haya avance. Un delta positivo se identifica como delta del reloj del runtime, nunca CPU. El tiempo de pared externo del host permanece separado. No sustituir el reloj por otro que prometa medir CPU: Workers puede congelar o limitar la resolución de sus relojes.

2. **Sondeo acotado y selectivo.** En `tests/run_spike.py` y `tests/run_runtime.py`, tratar `RemoteDisconnected` como transitorio junto a los errores ya esperados. Mantener el plazo monotónico de 90 segundos, el timeout de cada petición y la respuesta válida requerida. No capturar genéricamente errores para reintentarlos: JSON inválido y errores de programación siguen fallando. Un helper compartido bajo `tests/` puede concentrar este comportamiento sin introducir dependencias productivas.

3. **Diagnóstico antes de perder el proceso o su log.** Conservar el `evidence/runtime.log` que ya produce el spike; capturar el de producción dentro de su directorio temporal aislado y mostrarlo antes de eliminarlo. Ante fallo, mostrar causa, último error de conexión cuando proceda y código observado antes de la terminación de limpieza, o indicar que el proceso seguía vivo. Limitar el extracto a las últimas 120 líneas y 64 KiB; no volcar variables de entorno. Mantener cierre del grupo de procesos, espera y escalado de señal existentes. Un log ausente o ilegible no debe ocultar el fallo original. No modificar los archivos de evidencia histórica al implementar o ejecutar unidades.

4. **Regresiones locales incorporadas.** Usar relojes/procesos/respuestas controlados y directorios temporales para probar orden de importación con origen cero, reloj congelado y delta positivo, desconexión seguida de éxito, timeout, salida y error inesperado. Comprobar diagnóstico y limpieza sin esperas reales de 90 segundos. Incluir las unidades en la secuencia de `run_spike.py` previa a `pywrangler sync`, ampliando la selección existente si hace falta. Aclarar únicamente estas limitaciones de medición en `deploy/cloudflare/FEASIBILITY.md`, preservando registros históricos.

## Risks / Trade-offs

- Los campos diagnósticos internos podrán ser `null` → documentar el motivo y probar esa representación; los contratos HTTP del producto permanecen iguales.
- El entorno bloquea `index.pyodide.org` con 403 → verificar localmente la corrección y conservar pendientes las ejecuciones nativas de ambos perfiles; no reintentar ni sustituir esa evidencia por unidades.
- Resolver el fallo local no identifica automáticamente el fallo de CI → no atribuirle una causa sin su log. La aceptación Free sigue siendo independiente.

## Migration Plan

No hay migraciones ni despliegue. Aplicar la corrección de herramientas, ejecutar las comprobaciones locales y revisión independiente. La validación nativa se retomará cuando exista un entorno accesible; su ausencia no impide completar la corrección local ni autoriza declarar aceptado Cloudflare Free.
