# LCDGlance — Logitech G510 LCD + RGB

Monitor de sistema, panel de agentes y **mascotas animadas** para el **LCD monocromo
160×43** y la **iluminación RGB** del teclado Logitech G510, sobre Logitech Gaming
Software (LGS 8.57).

## Mascotas

Cada fuente tiene su propio personaje dibujado a mano (no texto), con animaciones:

| Mascota | Fuente | Dibujo | Color RGB |
|---|---|---|---|
| **CLAW** | OpenClaw | cangrejo: caparazón, pinzas, patas, ojos en tallos | cian |
| **CODEX** | Codex (`~/.codex`) | robot: antena con LED, visor con escáner, boca de rejilla | verde |
| **PC** | tu equipo | monitor con cara y peana | azul |

Animaciones: respiración vertical, parpadeo cada 2-4 s, mirada aleatoria, LED
intermitente y barrido del visor. La mascota **destacada** es la del agente ocupado
(o OpenClaw si no hay ninguno) y su color tiñe el teclado.

## Páginas

| # | Página | Contenido |
|---|---|---|
| 1 | Mascot | mascota activa en grande + estado |
| 2 | Sources | PC / CLAW / CODEX en miniatura con estado (`*` ocupado, `+` activo, `-` caído) |
| 3 | System | CPU / RAM / disco con barras |
| 4 | Network | subida/bajada + sparkline |
| 5 | Procs | procesos top por CPU |
| 6 | OpenClaw | contadores de subagentes + último trabajo |
| 7 | Alerts | alertas de sistema y de agentes |
| ★ | Download | aparece **solo** si hay una descarga real |

- **Botones**: B1/B2 cambian de página, B3 fuerza refresco, B4 alerta manual.
- **Auto-foco**: si un agente termina, salta a su mascota reaccionando ~8 s; si hay una
  descarga, muestra Download; después vuelve a tu página.
- Indicador de página: tira vertical de marcas en el borde izquierdo.

## RGB

Motor por prioridad, con respiración y atenuación nocturna (23:00-08:00 al 35 %):

```
alerta manual > agente falló > agente OK > descarga > agentes activos
> CPU>90 % > RAM>90 % > disco>95 % > color de la mascota activa
```

## Ficheros

```
lcdglance.py         aplicación principal
launch_detached.py   lanzador desacoplado (pythonw + DETACHED_PROCESS)
configure.py         normaliza la config de applets de LGS (deja solo LCDGlance)
preview.py           renderiza páginas y mascotas a PNG para revisar sin el teclado
start_lcdglance.vbs  auto-arranque (copiar a la carpeta Startup)
restart.bat          reinicia la aplicación
restart_lgs.bat      reinicia LGS + la aplicación
```

## Instalación

