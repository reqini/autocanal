# 🤖 AutoCanal — tu agente de YouTube, gratis y en tu Mac

**AutoCanal crea, edita y sube videos y Shorts a YouTube por vos.** Le pasás un video (o una idea) y él recorta, arma los shorts verticales, les pone títulos, portadas y descripción, y los sube a tu canal. También puede crear contenido 100 % original y publicarlo solo todos los días.

- 💸 **Sin APIs pagas ni suscripciones.** Todo corre en tu computadora con herramientas libres (ffmpeg, Python).
- 🔒 **Tus videos no salen de tu Mac** hasta que se suben a tu propio canal, con la API oficial de YouTube.
- 🧩 **Para cualquier rubro:** deportes, música para dormir, infantil, o cualquier video tuyo que quieras convertir en shorts.

> *English: AutoCanal is an open-source, local-first YouTube agent (Python + ffmpeg) that cuts, edits and uploads videos and Shorts for any niche. Docs are in Spanish.*

---

## ¿Qué puede hacer?

| Módulo | Le das | Te devuelve (y sube) |
| --- | --- | --- |
| **Cualquier rubro** | Un video tuyo ya editado | El video + N shorts verticales de 30 s con título y llamada a la acción |
| **Deportes** | Un partido completo (+ opcional, una reacción grabada) | Shorts de los mejores momentos con gancho de intriga, compilado horizontal y video de reacciones sincronizado |
| **Para dormir / relax** | Nada (o tu propio audio) | Un video de 8 h con pantalla negra y sonido original (ruido blanco, lluvia, música ambiente) + su short, todos los días |
| **Infantil** | Una historia escrita en un `.md` | Una serie de shorts animados con personajes propios (Lolo el patito y Rita la ranita), con música, voces de burbujitas y "continuará" |

Además: portadas automáticas, títulos y descripciones con hashtags, servicio automático diario, interfaz web local y aviso cuando YouTube pone el límite diario de subidas.

---

## 1. Instalación (macOS, una sola vez)

1. Descargá el repo: botón verde **Code → Download ZIP**, o en la Terminal:
   ```bash
   cd ~ && git clone https://github.com/reqini/autocanal.git
   ```
   Si bajaste el ZIP, descomprimilo en tu carpeta de usuario y renombralo a `autocanal`. Evitá el Escritorio y Documentos: macOS bloquea el modo automático ahí.
2. Instalá todo:
   ```bash
   bash ~/autocanal/instalar.command
   ```
   Instala ffmpeg y Python con Homebrew, las librerías, el comando `autocanal` y hace una prueba que arma un short de ejemplo.
3. Abrí una ventana nueva de Terminal y probá:
   ```bash
   autocanal ayuda
   ```

> Linux: funciona igual instalando `ffmpeg` y `python3` con tu gestor de paquetes y corriendo `pip install -r requirements.txt`. Los servicios automáticos y las notificaciones son solo para macOS.

## 2. Personalizá tu canal

Editá `config.json` (cualquier editor de texto):

```json
{
 "canal": "Mi Canal de Deportes",
 "marca": "MI CANAL",
 "handle": "@MiCanal",
 "hashtags": ["Deportes", "Highlights"],
 "relax_canal": "Mi Canal para Dormir",
 "infantil_canal": "Mi Canal Infantil",
 "shorts_auto": 5,
 "privacidad": "public"
}
```

- `marca` aparece en los shorts y portadas (la última palabra va en amarillo).
- `handle` aparece en el cierre animado "¿Te gustó? · Me gusta · Suscribite".
- `privacidad`: `public`, `unlisted` o `private` (ideal para probar).

## 3. Conectá YouTube (gratis, una sola vez)

AutoCanal sube con la API oficial de YouTube. Necesitás un "permiso" (`client_secret.json`) de Google Cloud:

