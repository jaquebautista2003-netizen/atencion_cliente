/** Convierte segundos a "3 min 20 s" o "45 s". */
export function duracion(seg: number | null | undefined): string {
  if (seg == null) return '—';
  const s = Math.round(seg);
  if (s < 60) return `${s} s`;
  const m = Math.floor(s / 60);
  const r = s % 60;
  return r ? `${m} min ${r} s` : `${m} min`;
}

/** Hora local "08:42" a partir de un ISO. */
export function hora(iso: string | null | undefined): string {
  if (!iso) return '';
  return new Date(iso).toLocaleTimeString('es-MX', { hour: '2-digit', minute: '2-digit' });
}

/** Segundos transcurridos desde un ISO hasta ahora. */
export function desde(iso: string | null | undefined, ahora = Date.now()): number | null {
  if (!iso) return null;
  return Math.max(0, (ahora - new Date(iso).getTime()) / 1000);
}
