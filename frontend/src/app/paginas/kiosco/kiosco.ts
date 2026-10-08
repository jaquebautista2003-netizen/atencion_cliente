import { Component, computed, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';

import { Turno } from '../../core/modelos';
import { TurnosService } from '../../core/turnos.service';

/** Vista para el cliente: un solo botón para sacar su turno. */
@Component({
  selector: 'app-kiosco',
  imports: [RouterLink],
  templateUrl: './kiosco.html',
  styleUrl: './kiosco.css',
})
export class Kiosco {
  private readonly svc = inject(TurnosService);

  protected readonly ticket = signal<Turno | null>(null);
  protected readonly ocupado = signal(false);
  protected readonly error = signal<string | null>(null);
  private limpiar?: ReturnType<typeof setTimeout>;

  /** Estado en vivo del ticket entregado (cambia cuando una mesa lo llama). */
  protected readonly vivo = computed(() => {
    const t = this.ticket();
    if (!t) return null;
    const mesa = this.svc.mesas().find((m) => m.turno?.id === t.id);
    if (mesa) return { mesa: mesa.id, posicion: null };
    const pos = this.svc.fila().findIndex((f) => f.id === t.id);
    return { mesa: null, posicion: pos >= 0 ? pos + 1 : t.posicion };
  });

  protected readonly enFila = computed(() => this.svc.fila().length);

  protected async tomar() {
    this.ocupado.set(true);
    this.error.set(null);
    try {
      this.ticket.set(await this.svc.tomarTurno());
      clearTimeout(this.limpiar);
      this.limpiar = setTimeout(() => this.ticket.set(null), 10000);
    } catch (e) {
      this.error.set((e as Error).message);
    } finally {
      this.ocupado.set(false);
    }
  }

  protected listo() {
    clearTimeout(this.limpiar);
    this.ticket.set(null);
  }
}
