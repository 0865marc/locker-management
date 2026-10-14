# Tasks

El usuario aprobó explícitamente el plan y la incorporación de las cinco especificaciones. El coordinador mantiene el seguimiento y asigna cada fase a su responsable.

## 1. Comprobar la base documental aprobada

- [x] 1.1 `sdd_builder`: contrastar los cinco deltas con las fuentes y los escenarios de aceptación documental de `design.md`; entregar evidencia de correspondencia y límites de cobertura, sin modificar código ni añadir pruebas. Si aparece una discrepancia de requisitos, devolverla al coordinador para revisión por `sdd_planner`.
- [x] 1.2 `sdd_builder`: verificar `openspec validate document-existing-capabilities --strict` y registrar su resultado. Si resulta útil y está disponible, ejecutar desde `backend/` la suite existente `uv run --extra dev python -m unittest discover -s tests -v`; informar por separado ejecución, omisiones e integración PostgreSQL no ejecutada, sin exigir Docker ni modificar datos.

## 2. Incorporar las especificaciones principales

- [x] 2.1 Coordinador: sincronizar mediante `openspec-sync-specs` los cinco deltas a las rutas exactas de `proposal.md`; comprobar que cada destino contiene su `Purpose` y todos sus requisitos y escenarios, sin marcadores pendientes, y ejecutar `openspec validate --specs --strict`.

## 3. Revisar y verificar el resultado conjunto

- [x] 3.1 `sdd_reviewer`: revisar independientemente las cinco specs principales contra deltas, fuentes, límites arquitectónicos y evidencia de verificación; entregar hallazgos con referencias o confirmar su ausencia, sin editar archivos.
- [x] 3.2 Coordinador: canalizar los hallazgos documentales hacia `sdd_planner` o `sdd_builder` según afecten al plan o al resultado, repetir la sincronización si cambia un delta y obtener la revisión del trabajo afectado; verificar que no queden hallazgos accionables y que el diff se limite a los artefactos del cambio y las cinco specs principales.
- [x] 3.3 Coordinador: verificar el estado final con `openspec validate document-existing-capabilities --strict` y `openspec validate --specs --strict`, y entregar el informe de incorporación, revisión y comprobaciones, distinguiendo sincronización completada de archivado no realizado.

## Workflow follow-up

- Mantener el cambio sin archivar; el archivado solo se realizará si el usuario lo solicita posteriormente.

## Verification evidence

- 1.1: `sdd_builder` contrastó los 16 requisitos y 22 escenarios con código, configuración, README y pruebas existentes sin encontrar discrepancias. `sdd_planner` alineó los cinco deltas con el idioma inglés solicitado en la propuesta aprobada: mismos contratos y segmentos literales, incluidos mensajes de error en español. El builder y el coordinador revisaron el texto final.
- 1.2: `openspec validate document-existing-capabilities --strict` correcto después de la traducción. Se inspeccionaron las pruebas, pero no se ejecutó la suite: el alcance es documental y la verificación estática es suficiente según el diseño aprobado. No se ejecutaron integración PostgreSQL, Docker ni operaciones de base de datos. Los límites de cobertura siguen registrados en `design.md`.
- 2.1: sincronizadas las cinco specs principales mediante `openspec-sync-specs`, con `Purpose` y `Requirements`, sin encabezados de operaciones delta ni marcadores pendientes. Comparación exacta contra los deltas después de convertir únicamente título y encabezado de requisitos: 16 requisitos y 22 escenarios conservados. `openspec validate --specs --strict`: 5 correctas, 0 fallos; `openspec list --specs` reconoce las cinco capacidades.
- 3.1: revisión independiente de `sdd_reviewer` sin hallazgos accionables. Confirmados contratos HTTP y errores, persistencia y rollback, migraciones, ciclo de vida, límites arquitectónicos y equivalencia exacta de las cinco specs con sus deltas. Inglés y literales preservados. El reviewer ejecutó ambas validaciones estrictas correctamente; inspeccionó pruebas, sin ejecutarlas.
- 3.2: no hubo hallazgos que requirieran correcciones. El coordinador comparó SHA-256 con la referencia previa a la aplicación: los 51 archivos originales fuera del directorio del cambio permanecen iguales y las únicas incorporaciones son las cinco specs principales. Dentro del cambio se actualizaron los deltas al inglés, una frase de idioma en el diseño y el seguimiento de tareas. Se preservó la propuesta editada previamente por el usuario. Git no está disponible como repositorio utilizable en este directorio; la comprobación de alcance se basa en inventario y hashes.
- 3.3: comprobación final del coordinador: `openspec validate document-existing-capabilities --strict` correcto y `openspec validate --specs --strict` con 5 correctas y 0 fallos. Documentación incorporada y sincronizada, revisión terminada sin hallazgos y seis tareas verificadas. No se ejecutaron pruebas de aplicación ni integración PostgreSQL. El cambio permanece sin archivar.