Copia la carpeta a `C:\Users\<usuario>\lcdglance\` y:

```bat
python configure.py            :: deja solo el applet correcto en LGS
python launch_detached.py      :: arranca la aplicación desacoplada
```

Auto-arranque: copia `start_lcdglance.vbs` a
`%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\`.

## Fuentes de datos

- **PC**: `psutil` (CPU, RAM, disco, red, procesos). Coste amortiguado con caché:
  contadores baratos cada 1 s, escaneo de procesos cada 3 s **en un hilo aparte**
  (bloqueaba 347 ms y era el mayor consumidor del bucle).
- **OpenClaw**: la sonda `lcd-probe` (en WSL) ejecuta `openclaw tasks --json` sobre
  **todos** los runtimes (~1,6 MB de JSON) y devuelve solo unas líneas compactas
  (1,1 s, unos cientos de bytes).  Mirar solo `subagent` era el error: hay 9 tareas de
  ese tipo frente a ~700 de `cli` y ~690 de `cron`.
- **Codex**: `stat` de `~/.codex/logs_2.sqlite` + sesión más reciente en `~/.codex/sessions`.

## Reglas de alerta

| Evento | Reacción |
|---|---|
| Subagente termina (OK o fallo) | flash RGB + salto a la mascota 8 s |
| Automatización (`cron`) **no exitosa** | flash RGB + salto a la mascota |
| Automatización correcta (heartbeat) | solo se lista en Alerts (evita ruido) |
| Tareas `cli` | excluidas: son nuestras propias llamadas `exec` |
| Descarga real detectada | vista Download automática |

## Rendimiento (medido)

| Componente | Antes | Ahora |
|---|---|---|
| `get_system_stats()` | 349 ms por llamada | 0,01 ms (caché 1 s / 3 s) |
| Conversión a bitmap | 1,98 ms | 0,11 ms (LUT `point().tobytes()`) |
| Escaneo de descargas | siempre, 1 Hz | se salta si no hay red |
| Envío al LCD | 4 Hz fijo | adaptativo + deduplicado |
| **CPU en reposo** | 10,8 % de un núcleo | **7,6 %** |

## Notas técnicas (trampas encontradas)

1. **El búfer del LCD es 1 byte por píxel: 160×43 = 6880 bytes**, no un bitmap de 1 bpp
   empaquetado. Pasar 860 bytes hace que el SDK lea fuera del búfer y la pantalla
   muestre ruido.
2. **Nunca usar `Image.convert("1")`** en Pillow: aplica dithering Floyd-Steinberg y
   destroza el texto. Binarizar con umbral manual.
3. **Tipografía**: Consolas Bold 11 px con **umbral 120**. Con regular y umbral 128 se
   pierden las astas derechas de `o`, `N`, `P`; con umbral 100 los tres trazos de la
   `m` minúscula se funden en un bloque sólido.
4. **LGS manda sobre el LCD** vía `%LOCALAPPDATA%\Logitech\Logitech Gaming Software\settings.json`:
   `foregroundapplet` debe apuntar a nuestro applet y `switchmethod` debe ser `0`, o LGS
   rota entre applets y el nuestro desaparece. Editarlo **con LGS cerrado**.
5. **Lanzar con `start /B` no sirve**: el proceso muere al cerrarse la consola. Usar
   `pythonw.exe` con `DETACHED_PROCESS`.
6. **Un applet de LGS se identifica por su ejecutable**: lanzar con `python.exe` y con
   `pythonw.exe` registra **dos applets distintos**. Usar siempre el mismo binario.
7. **Detección de descargas**: exigir fichero creciendo en carpeta real **y** tráfico de
   red, ≥ 4 s y ≥ 3 MB; excluir cachés y `%TEMP%` o el vídeo en streaming la dispara.
8. **Verificación sin teclado**: `preview.py` hace el round-trip por el conversor de
   bitmap, así que el PNG es exactamente lo que recibe el panel. El **Emulador de LCD**
   de LGS también sirve como banco de pruebas (capturable con `nodes screen_snapshot`).
9. **Nunca borrar bloques con heurísticas de fin de línea.** Un script que cortaba
   "hasta la línea que termina en `]`" se llevó 33 líneas de más (`BIN_THRESHOLD`, los
   `try/except` de importación, `_TRANSLIT`). Tras cualquier limpieza estructural,
   ejecutar un chequeo estático de nombres indefinidos (AST) antes de desplegar.
10. **`(c_ubyte * n)(*data)` desempaqueta n argumentos por frame**. Para buffers
    grandes usar `ctypes.create_string_buffer(data, len(data))`.

## Página VPS (SSH remoto)

La página 8 muestra estadísticas de un servidor remoto vía SSH. No instala nada en el VPS:
ejecuta comandos estándar de Linux (`/proc/loadavg`, `free`, `df`, `uptime`, `ps`) por SSH.

### Configuración

Edita `vps_config.json` en la carpeta de LCDGlance:

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

- **`host`**: dirección IP o dominio del VPS. Si está vacío, la página VPS **no aparece** (7 páginas, igual que antes).
- **`user`**: usuario SSH (por defecto `root`).
- **`key_path`**: ruta a la clave privada SSH en Windows. Si está vacío, usa el agente SSH o la clave por defecto.
- **`poll_interval`**: segundos entre consultas (por defecto 30). No bajar de 15 para no saturar el VPS.
- **`timeout`**: segundos de espera de conexión SSH (por defecto 5).
- **`max_retries`**: fallos consecutivos antes de mostrar "VPS OFFLINE" (por defecto 3).
- **`retry_interval`**: segundos entre reintentos cuando está offline (por defecto 60).

La página muestra:

- **Conectado**: CPU%, RAM%, disco% con barras, uptime, top 3 procesos. Indicador verde.
- **Desconectado**: "VPS OFFLINE" o "VPS CONNECT...", indicador rojo, contador de reintentos.

El hilo SSH es asíncrono y no bloquea el bucle principal del LCD.

## Scouter (B3 mejorado)

Pulsar B3 muestra el **scouter** durante 5 segundos con:

- Nivel de poder (PL) en la cabecera
- CPU / RAM / disco con barras y porcentajes
- Temperatura CPU (si `psutil` la proporciona)
- Estado del gateway: **GW UP** (punto lleno) o **GW DOWN** (punto hueco)
- Número de agentes activos: **AG** + cuenta
- Estado de Codex

Transcurridos 5 segundos vuelve a la página actual automáticamente.
