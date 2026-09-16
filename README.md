# LCDGlance

**Monitor de sistema, panel de agentes y mascotas animadas** para el **LCD monocromo
160×43** y la **iluminación RGB** del teclado Logitech **G510**, sobre Logitech Gaming
Software (LGS 8.57).

> Una pantalla retro sci-fi con reloj en tiempo real, resumen instantáneo (**NOW**),
> diagnóstico de conexiones y tres mascotas pixel-art dibujadas a mano — una por cada
> fuente que vigila. **v10** añade un supervisor de conexiones, scheduler por deadlines
> y tarjetas de evento.

![Mascotas: PC, CLAW, CODEX](docs/screens/hero-mascots.png)

---

## Vista general

![Todas las páginas](docs/screens/pages-mosaic.png)

LCDGlance convierte el LCD del G510 (monocromo, 1-bit) en un panel de control vivo:

- **Tres fuentes vigiladas** — tu PC, el gateway OpenClaw y Codex — cada una con su
  propia mascota animada y su color RGB.
- **Reloj en tiempo real (HH:MM)** en la cabecera de *todas* las páginas, alineado a la
  derecha y sin solapar el título ni el indicador de página.
- **Auto-foco**: si un agente termina o empieza una descarga, el panel salta solo a la
  escena relevante y vuelve a tu página.
- **7–8 páginas** de datos (ver abajo) + overlays de **Download** y **Overview**.

---

## Mascotas

Cada fuente tiene su propio personaje **dibujado a mano** con primitivas vectoriales
(no sprites pixel-art, que se pixelan mal en un panel 1-bit), con animaciones
independientes:

| Mascota | Fuente | Dibujo | Color RGB |
|---|---|---|---|
| **CLAW** | OpenClaw | cangrejo: caparazón, pinzas, patas, ojos en tallos | cian |
| **CODEX** | Codex (opcional) | robot: antena con LED, visor con escáner, boca de rejilla | verde |
| **PC** | tu equipo | monitor con cara y peana | azul |

**Animaciones** (por mascota):

- Respiración vertical suave en reposo, rebote enérgico cuando está ocupada, temblor
  frenético en alarma.
- Parpadeo cada 2–4 s y mirada de reojo aleatoria.
- Destellos de energía **pulsantes** que radian del cuerpo mientras la fuente trabaja.
- LED intermitente de antena (CODEX) y barrido del visor.

La mascota **destacada** es la del agente ocupado (o OpenClaw si no hay ninguno), y su
color tiñe el teclado RGB.

---

## Páginas

| # | Página | Contenido | Captura |
|---|---|---|---|
| 1 | **NOW** | resumen instantáneo: PC, CLAW y CODEX (red en la cabecera) | ![Now](docs/screens/now.png) |
| 2 | **Mascot** | mascota + estado/modelo/cuota por fuente (B3 cambia de mascota) | ![Mascot](docs/screens/mascot-claw.png) |
| 3 | **Sources** | PC / CLAW / CODEX con estado supervisor (OK/BUSY/STALE/OFFLINE) | ![Sources](docs/screens/sources.png) |
| 4 | **System** | CPU (+temp) / RAM (usada/total) / disco (libre), en unidades reales | ![System](docs/screens/system.png) |
| 5 | **Network** | subida/bajada, pico, sparkline y estado de descarga | ![Network](docs/screens/network.png) |
| 6 | **OpenClaw** | gateway con estado supervisor, agentes, latencia y backoff | ![OpenClaw](docs/screens/openclaw.png) |
| 7 | **Codex** | terminal física del agente: WORKING / IDLE / OFFLINE | ![Codex](docs/screens/codex.png) |
| 8 | **Activity** | timeline de eventos recientes (tareas, descargas, alertas) | ![Activity](docs/screens/activity.png) |
| 9 | **Alerts** | alertas con modo **invertido** para críticas (CPU>95 %, temp>90°) | ![Alerts](docs/screens/alerts-active.png) |
| 10 | **VPS** | servidor remoto SSH (si se configura `vps_config.json`) | ![VPS](docs/screens/vps.png) |
| ★ | **Download** | solo con descarga real: progreso, ETA y estado | ![Download](docs/screens/download.png) |
| ◈ | **Scouter** | **B3 mantenido**: power level animado (0→PL en 300 ms) + análisis | ![Overview](docs/screens/overview.png) |
| ☾ | **Screensaver** | reloj + mascota dormida + interlude "NOMINAL" cada 12 s | ![Screensaver](docs/screens/screensaver.png) |
| ⚙ | **Quick menu** | **B3+B4**: acciones del contexto, invertido solo en la opción activa | ![Menu](docs/screens/quickmenu.png) |
| ✉ | **Event card** | notificación a pantalla completa al terminar tarea/build/descarga | ![Event](docs/screens/eventcard.png) |