1. Entrá a [console.cloud.google.com](https://console.cloud.google.com) y creá un proyecto.
2. **APIs y servicios → Biblioteca** → buscá **YouTube Data API v3** → **Habilitar**.
3. **Pantalla de consentimiento de OAuth** → tipo **Externo** → completá nombre y mail → en **Usuarios de prueba** agregá tu Gmail.
4. **Credenciales → Crear credenciales → ID de cliente de OAuth → App de escritorio** → **Descargar JSON**.
5. Copiá ese archivo a la carpeta del bot con el nombre `client_secret.json`.

La primera vez que subas, se abre el navegador: elegí el canal correcto y aceptá. Si dice "Google no verificó esta app", tocá **Continuar** (la app es tuya). Con la app en modo prueba, el permiso dura 7 días: después se vuelve a pedir solo.

Cada módulo tiene su propio permiso, así podés tener **un canal distinto por rubro** con la misma cuenta.

---

## 4. Cómo usarlo

Truco: escribí el comando hasta donde va el archivo y **arrastrá el video a la Terminal**, se escribe solo su ruta. El **número al final** de casi todos los comandos es la cantidad de shorts.

### 🎬 Cualquier rubro: tu video → video + shorts

```bash
autocanal archivo ~/Desktop/mi_video.mp4 "Título del video" 3
```
Sube el video y 3 shorts verticales de 30 s repartidos a lo largo del video.

### ⚽ Deportes

```bash
# Partido completo → 5 shorts de los mejores momentos + compilado
autocanal auto ~/Desktop/partido.mp4 "Equipo A vs Equipo B" 5

# Partido + reacción grabada → además, video de reacciones sincronizado
autocanal auto ~/Desktop/partido.mp4 "Equipo A vs Equipo B" ~/Desktop/reaccion.mp4
```
Detecta los momentos fuertes por la emoción del relato (el "¡GOOOL!"). Funciona con cualquier deporte con relator. La reacción tiene que ser una grabación de alguien mirando ese partido (con el audio del partido de fondo) para poder sincronizarla.

Paso a paso: `autocanal nuevo`, `analizar` (genera `plan.txt` para revisar o corregir), `shorts`, `reacciones`, `subir`.

### 🌙 Para dormir / relax

```bash
autocanal relax                 # crea el video de hoy (8 h) + su short
autocanal relax lluvia 10       # elegí sonido (blanco | lluvia | ambiente) y horas
autocanal relax archivo ~/Desktop/frecuencia.mp4 "777Hz Pantalla Negra" 2
autocanal relax servicio        # todos los días a las 03:10, solo
```
Todo el sonido se genera en tu Mac: no hay derechos de autor de nadie más.

### 🦆 Infantil: de una historia en `.md` a una serie de shorts

```bash
autocanal lolo historia ~/Desktop/mi_historia.md 6
```
La forma más simple de escribir la historia es una línea:
```
Lolo y Rita buscan una torta para la fiesta, 5 shorts
```
O un guion con control total (modelo en `historias/EJEMPLO.md`):
```markdown
# El tesoro del bosque
cantidad: 4
objetivo: flor           # flor | torta | hongo | meta
moraleja: ¡La amistad es el mejor tesoro!
amiga: si
escenarios: casa, bosque, montaña, meta

## Parte 1: El mapa del tesoro
lolo: ¡Hola, amigos! ¡Miren lo que encontré!
## Parte 3
rita: ¡Lolo! ¡El tesoro está en la cima!
```
Lo que no escribas lo inventa el bot. Otros: `autocanal lolo nuevo` (historia nueva del día), `autocanal lolo servicio` (una por día a las 17:10). Todo se sube marcado como **contenido para niños**.

### 🖥️ Sin Terminal

Doble clic en **AutoCanal Web.command**: abre una interfaz local en el navegador para cargar videos y ver lo que se armó.

### ⏰ Modo piloto automático

```bash
autocanal servicio instalar && autocanal relax servicio && autocanal lolo servicio
```
Deportes queda vigilando la carpeta `partidos/` (soltás un partido y se procesa solo). Dormir e infantil publican uno nuevo por día. La Mac tiene que quedar prendida y con internet.

---

## 5. Adaptarlo a tu rubro

- **Sin tocar código:** `autocanal archivo` sirve para cualquier nicho (recetas, gaming, podcasts, clases, viajes…). Cambiá nombres, marca y hashtags en `config.json`.
- **Con código:** cada módulo es un archivo Python chico dentro de `autocanal/`:
  - `recorte.py`: recorte vertical 9:16 con fondo desenfocado y textos (base para cualquier rubro).
  - `detect.py`: detección de momentos por audio (adaptable a risas, aplausos, picos de música).
  - `relax.py`: generación de sonido y video largo.
  - `lolo.py`: motor de animación 2D y generador de historias.
  - `subir.py`: subida con la API oficial (cola en `publicar.json`).

  Un rubro nuevo es un módulo que deja videos en una carpeta `listo/` con su `publicar.json` y llama a `subir_lista()`.

## 6. Reglas importantes

- **Subí solo contenido propio o con permiso.** Partidos, reacciones o videos de otros canales pueden darte un reclamo o una advertencia de derechos de autor. AutoCanal no descarga videos de YouTube, TikTok ni Instagram a propósito.
- **Límite diario:** YouTube limita cuántos videos sube un canal nuevo por día (alrededor de 10). Lo que no entra queda en cola y se sube con `autocanal subir`, `relax subir` o `lolo subir` al día siguiente.
- **Para videos de más de 15 min** verificá tu teléfono en [youtube.com/verify](https://www.youtube.com/verify).
- `client_secret.json` y los `.token*.json` son tus llaves: no los compartas ni los subas a GitHub (el `.gitignore` ya los excluye).

## Requisitos

macOS 12+ (o Linux), Python 3.10+, ffmpeg. Opcional: whisper.cpp para leer el relato.

## Contribuir

¡Bienvenidos los aportes! Abrí un *issue* con tu idea o un *pull request* con un rubro nuevo, personajes, sonidos o traducciones.

## Licencia

[MIT](LICENSE) © 2026 [Luciano Recchini](https://www.lucianorecchini.com/). Las fuentes incluidas tienen licencias libres (ver `assets/fonts/LICENCIAS.md`).
