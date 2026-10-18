# Catálogo de ubicaciones reales para lockers DEMO

`spain-addresses.json` conserva 3423 registros aptos, con identificadores de las
52 códigos provinciales (50 provincias, Ceuta y Melilla), del inventario público
de estaciones de servicio MITECO. Las
ubicaciones/direcciones provienen de la fuente; los lockers **son ficticios** y no
se afirma que existan en esas instalaciones. La comprobación es documental, sin
inspección física independiente, geocodificación ni garantía de precisión catastral.

## Fuente fijada y reutilización

- Fuente oficial: **Ministerio para la Transición Ecológica y el Reto Demográfico
  (MITECO), precios de carburantes e información de estaciones de servicio**.
- API de origen:
  <https://sedeaplicaciones.minetur.gob.es/ServiciosRESTCarburantes/PreciosCarburantes/EstacionesTerrestres/>.
- Fecha declarada del snapshot: **17/10/2026 23:09:30**; 11 431 registros,
  12 149 531 bytes.
- Copia redistribuida fijada en el commit `5e9e8770d97ccb882127e6cd4cd60b302fc0a1d2`:
  <https://raw.githubusercontent.com/ioritzarroyuelos-ai/gasolineras-espana/5e9e8770d97ccb882127e6cd4cd60b302fc0a1d2/public/data/stations.json>.
- SHA-256 del snapshot:
  `91ee3c584c20563d60f5f9389dec011cef0e3d8a69a2fc89ab9cc5aadbf26f9b`.
- SHA-256 del extracto local:
  `5fa87d383d0f42cfa48f032098b0210731461e838f6fdd8e4107a345900d01d6`.
- Extracto preparado el **2026-10-18**. La ejecución no actualiza esta versión.

El `scripts/fetch-prices.mjs` del mismo commit se comprobó documentalmente:
descarga el endpoint oficial anterior y escribe `JSON.stringify(all)` en el
snapshot completo, antes de producir otros archivos derivados. En esta red la
API oficial no es accesible; se comprobó la copia fijada, su hash y el código de
adquisición. Esto no constituye una consulta contemporánea independiente al
servidor oficial ni una verificación física de cada ubicación.

El [aviso legal de MITECO](https://www.miteco.gob.es/es/atencion-al-ciudadano/aviso-legal.html)
permite reutilizar la información con atribución a la fuente y fecha, sin alterar
su sentido ni insinuar respaldo institucional. Se conservan esos datos aquí y en
el catálogo. La licencia MIT del **código** del mirror no se aplica por ello a los
datos oficiales; no se presenta el extracto como dominio público ni como información
propia o respaldada por el Ministerio. Al redistribuirlo, conserva esta atribución,
fecha y distinción entre ubicaciones de la fuente y lockers DEMO.

## Selección y correspondencia de campos

Cada registro mantiene sin modificar `IDEESS`, `IDProvincia`, `Provincia`,
`Municipio`, `Localidad`, `Dirección`, `C.P.`, `Latitud` y `Longitud (WGS84)`.
No se incluyen precios, horarios ni marcas. La cabecera `source` conserva origen,
commit de la copia, fecha, hash y tamaño/cantidad del snapshot completo.

Solo se admiten campos completos, `IDEESS` numérico único, `IDProvincia` de 01 a
52 y CP textual de cinco dígitos cuyo prefijo coincide con esa provincia.
`Dirección` debe coincidir completamente con:

```text
(CALLE|AVENIDA|PLAZA|PASEO|RONDA|TRAVESIA|TRAVESÍA|CARRER|AVINGUDA|RAMBLA) [^,]+,\s*[0-9]+[A-Za-z]?
```

La única coma separa calle y portal explícito. Se excluyen carreteras, kilómetros,
`S/N`, portales ambiguos y direcciones incompletas. Por ejemplo, `CR CM-332, 46,4`
no se convierte en portal 4. La latitud/longitud debe ser decimal finita, dentro
del ámbito amplio de España (latitud 27..44, longitud -19..5), sin desplazamientos
ni redondeos; esto excluye el registro IDEESS **12883**, que declara **0,0**.
No se usa Natural Earth para descartar ubicaciones costeras de esta fuente.

| Payload público | Campo fuente |
| --- | --- |
| `street` / `street_number` | Partes inequívocas de `Dirección` |
| `postal_code` | `C.P.` como texto, conservando ceros |
| `city` | `Localidad`; `Municipio` también se preserva para auditoría |
| `province` | `Provincia` |
| `country_code` | `ES`, ámbito nacional de la fuente y provincia validada |
| `latitude` / `longitude` | `Latitud` / `Longitud (WGS84)`, coma decimal convertida a punto |

Los pares permanecen inseparables: no se asigna un CP de este catálogo a un punto
aleatorio. Los metadatos de procedencia no se envían a `POST /lockers`.

## Reproducir el extracto sin red

Con la copia exacta de `stations.json` ya descargada, desde `backend/`:

```bash
python3 -m scripts.data.extract_addresses /ruta/stations.json
sha256sum scripts/data/spain-addresses.json
python3 scripts/seed_lockers.py --dry-run
```

El extractor comprueba el SHA-256, fecha y cantidad del snapshot antes de escribir.
Guarda solo los campos fuente anteriores, en el orden original, con JSON UTF-8
compacto y un salto de línea final. Tanto el extractor como el seed usan la
biblioteca estándar. El seed valida el catálogo entero antes de cualquier POST.

Con `random.Random(seed)` se baraja una copia del catálogo por ronda, sin repetir
un registro antes de agotar esa ronda. Al superar 3423 registros se permite otra
ronda y repeticiones; distintos identificadores fuente también pueden compartir
ubicación. La semilla reproduce el orden/payload con esta versión, no los UUID que
asigna la API. La distribución no es uniforme sobre el territorio ni reserva cupos
por provincia. No se actualizan, borran ni completan los lockers ya existentes.
