# Geografía terrestre de España para datos sintéticos

`spain.geojson` es únicamente la geometría GeoJSON `MultiPolygon` de la entidad
`ADM0_A3 == "ESP"` de **Natural Earth**, Admin 0 Countries, escala 1:10m.
Contiene 23 polígonos, incluidos península, Baleares, Canarias, Ceuta, Melilla y
Llívia. Los anillos interiores se conservan sin simplificar ni redondear.

- Repositorio: <https://github.com/nvkelso/natural-earth-vector>.
- Commit fijado: `ca96624a56bd078437bca8184e78163e5039ad19`.
- Fuente exacta: <https://raw.githubusercontent.com/nvkelso/natural-earth-vector/ca96624a56bd078437bca8184e78163e5039ad19/geojson/ne_10m_admin_0_countries.geojson>.
- Extraído el 2026-10-17 mediante selección de esa entidad y serialización de su
  campo `geometry` con `json.dumps(geometry, separators=(',', ':')) + '\n'`.
- SHA-256 fuente: `239eec57ac17f100a11e2536cffc56752c318b50ae765b0918ff7aab4ce8f255`.
- SHA-256 extracto: `c6a659d690478277c1148227b07170bafe7a23939940cde0d7f31496a02e47a6`.

Natural Earth distribuye sus datos en **dominio público**:
<https://www.naturalearthdata.com/about/terms-of-use/>. La procedencia se conserva
para permitir auditar y reproducir el dato de referencia.

Son límites generalizados para cartografía, no precisión catastral. El generador
solo comprueba pertenencia a esta geometría, incluidos sus huecos, también después
de redondear a seis decimales. Las posiciones y alias `DEMO-<seed>-<índice>` son
sintéticos: no representan instalaciones ni direcciones reales. El muestreo por
rechazo no garantiza cantidades iguales por isla o territorio.

La geografía se lee localmente: ni el generador ni sus pruebas necesitan descargar
límites, usar un geocodificador o comunicarse con un proveedor cartográfico.
