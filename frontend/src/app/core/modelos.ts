export type EstadoTurno = 'espera' | 'atendiendo' | 'finalizado';

export interface Turno {
  id: number;
  numero: number;
  codigo: string;
  estado: EstadoTurno;
  mesa_id: number | null;
  creado_en: string;
  llamado_en: string | null;
  finalizado_en: string | null;
  posicion?: number | null;
}

export interface Mesa {
  id: number;
  nombre: string;
  activa: boolean;
  ocupada: boolean;
  turno: Turno | null;
}

export interface Llamado {
  codigo: string;
  mesa_id: number;
  llamado_en: string;
}

export interface Estadisticas {
  en_espera: number;
  en_atencion: number;
  atendidos: number;
  espera_promedio_seg: number | null;
  atencion_promedio_seg: number | null;
}

export interface EstadoSistema {
  mesas: Mesa[];
  fila: Turno[];
  ultimos_llamados: Llamado[];
  estadisticas: Estadisticas;
  actualizado_en: string;
}

export interface MensajeWs {
  evento: string;
  datos: Record<string, unknown>;
  estado: EstadoSistema;
}
