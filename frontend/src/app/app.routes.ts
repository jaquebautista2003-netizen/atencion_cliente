import { Routes } from '@angular/router';

export const routes: Routes = [
  {
    path: '',
    title: 'Panel de atención',
    loadComponent: () => import('./paginas/panel/panel').then((m) => m.Panel),
  },
  {
    path: 'kiosco',
    title: 'Tomar turno',
    loadComponent: () => import('./paginas/kiosco/kiosco').then((m) => m.Kiosco),
  },
  {
    path: 'pantalla',
    title: 'Pantalla de turnos',
    loadComponent: () => import('./paginas/pantalla/pantalla').then((m) => m.Pantalla),
  },
  { path: '**', redirectTo: '' },
];
