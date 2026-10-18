# Spec Delta

## ADDED Requirements

### Requirement: Identify the Cloudflare acceptance HTTP client

El cliente HTTP de aceptación Cloudflare SHALL enviar `User-Agent: LockerManagementAcceptance/0.1` en todas sus peticiones. SHALL conservar métodos, cuerpos, Content-Type, proxies, verificación TLS, timeout y presupuesto de peticiones existentes.

#### Scenario: Identify reads and writes consistently
- **WHEN** la campaña envía una petición GET o una petición con cuerpo mediante su cliente HTTP
- **THEN** incluye el identificador propio estable y conserva el método, el cuerpo y las restantes opciones de transporte
- **AND** superar un GET de diagnóstico no acredita la campaña completa ni las cuotas Free
