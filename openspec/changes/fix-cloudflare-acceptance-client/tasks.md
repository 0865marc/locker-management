# Tasks

Plan aprobado por el usuario antes de implementar. Se omite deliberadamente `design.md`, condicional según las instrucciones CLI: una cabecera en un archivo no requiere un diseño separado ni deja decisiones abiertas.

## 1. Identificar y verificar el cliente

- [x] 1.1 Añadir `User-Agent: LockerManagementAcceptance/0.1` en la construcción común de peticiones de `HttpRequest`, sin cambiar ninguna otra opción. Revisar el diff y pasar `deploy/cloudflare/.venv/bin/python -m unittest discover -s deploy/cloudflare/tests -p test_acceptance.py -v` desde la raíz; no añadir tests permanentes que solo repliquen la constante.
- [x] 1.2 Ejecutar Ruff sobre el archivo y, desde `backend/`, `uv run --extra dev pyright --project .. --warnings` y `uv run --extra dev pyright --project ../deploy/cloudflare --warnings`, ambos con cero errores y advertencias. Obtener revisión independiente del alcance y evidencia, corrigiendo cualquier hallazgo pertinente.

Verificación: tres pruebas existentes aprobadas; Ruff y formato correctos; ambos Pyright con cero errores y advertencias. Revisión independiente sin hallazgos. Los comandos uv utilizaron `UV_CACHE_DIR=/workspace/locker-management/.cache/uv`, una caché escribible del entorno.

El usuario informó HTTP 200 únicamente para el GET de diagnóstico con la nueva cabecera. La campaña remota completa y las mediciones/cuotas Free permanecen pendientes; este cambio no las ejecuta ni las declara aprobadas.