### Alertas activas

Cuando hay problemas la página Alerts pasa de "clear" a una lista con iconos de
severidad:

| Sin alertas | Con alertas |
|---|---|
| ![Alertas clear](docs/screens/alerts-clear.png) | ![Alertas activas](docs/screens/alerts-active.png) |

Si el nivel es crítico (CPU > 95 %, temperatura > 90°), el panel entero se invierte
para que no puedas ignorarlo.

### Scouter — B3 mantenido

Mantén **B3** medio segundo para ver el scouter: un overlay con la lectura completa del
sistema (barras CPU/RAM/disco, temperatura, plano de poder, gateway, agentes activos y
Codex). Se cierra solo a los 8 segundos y vuelve a tu página.

![Overview](docs/screens/overview.png)

### Screensaver — pantalla de descanso

Tras **90 segundos sin pulsar nada y sin que haya trabajo**, el panel pasa a la pantalla
de descanso: reloj grande, mascota dormida y `Zzz`, refrescando a solo 2 FPS.

No es un salvapantallas ciego: **cualquier actividad lo despierta** —

- agentes trabajando (OpenClaw o Codex),
- una descarga en curso,
- CPU por encima del umbral,
- un evento reciente (tarea terminada).

Al despertar salta directamente a la **mascota reaccionando** durante 6 s, para que veas
*qué* se está haciendo y no solo *que* pasa algo. Una pulsación de botón también lo
cierra, y el menú rápido (`B3+B4`) permite activarlo o desactivarlo a mano.

Cada **12 segundos** interrumpe brevemente la calma con un interludio **`NOMINAL`** de
2,5 s: un tick grande y CPU / RAM / red, para saber de un vistazo que todo sigue bien.

![Screensaver](docs/screens/screensaver.png)

### Toasts — avisos breves

Para eventos menores (un agente terminado, un poll forzado) hay un **toast**: una
banda de 10 px en la parte superior que se superpone a la página sin cambiarla. El
texto va en negro sobre la barra blanca, y los toasts repetidos se deduplican.

![Toast](docs/screens/toast.png)

### Event cards — notificaciones de hardware

Cuando algo termina de verdad (una tarea de agente, una build, una descarga), no salta
un toast diminuto: la **tarjeta de evento** ocupa el panel entero durante ~2,5 s con
icono, título y detalle. Es una notificación de hardware, no un cambio de página.

![Event card](docs/screens/eventcard.png)

Eventos que generan tarjeta:

| Evento | Icono | Contenido |
|---|---|---|
| Tarea de agente OK | ✓ | `TASK COMPLETE` + nombre |
| Tarea de agente fallida | ! | `TASK FAILED` + «see Alerts page» |
| Descarga completada | ↓ | `DOWNLOAD COMPLETE` + fichero |

### Diagnostics — estado de cada conexión

En el menú rápido (`B3+B4` → **Diagnostics**) hay una página de diagnóstico que muestra
el estado **real** de cada componente: `online`, `stale`, `connecting` u `offline`, con
icono, edad del estado, latencia y contador de fallos.

![Diagnostics](docs/screens/diagnostics.png)

