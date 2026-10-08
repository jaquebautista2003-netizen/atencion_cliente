import { Component, computed, effect, inject, signal, untracked } from '@angular/core';
import { RouterLink } from '@angular/router';

import { Llamado } from '../../core/modelos';
import { RelojService } from '../../core/reloj.service';
import { TurnosService } from '../../core/turnos.service';

/** Pantalla para TV: muestra qué turno pasa a qué mesa y lo anuncia por voz. */
@Component({
  selector: 'app-pantalla',
  imports: [RouterLink],
  templateUrl: './pantalla.html',
  styleUrl: './pantalla.css',
})
export class Pantalla {
  protected readonly svc = inject(TurnosService);
  private readonly reloj = inject(RelojService);

  protected readonly sonido = signal(false);
  protected readonly destacado = signal<Llamado | null>(null);
  private timer?: ReturnType<typeof setTimeout>;
  private audio?: AudioContext;

  protected readonly horaActual = computed(() =>
    new Date(this.reloj.ahora()).toLocaleTimeString('es-MX', { hour: '2-digit', minute: '2-digit' }),
  );
  protected readonly proximos = computed(() => this.svc.fila().slice(0, 8));

  constructor() {
    effect(() => {
      const llamado = this.svc.nuevoLlamado();
      if (!llamado) return;
      untracked(() => this.anunciar(llamado));
    });
  }

  protected activarSonido() {
    this.audio = new AudioContext();
    this.sonido.set(true);
    this.campana();
  }

  private anunciar(l: Llamado) {
    this.destacado.set(l);
    clearTimeout(this.timer);
    this.timer = setTimeout(() => this.destacado.set(null), 7000);
    if (!this.sonido()) return;

    this.campana();
    const [letra, num] = l.codigo.split('-');
    const voz = new SpeechSynthesisUtterance(
      `Turno ${letra} ${Number(num)}, pase a la mesa ${l.mesa_id}`,
    );
    voz.lang = 'es-MX';
    voz.rate = 0.95;
    setTimeout(() => speechSynthesis.speak(voz), 700);
  }

  /** Ding-dong generado con Web Audio (sin archivos de audio). */
  private campana() {
    const ctx = this.audio;
    if (!ctx) return;
    [880, 660].forEach((freq, i) => {
      const osc = ctx.createOscillator();
      const gan = ctx.createGain();
      const t = ctx.currentTime + i * 0.35;
      osc.frequency.value = freq;
      osc.type = 'sine';
      gan.gain.setValueAtTime(0.0001, t);
      gan.gain.exponentialRampToValueAtTime(0.35, t + 0.02);
      gan.gain.exponentialRampToValueAtTime(0.0001, t + 0.6);
      osc.connect(gan).connect(ctx.destination);
      osc.start(t);
      osc.stop(t + 0.65);
    });
  }
}
