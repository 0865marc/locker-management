# Design

## Context

Ver proposal.md para motivación. Dimensions ya existe en domain/lockers.py; LockerService y repositorios contienen firmas por completar. Se mantiene dominio puro, casos de uso en application y puertos en domain/ports.py. El usuario ratificó el alcance el 2026-10-15 y precisó anotaciones estándar de Python sin herramientas nuevas. Esta revisión documental no ha iniciado implementación ni ejecutado pruebas o diagnósticos de Pylance.

## Goals / Non-Goals

**Goals:** anotaciones de tipos completas y coherentes, ubicación persistida del locker y comparador reutilizable.

**Non-Goals:** dominio Parcel, extraer Dimensions, puente con Locker, API/wiring de cotizaciones y búsqueda postal. Sin colas, almacenamiento de cotizaciones ni clientes reales. No refactorizar disponibilidad para un puente que ya no se implementa.

## Decisions

### 1. Tipado del código existente y nuevo

Completar parámetros, retornos, colecciones, genéricos, opcionales y callbacks de funciones existentes afectadas y nuevas: Locker/Dimensions, servicios, HTTP, repositorios, recepción/custodia y composición. Usar anotaciones estándar de Python, tipos propios, Protocol y Awaitable[T], con narrowing explícito de valores opcionales y contratos coherentes entre puertos/adaptadores. Corregir incompatibilidades reales sin ocultarlas con Any o supresiones generales; casts puntuales requieren fundamento. Mantener 0001–0003 intactas.

Verificar mediante revisión de anotaciones/contratos y pruebas de comportamiento existentes. Revisar los diagnósticos de Pylance en VSCode cuando esté disponible, sin afirmar que se han ejecutado desde este entorno. No instalar ni configurar un checker nuevo, ni cambiar pyproject/uv.lock por tipado.

### 2. Ubicación nullable y compatible

Address contiene country_code=ES, postal_code de cinco ASCII y province/city/street/street_number textuales recortados no blancos; número como 12B o s/n. Coordinates contiene latitude [-90,90] y longitude [-180,180], ambas finitas, aceptando números JSON pero no booleanos/cadenas. Cada valor puede ser null independientemente; no hay geocodificación.

POST /lockers exige Address completo o location_id no nulo, o ambos. location_id sigue siendo agrupación opaca recortada, no vacía y sensible a mayúsculas; ahora puede ser null. Coordenadas solas no bastan para el alta. Históricos conservan alias y geografía null; respuestas de configuración incluyen los tres campos aunque sean null.

PATCH /lockers/{id} acepta un subconjunto no vacío de active/address/coordinates: omisión conserva, objeto reemplaza completo y null borra solo geografía; active no admite null. Validación y persistencia atómicas bajo el bloqueo existente, sin alterar alias/celdas/custodia. Se permite borrar Address tras el alta incluso sin alias.

Listado mantiene su filtro opcional location_id; sin filtro incluye también lockers sin alias. GET /lockers/availability conserva selector, respuesta y reglas actuales, sin metadatos/filtros nuevos. Un locker sin alias se gestiona por UUID/listado general y no aparece en consultas por alias; su selección geográfica de disponibilidad se resolverá después, sin fabricar etiquetas.

### 3. Contrato mínimo de transporte y puerto

Nuevo domain/shipping_quotes.py con valores inmutables/validados:

- ShippingQuoteRequest(origin_country_code, origin_postal_code, destination_country_code, destination_postal_code, weight_grams, dimensions). Países ES, CP de cinco ASCII, peso entero 1..30000 g y ejes enteros 1..2000 mm; booleanos inválidos. Importa Dimensions desde domain/lockers.py, cuyo rango general 1..2147483647 permanece. Se acepta esa dependencia temporal de módulo, sin usar la entidad Locker ni crear Parcel/ParcelSpec/ShippingRoute.
- ShippingOffer(service_code, price_cents, currency, transit_days_min, transit_days_max): céntimos enteros positivos/EUR y días naturales positivos desde futura expedición, min <= max. Sin clases Money/TransitEstimate.
- QuoteOffers(offers: tuple[ShippingOffer, ...]) no vacía con service_code únicos, o NoCoverage como respuesta válida de negocio. ProviderResult contiene provider_code, status QUOTED/NOT_COVERED/FAILED, offers y error_code.

ShippingProvider es un Protocol en domain/ports.py: propiedad code: str y async quote(request: ShippingQuoteRequest) -> QuoteOffers | NoCoverage. ProviderTechnicalError representa fallos técnicos esperados. Códigos de proveedor/servicio: cadenas no vacías, recortadas y sensibles a mayúsculas; no enum cerrado ni payload externo genérico.

### 4. Una utilidad de aplicación, sin composición HTTP

application/shipping_quote_use_cases.py implementa QuoteShipping(providers, ...) y async compare(request) -> tuple[ProviderResult, ...]. Copia proveedores a tupla y rechaza colección vacía, códigos inválidos o duplicados antes de llamar. Resultados ordenados por provider_code y ofertas por service_code. No estado agregado, ID, snapshot ni wrapper histórico. El caller instancia/injecta los proveedores explícitamente; no factory ni wiring en main.

