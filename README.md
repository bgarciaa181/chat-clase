# 💬 Chat de clase

Chat para hablar y **pasarse archivos de cualquier tamaño** con los compañeros de clase, desde el **navegador** del PC o del móvil. El servidor está hecho en **Python** sin librerías externas y la página en **HTML, CSS y JavaScript**.

Proyecto personal para practicar redes y desarrollo web mientras estudio el Grado Superior de ASIR.

## ✨ Qué se puede hacer

- 💬 Hablar con todos los conectados, desde el PC o el móvil
- 📎 Enviar archivos de hasta **2 GB**, que se suben **por trozos** con barra de progreso
- 🖼️ Las fotos se ven directamente en el chat
- 🖱️ Arrastrar archivos encima del chat para enviarlos
- 👥 Ver quién está conectado
- 🌙 Modo oscuro automático

## 📁 Archivos

| Archivo / carpeta  | Qué es                                                         |
|--------------------|----------------------------------------------------------------|
| `servidor_web.py`  | Servidor web y API del chat (mensajes y subida de archivos)    |
| `web/index.html`   | La página del chat que se abre en el navegador                 |

## 🚀 Cómo usarlo

**1. Arrancar el servidor** en un equipo:

```bash
python3 servidor_web.py
```

```
===== CHAT DE CLASE (v3 web) =====
Abre en el navegador:  http://localhost:8080
Tus compañeros:        http://192.168.1.50:8080
```

**2. Entrar al chat:** cada compañero abre en su navegador la dirección que sale (`http://192.168.1.50:8080`), escribe su nombre y listo. No hace falta instalar nada.

> En Windows usa `python` en lugar de `python3`.

## ⚙️ Cómo funciona

```
 Navegador (Ana) ──┐
                   │      HTTP, puerto 8080
 Navegador (Bea) ──┼──────────────────────►  servidor_web.py
                   │                          ├─ guarda los mensajes en memoria
 Móvil (Luis)    ──┘                          └─ guarda los archivos en archivos/
```

### Mensajes

El servidor guarda los mensajes en una lista, y cada uno lleva un número (`id`). Cada navegador pregunta **cada segundo**: *"¿hay mensajes nuevos desde el número X?"* (`GET /mensajes?desde=X`). Esta técnica se llama **polling**.

### Archivos por trozos

Mandar un archivo grande de golpe gastaría mucha memoria y bloquearía el chat, así que el navegador lo parte en **trozos de 1 MB**:

```
Navegador                                   Servidor
 │ POST /subir/inicio  {nombre, tamaño} ───► │ crea un archivo vacío y devuelve un id
 │ POST /subir/trozo?id=...  (1 MB)     ───► │ lo añade al final del archivo
 │ POST /subir/trozo?id=...  (1 MB)     ───► │ lo añade al final del archivo
 │   ...                                     │
 │ POST /subir/fin?id=...               ───► │ comprueba que está completo y lo anuncia
```

- En el navegador, `archivo.slice()` corta el trozo sin cargar el archivo entero.
- El servidor escribe cada trozo en disco, así que la memoria apenas se nota aunque el archivo pese 1 GB.
- La barra de progreso está hecha de **cuadritos**, y cada uno representa un grupo de trozos.
- Los demás descargan el archivo con `GET /descargar/<id>`, y el servidor lo envía de 64 KB en 64 KB.

### Historial y registro (log)

Todo se guarda en la carpeta `datos/`:

- **`historial.json`**: los mensajes y la lista de archivos. Se guarda con cada mensaje y se carga al arrancar, así que **no se pierde nada al apagar el servidor**. Se escribe primero en un archivo temporal y luego se renombra, para que no se quede a medias si se corta.
- **`registro-AAAA-MM-DD.log`**: el log del servidor, un archivo por día, con la fecha, la IP y qué ha pasado:

```
[2026-11-03 12:38:10] 192.168.1.23    ENTRA    Maxi
[2026-11-03 12:38:15] 192.168.1.23    MENSAJE  Maxi: Que tal?
[2026-11-03 12:39:02] 192.168.1.31    ARCHIVO  Luis sube apuntes.pdf (3.0 MB)
[2026-11-03 12:39:40] 192.168.1.50    DESCARGA apuntes.pdf
```

Para verlo en directo mientras se usa el chat:

```bash
tail -f datos/registro-$(date +%F).log
```

Para buscar algo concreto en todos los días, por ejemplo todo lo que ha hecho una IP:

```bash
grep "192.168.1.23" datos/registro-*.log
```

### Limpieza automática

Para que el disco no se llene, al principio de `servidor_web.py` hay un ajuste:

```python
DIAS_GUARDAR = 7   # 0 = guardar siempre
```

Una vez por hora, un hilo borra los mensajes, **los archivos subidos** y los logs de más de esos días (la misma idea que `logrotate` en Linux). También borra los restos de subidas que se cortaron a medias.

La carpeta `datos/` está en el `.gitignore`: **nunca se sube a GitHub**. Cada persona que descargue el proyecto tiene su propio historial y su propio log, solo en su equipo.

### Seguridad básica

- Los mensajes se muestran con `textContent`, así que nadie puede colar código HTML o JavaScript.
- Los nombres de archivo se limpian con `os.path.basename` para evitar rutas como `../../`.
- El servidor comprueba los tamaños: máximo 2 GB por archivo y 4 MB por trozo.

## 🌍 Usarlo desde fuera de clase (Tailscale)

[Tailscale](https://tailscale.com) crea una **red privada virtual (VPN)** entre vuestros equipos por internet, y además el tráfico va cifrado.

1. Instalar Tailscale en cada equipo (en Linux: `curl -fsSL https://tailscale.com/install.sh | sh` y después `sudo tailscale up`). En el móvil hay app.
2. Invitar a los compañeros a tu red de Tailscale desde el panel de administración.
3. Quien hace de servidor mira su IP con `tailscale ip -4` (algo como `100.101.102.103`).
4. Los demás abren `http://100.101.102.103:8080`.

## 🛠️ Problemas frecuentes

- **La página no carga en otro equipo**: comprueba con `ping` que llegas al servidor.
- **El ping va pero la página no**: el firewall bloquea el puerto. En Ubuntu: `sudo ufw allow 8080/tcp`.
- **Sale "Sin conexión con el servidor"**: se ha cerrado `servidor_web.py`.

## ⚠️ Aviso

Proyecto educativo para usar entre compañeros de confianza. Sin Tailscale, los mensajes viajan sin cifrar por la red local. El servidor guarda las conversaciones y las IPs en `datos/`, así que avisa a tus compañeros de que el chat queda registrado. Para empezar de cero, borra las carpetas `datos/` y `archivos/` con el servidor apagado.

## 🔮 Posibles mejoras

- [x] Guardar el historial y un registro (log) de lo que pasa
- [ ] Mensajes privados
- [ ] Contraseña para entrar al chat
- [ ] Usar WebSockets en vez de polling

## 👩‍💻 Autora

Beatriz García · [@bgarciaa181](https://github.com/bgarciaa181)