Es la vista que faltaba para saber *por qué* algo no responde, en vez de adivinar.

---

## Botones

Toque corto vs. **mantener pulsado** (~0,6 s) — cada botón tiene dos funciones:

| Botón | Toque corto | Mantener pulsado |
|---|---|---|
| **B1** | Página anterior | Saltar a la 1ª página |
| **B2** | Página siguiente | Saltar a la última página |
| **B3** | **Cambiar de mascota**: salta a Mascot y cicla AUTO → PC → CLAW → CODEX | Scouter (plano de poder, temperaturas, gateway) 8 s |
| **B4** | Flash blanco + toggle alerta RGB manual | Flash largo + estado ALERT 1,5 s |
| **B1+B2** | Avance rápido de página (3 saltos) | — |
| **B3+B4** | — | Menú rápido de acciones |

**Atajos mantenidos (≥0,5 s).** Un hold nunca dispara si su compañero de combo también
está pulsado, así `B1+B2` y `B3+B4` siguen siendo inequívocos.

En el menú rápido, `B3` selecciona y `B4` cancela. La opción **Diagnostics** abre la
página de estado de conexiones; cualquier botón la cierra.

**B3 — cambiar de mascota.** Cada pulsación avanza a la siguiente mascota y muestra un
aviso breve (`MASCOT PC`, `MASCOT CLAW`, `MASCOT CODEX`, `MASCOT AUTO`). En `AUTO` el panel
elige solo la mascota de la fuente ocupada. El color RGB del teclado sigue a la mascota
seleccionada.

**Auto-foco** — sin tocar nada:

- Un agente termina → salta a su mascota reaccionando ~8 s.
- Una descarga empieza → vista Download; al acabar, vuelve a tu página.

**Indicador de página**: puntos en la esquina superior derecha (el relleno = actual).

---

## RGB

Motor por prioridad, con respiración y atenuación nocturna automática (23:00–08:00 al
35 %) más overrive manual por **B4 mantenido**:

```
alerta manual > agente falló > agente OK > descarga > agentes activos
> CPU>90 % > RAM>90 % > disco>95 % > color de la mascota activa
```

La **atenuación nocturna es automática** (23:00–08:00 al 35 %), no hay botón que la active.
El **B4 mantenido** refuerza la alerta: flash largo + estado ALERT durante 1,5 s.

---

## Instalación

1. Copia la carpeta a `C:\Users\<usuario>\lcdglance\`.

2. Normaliza la config de LGS (deja solo el applet correcto), **con LGS cerrado**:

   ```bat
   python configure.py
   ```

3. Arranca la aplicación desacoplada:

   ```bat
   python launch_detached.py
   ```

**Auto-arranque**: copia `start_lcdglance.vbs` a
`%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\`.

> Requisitos: Windows + Logitech Gaming Software 8.57, Python 3.10+ y las librerías
> `pillow` y `psutil`. Para OpenClaw/Codex necesitas la sonda `lcd-probe` en WSL.

---

## Ficheros

```
lcdglance.py         aplicación principal (arranque + bucle principal)
verify.py            autocomprobación: render de todas las páginas sin solapes
preview.py           genera TODAS las capturas de docs/screens/ (--out para cambiar)
launch_detached.py   lanzador desacoplado (pythonw + DETACHED_PROCESS)
configure.py         normaliza la config de applets de LGS
configure_keys.py    configuración de colores RGB por tecla
preview.py           renderiza páginas/mascotas a PNG para revisar sin teclado
vps_config.json      configuración del VPS remoto (opcional)
start_lcdglance.vbs  auto-arranque (copiar a Startup)
restart.bat          reinicia la aplicación
restart_lgs.bat      reinicia LGS + la aplicación

