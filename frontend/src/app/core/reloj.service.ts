import { Injectable, signal } from '@angular/core';

/** Reloj compartido que avanza cada segundo para los contadores en vivo. */
@Injectable({ providedIn: 'root' })
export class RelojService {
  readonly ahora = signal(Date.now());

  constructor() {
    setInterval(() => this.ahora.set(Date.now()), 1000);
  }
}
