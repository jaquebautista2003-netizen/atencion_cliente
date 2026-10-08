import { HttpClient, HttpErrorResponse } from '@angular/common/http';
import { DestroyRef, Injectable, computed, inject, signal } from '@angular/core';
import { firstValueFrom } from 'rxjs';

import { EstadoSistema, Llamado, MensajeWs, Turno } from './modelos';

/**
 * Fuente única de verdad del frontend.
 * Recibe el estado en tiempo real por WebSocket (con reconexión automática)
 * y expone las acciones del sistema vía HTTP.
 */
@Injectable({ providedIn: 'root' })
export class TurnosService {
  private readonly http = inject(HttpClient);
  private readonly api = '/api';

  private ws?: WebSocket;
  private reintento?: ReturnType<typeof setTimeout>;
  private ping?: ReturnType<typeof setInterval>;
  private intentos = 0;

  readonly estado = signal<EstadoSistema | null>(null);
  readonly conectado = signal(false);
  /** Último turno llamado a una mesa (para anunciarlo en pantalla). */
  readonly nuevoLlamado = signal<Llamado | null>(null);

  readonly mesas = computed(() => this.estado()?.mesas ?? []);
  readonly fila = computed(() => this.estado()?.fila ?? []);
  readonly llamados = computed(() => this.estado()?.ultimos_llamados ?? []);
  readonly stats = computed(() => this.estado()?.estadisticas ?? null);

  constructor() {
    this.conectar();
    inject(DestroyRef).onDestroy(() => this.cerrar());
  }

  // ---------------------------------------------------------------- acciones
  tomarTurno(): Promise<Turno> {
    return this.ejecutar(this.http.post<Turno>(`${this.api}/turnos`, {}));
  }

  finalizarAtencion(mesaId: number) {
    return this.ejecutar(this.http.post(`${this.api}/mesas/${mesaId}/finalizar`, {}));
  }

  cambiarMesa(mesaId: number, activa: boolean) {
    return this.ejecutar(this.http.patch(`${this.api}/mesas/${mesaId}`, { activa }));
  }

  cancelarTurno(turnoId: number) {
    return this.ejecutar(this.http.delete(`${this.api}/turnos/${turnoId}`));
  }

  consultarTurno(turnoId: number): Promise<Turno> {
    return this.ejecutar(this.http.get<Turno>(`${this.api}/turnos/${turnoId}`));
  }

  reiniciar() {
    return this.ejecutar(this.http.post(`${this.api}/reiniciar`, {}));
  }

  // --------------------------------------------------------------- tiempo real
  private conectar() {
    const protocolo = location.protocol === 'https:' ? 'wss' : 'ws';
    this.ws = new WebSocket(`${protocolo}://${location.host}/ws`);

    this.ws.onopen = () => {
      this.conectado.set(true);
      this.intentos = 0;
      this.ping = setInterval(() => this.ws?.send('ping'), 25000);
    };

    this.ws.onmessage = (e) => {
      const msg: MensajeWs = JSON.parse(e.data);
      this.detectarLlamado(msg.estado);
      this.estado.set(msg.estado);
    };

    this.ws.onclose = () => {
      this.conectado.set(false);
      clearInterval(this.ping);
      // Reconexión con espera progresiva (1s, 2s, 4s ... máx 10s)
      const espera = Math.min(1000 * 2 ** this.intentos++, 10000);
      this.reintento = setTimeout(() => this.conectar(), espera);
      // Mientras tanto, mantener el estado actualizado por HTTP
      this.refrescar();
    };
  }

  private async refrescar() {
    try {
      const estado = await firstValueFrom(this.http.get<EstadoSistema>(`${this.api}/estado`));
      this.estado.set(estado);
    } catch {
      /* backend no disponible: se reintenta con el WebSocket */
    }
  }

  private detectarLlamado(nuevo: EstadoSistema) {
    const anterior = this.estado();
    const ultimo = nuevo.ultimos_llamados[0];
    if (!anterior || !ultimo) return;
    const previo = anterior.ultimos_llamados[0];
    if (!previo || previo.codigo !== ultimo.codigo || previo.llamado_en !== ultimo.llamado_en) {
      this.nuevoLlamado.set(ultimo);
    }
  }

  private cerrar() {
    clearTimeout(this.reintento);
    clearInterval(this.ping);
    if (this.ws) {
      this.ws.onclose = null;
      this.ws.close();
    }
  }

  private async ejecutar<T>(peticion: import('rxjs').Observable<T>): Promise<T> {
    try {
      return await firstValueFrom(peticion);
    } catch (e) {
      const err = e as HttpErrorResponse;
      throw new Error(err.error?.detail ?? 'No se pudo conectar con el servidor');
    }
  }
}