src/
  supervisor/ core.py                  ONLINE → STALE → OFFLINE + backoff
  hardware/  lcd.py, led.py            controladores de las DLLs de Logitech
  sources/   system, openclaw,          recogida de datos (hilos aparte)
             download, vps
  render/    gfx.py, bitmap.py,        lienzo 1-bit, binarización LUT, fuente
             bitmap_font.py            bitmap nativa (disponible, no cableada)
  anim/      controller, scene,         máquina de estados, escenas,
             transition, toast,        transiciones, avisos,
             eventcard                 tarjetas de evento a pantalla completa
  mascots/   mascot.py, sprites.py      mascotas procedurales (+ sprites opt-in),
             interactions, sources     escenas compartidas, lógica de fuentes
  pages/     una por pantalla           Now, Mascot, Sources, System, Network,
                                        OpenClaw, Codex, Activity, Alerts, VPS,
                                        Download, Status, Screensaver, QuickMenu,
                                        Diagnostics
  ui/        buttons, rgb, applets      botones, motor RGB, limpieza de applets
  util/      constants, text, ringbuf   ajustes, helpers de texto, historial
```

### Fiabilidad — supervisor de conexiones

Cada componente vigilado (LCD, RGB, OpenClaw, VPS) tiene un `ConnectionSupervisor` con
una máquina de estados real:

```
CONNECTING → ONLINE → STALE → OFFLINE → (backoff 1,2,4,8,15,30 s) → CONNECTING
```

- Un fallo transitorio baja a **STALE** (sigue usable, pero se avisa).
- Dos fallos consecutivos bajan a **OFFLINE** y arranca el backoff.
- Un solo éxito desde cualquier estado vuelve a **ONLINE**.

Esto elimina dos bugs clásicos: morir en silencio (el componente dejaba de responder sin
que nadie lo supiera) y marcar `offline` por un único timeout puntual.

### Rendimiento — scheduler por deadlines

El bucle principal ya no duerme un intervalo fijo: calcula el **próximo deadline**
(input a 50 Hz, render al FPS del estado actual) y duerme justo hasta el más cercano,
con un mínimo de 5 ms. Así los 12/24 FPS se alcanzan de verdad cuando hay animación, y
en reposo no se quema CPU.

### Capturas

Todas las imágenes de `docs/screens/` las genera `preview.py`, que renderiza cada página
con un estado de sistema realista, **binariza igual que el panel** (`to_mono_bytes`) y
escribe el PNG a 4×. Regenerarlas es un solo comando, así que la documentación no puede
quedar desfasada respecto al código:

```bash
python preview.py
```

> Las mascotas se dibujan **proceduralmente** (primitivas de Pillow). Existe un
> renderizador de sprites pixel-art (`src/mascots/sprites.py`) desactivado por defecto
> con `USE_SPRITES = False` en `src/util/constants.py`: en el panel real se veía peor.
> Actívalo solo si quieres experimentar.

---

## Fuentes de datos

- **PC**: `psutil` (CPU, RAM, disco, red, procesos). Caché amortiguado: contadores
  baratos cada 1 s, escaneo de procesos cada 3 s **en un hilo aparte**.
- **OpenClaw**: sonda `lcd-probe` (WSL) que ejecuta `openclaw tasks --json` sobre
  **todos** los runtimes y devuelve solo líneas compactas. Mirar solo `subagent` era el
  error: hay 9 tareas de ese tipo frente a ~700 de `cli` y ~690 de `cron`.
- **Codex**: `stat` de `~/.codex/logs_2.sqlite` + sesión más reciente en `~/.codex/sessions`.
- **VPS**: comandos estándar de Linux por SSH (sin instalar nada en el servidor).

---

## Reglas de alerta

| Evento | Reacción |
|---|---|
| Subagente termina (OK o fallo) | flash RGB + salto a la mascota 8 s |
| Automatización (`cron`) **no exitosa** | flash RGB + salto a la mascota |
| Automatización correcta (heartbeat) | solo se lista en Alerts (evita ruido) |
| Tareas `cli` | excluidas: son nuestras propias llamadas `exec` |
| Descarga real detectada | vista Download automática |

---

## Página VPS (SSH remoto)

La página 8 muestra estadísticas de un servidor remoto vía SSH. No instala nada en el
VPS: ejecuta `/proc/loadavg`, `free`, `df`, `uptime` y `ps` por SSH.

Edita `vps_config.json`:

```json
{
  "host": "tu-servidor.com",
  "user": "root",
  "key_path": "C:\\Users\\VersusPc\\.ssh\\id_rsa",
  "poll_interval": 30,
  "timeout": 5,
  "max_retries": 3,
  "retry_interval": 60
}
```

- **`host`**: IP o dominio del VPS. Vacío ⇒ la página VPS **no aparece** (7 páginas).
- **`user`**: usuario SSH (por defecto `root`).
- **`key_path`**: ruta a la clave privada en Windows. Vacío ⇒ agente SSH o clave por defecto.
- **`poll_interval`** / **`timeout`** / **`max_retries`** / **`retry_interval`**:
  cadencia, espera y tolerancia a fallos de la conexión.

La página muestra: conectado (CPU/RAM/disco + uptime + top3, indicador verde) o
desconectado (OFFLINE/CONNECT, indicador rojo, contador de reintentos). El hilo SSH es
asíncrono y **no bloquea** el bucle principal.

---

## Rendimiento (medido)

| Componente | Antes | Ahora |
|---|---|---|
| `get_system_stats()` | 349 ms/llamada | 0,01 ms (caché 1 s / 3 s) |
| Conversión a bitmap | 1,98 ms | 0,11 ms (LUT) |
| Escaneo de descargas | siempre, 1 Hz | se salta sin red |
| Envío al LCD | 4 Hz fijo | adaptativo + deduplicado |
| Bucle principal | `sleep(0,1)` fijo | deadline (input 50 Hz, render por FPS) |
| Sonda OpenClaw | timeout 180 s | timeout 30 s + `_poll_lock` |
| Render de página | — | **~3 ms/frame** (presupuesto 250 ms) |
| **CPU en reposo** | 10,8 % de un núcleo | **7,6 %** |

---

## Notas técnicas (trampas encontradas)

1. **El búfer del LCD es 1 byte por píxel: 160×43 = 6880 bytes**, no un bitmap 1 bpp
   empaquetado. Pasar 860 bytes hace que el SDK lea fuera del búfer y la pantalla
   muestre ruido.
2. **Nunca usar `Image.convert("1")`**: aplica dithering Floyd-Steinberg y destroza el
   texto. Binarizar con umbral manual.
3. **Tipografía**: Consolas Bold 11 px con umbral 120. Con regular y umbral 128 se
   pierden las astas derechas de `o`, `N`, `P`; con 100 los trazos de la `m` se funden.
4. **LGS manda sobre el LCD** vía `settings.json`: `foregroundapplet` debe apuntar a
   nuestro applet y `switchmethod = 0`, o LGS rota y el nuestro desaparece. Editarlo
   **con LGS cerrado**.
5. **`start /B` no sirve**: el proceso muere al cerrarse la consola. Usar `pythonw.exe`
   con `DETACHED_PROCESS`.
6. **Un applet se identifica por su ejecutable**: `python.exe` y `pythonw.exe` registran
   **dos applets distintos**. Usar siempre el mismo binario.
7. **Detección de descargas**: exigir fichero creciendo **y** tráfico de red, ≥ 4 s y
   ≥ 3 MB; excluir cachés y `%TEMP%` o el streaming la dispara.
8. **Verificación sin teclado**: `preview.py` hace el round-trip por el conversor de
   bitmap, así que el PNG es exactamente lo que recibe el panel.
9. **Tras cualquier limpieza estructural**, ejecutar un chequeo AST de nombres no
   definidos antes de desplegar.
10. **`(c_ubyte * n)(*data)` desempaqueta n argumentos por frame**. Para buffers
    grandes usar `ctypes.create_string_buffer(data, len(data))`.

---

## Licencia

Código y arte propios. Las mascotas y el estilo overview son un homenaje retro; úsalos
como quieras en tus despliegues.