QUOTED exige ofertas y error null; NOT_COVERED tiene ofertas vacías y error null; FAILED tiene ofertas vacías y PROVIDER_ERROR o PROVIDER_TIMEOUT. Entrada/configuración se valida antes de llamadas. Respuestas inválidas, ProviderTechnicalError y otras excepciones ordinarias del adaptador se normalizan a PROVIDER_ERROR conservando resultados ajenos, sin exponer payloads/credenciales.

Máximo 3 llamadas concurrentes por comparación; timeout de 2 s después de adquirir slot, con parámetros positivos inyectables para pruebas. Sin reintentos/deadline global. Cancelación del caller se propaga tras cancelar y esperar a hijos activos/en espera, sin trabajo desacoplado. Los adaptadores deben cooperar con cancelación; no se promete detener efectos externos futuros. La espera con N proveedores puede crecer por tandas.

Tres clases en adapters/providers/simulated_shipping.py implementan el puerto y devuelven una oferta cada una, sin ifs por proveedor en el comparador. Cuarto double con dos servicios prueba extensión sin cambiar lógica común. REST/SOAP/SDK serían futuros adaptadores responsables de traducción, autenticación y errores; no clientes actuales.

Con kg=ceil(max(weight_grams,ceil(volume_mm3/5000))/1000) y zone=0 si coinciden los dos primeros dígitos de ambos CP, 1 en otro caso:

| provider_code / service_code | Céntimos EUR | min = max días |
| --- | --- | --- |
| sim-economy / economy | 250 + 40*kg + 100*zone | 3 + zone |
| sim-standard / standard | 400 + 60*kg + 150*zone | 2 + zone |
| sim-express / express | 650 + 90*kg + 200*zone | 1 + zone |

Aritmética entera, sin red/azar/perfiles operativos. Límites: kg <= 1600 y precio <= 144850 céntimos. Ejemplo 1200 g, 200×150×100 mm y mismo prefijo postal: 330/520/830 céntimos y 3/2/1 días. Fallos/no cobertura/latencias se prueban con doubles.

### 5. Archivos y verificación

| Bloque | Archivos previstos |
| --- | --- |
| Tipado | funciones existentes afectadas y nuevas de backend/domain, application, adapters y main.py; sin cambios de dependencias/configuración |
| Locker | backend/domain/lockers.py, domain/ports.py, application/locker_use_cases.py, adapters/http/locker_schemas.py, locker_routes.py, adapters/database/sqlmodel_lockers.py y metadata/env si procede |
| Migración | nuevo backend/adapters/database/migrations/versions/0004_locker_geography.py |
| Comparador | nuevos backend/domain/shipping_quotes.py, application/shipping_quote_use_cases.py, adapters/providers/__init__.py y simulated_shipping.py |
| Pruebas | nuevo backend/tests/unit/test_shipping_quotes.py; adaptar unit/test_lockers.py, test_main.py y tests afectados por tipos; integration/test_locker_http.py, test_locker_repositories.py, test_migrations.py y test_postgresql.py |

README documenta geografía y ejemplo directo del comparador. No hay endpoint shipping, QuoteLockerShipping, domain/dimensions.py ni cambios funcionales de runtime/Compose. Unitarias sin servicios cubren cuarto proveedor/múltiples ofertas, configuración inválida, no cobertura/errores, límites y cancelación mediante barreras/eventos. PostgreSQL conserva aislamiento, fallo explícito sin skips, concurrencia/rollback de custodia y metadata; añade geografía y migración. Revisión sdd_reviewer antes de completar implementación.

Comandos desde backend:

```sh
uv run --extra dev python -m unittest discover -s tests/unit -t . -v
TEST_DATABASE_URL='<postgresql+asyncpg de pruebas>' uv run --extra dev python -m unittest discover -s tests/integration -t . -v -f
TEST_DATABASE_URL='<postgresql+asyncpg de pruebas>' uv run --extra dev python -m unittest discover -s tests -t . -v -f
```

## Risks / Trade-offs

- [Dimensions reside en lockers] → Reutilizar ese tipo sin duplicarlo; un dominio Parcel será otro cambio.
- [Locker sin alias] → Acceso por UUID/listado general; selección geográfica de disponibilidad aplazada.
- [Muchos proveedores] → Concurrencia/timeout por llamada, sin promesa de latencia total constante ni límite entre callers.

## Migration Plan

0004 sobre 0003 añade seis columnas Address nullable, latitude/longitude DOUBLE PRECISION nullable, checks de grupos completos/formatos/rangos y permite location_id null. Sin índice postal anticipado; conservar índice legacy. Sin backfill, tablas de cotización ni cambios a 0001–0003.

El migrador existente aplica 0004 antes de la API. Downgrade comprueba bajo bloqueo, antes de DDL, que toda geografía sea null y todos los aliases no nulos; entonces retira solo columnas/checks nuevos y restaura NOT NULL. Si no, rechaza sin alterar datos, estructura o revisión. Verificar upgrade poblado 0003→0004, rechazos por dirección/coordenadas/alias null, round trip y metadata; conservar explícita la prueba histórica 0002→0003.
