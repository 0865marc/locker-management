import { availableLockers, type AvailableLocker } from './lockers';
export function publicApiUrl(
  config: string | undefined,
  pageProtocol: string,
  path: string,
): string {
  try {
    if (!config?.trim()) throw new Error();
    const url = new URL(config);
    if (
      !['http:', 'https:'].includes(url.protocol) ||
      url.username ||
      url.password ||
      url.search ||
      url.hash ||
      (pageProtocol === 'https:' && url.protocol !== 'https:')
    )
      throw new Error();
    url.pathname = `${url.pathname.replace(/\/+$/, '')}/${path}`;
    return url.href;
  } catch {
    throw new Error(
      'La conexión con el servicio de lockers no está configurada correctamente. Contacta con el responsable del sitio.',
    );
  }
}
export function lockersUrl(
  config: string | undefined,
  pageProtocol: string,
): string {
  return publicApiUrl(config, pageProtocol, 'lockers');
}
export async function loadLockers(
  config: string | undefined,
  pageProtocol: string,
  fetcher: typeof fetch = fetch,
): Promise<AvailableLocker[]> {
  const url = lockersUrl(config, pageProtocol);
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 5000);
  try {
    const response = await fetcher(url, {
      method: 'GET',
      credentials: 'omit',
      cache: 'no-store',
      signal: controller.signal,
    });
    if (!response.ok)
      throw new Error(
        `El servicio de lockers no ha podido completar la consulta (HTTP ${response.status}).`,
      );
    let payload: unknown;
    try {
      payload = await response.json();
    } catch {
      if (controller.signal.aborted) throw new Error();
      throw new Error(
        'El servicio de lockers ha devuelto una respuesta que no se puede leer.',
      );
    }
    return availableLockers(payload);
  } catch (error) {
    if (controller.signal.aborted)
      throw new Error(
        'La consulta ha superado los cinco segundos. Vuelve a intentarlo.',
      );
    if (error instanceof TypeError)
      throw new Error(
        'No se ha podido conectar con el servicio de lockers. Comprueba la conexión o inténtalo de nuevo.',
      );
    throw error;
  } finally {
    clearTimeout(timeout);
  }
}
