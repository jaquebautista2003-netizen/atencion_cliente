import { Component, inject, signal } from '@angular/core';

import { duracion, desde, hora } from '../../core/formato';
import { Mesa, Turno } from '../../core/modelos';
import { RelojService } from '../../core/reloj.service';
import { TurnosService } from '../../core/turnos.service';

@Component({
  selector: 'app-panel',
  templateUrl: './panel.html',
  styleUrl: './panel.css',
})
export class Panel {
  protected readonly svc = inject(TurnosService);
  protected readonly reloj = inject(RelojService);

  protected readonly ocupado = signal(false);
  protected readonly ultimoTicket = signal<Turno | null>(null);
  protected readonly aviso = signal<string | null>(null);
  private avisoTimer?: ReturnType<typeof setTimeout>;

  protected readonly duracion = duracion;
  protected readonly hora = hora;

  protected transcurrido(iso: string | null | undefined): string {
    return duracion(desde(iso, this.reloj.ahora()));
  }

  protected async tomarTurno() {
    await this.accion(async () => {
      const t = await this.svc.tomarTurno();
      this.ultimoTicket.set(t);
      this.mostrar(
        t.mesa_id ? `${t.codigo} → pase a Mesa ${t.mesa_id}` : `${t.codigo} en fila (posición ${t.posicion})`,
      );
    });
  }

  protected finalizar(mesa: Mesa) {
    return this.accion(() => this.svc.finalizarAtencion(mesa.id));
  }

  protected alternarMesa(mesa: Mesa) {
    return this.accion(() => this.svc.cambiarMesa(mesa.id, !mesa.activa));
  }

  protected cancelar(turno: Turno) {
    if (!confirm(`¿Quitar el turno ${turno.codigo} de la fila?`)) return;
    return this.accion(() => this.svc.cancelarTurno(turno.id));
  }

  protected reiniciar() {
    if (!confirm('Se borrarán todos los turnos y la numeración volverá a A-001. ¿Continuar?')) return;
    return this.accion(async () => {
      await this.svc.reiniciar();
      this.ultimoTicket.set(null);
    });
  }

  private async accion(fn: () => Promise<unknown>) {
    this.ocupado.set(true);
    try {
      await fn();
    } catch (e) {
      this.mostrar((e as Error).message);
    } finally {
      this.ocupado.set(false);
    }
  }

  private mostrar(msg: string) {
    clearTimeout(this.avisoTimer);
    this.aviso.set(msg);
    this.avisoTimer = setTimeout(() => this.aviso.set(null), 3500);
  }
}
