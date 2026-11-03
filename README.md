# 💬 Chat de clase

Chat hecho en **Python** con **sockets** y **hilos** para hablar y **pasarse archivos** con los compañeros. Un equipo hace de servidor y el resto se conectan como clientes, desde la misma red local o desde casa usando **Tailscale**.

Proyecto personal para practicar redes (modelo cliente-servidor, TCP, IPs, puertos y VPN) mientras estudio el Grado Superior de ASIR.

## ✨ Qué se puede hacer

- 💬 Mandar mensajes a todos los conectados
- 📎 Enviar archivos (fotos, PDFs, apuntes... hasta 5 MB)
- 📂 Los archivos recibidos se guardan solos en la carpeta `recibidos/`
- 👥 Ver quién está conectado
- 🪟 Cliente con ventana o cliente de terminal (pueden usarse a la vez)

## 📁 Archivos

| Archivo          | Qué es                                                     |
|------------------|------------------------------------------------------------|
| `servidor.py`    | Recibe los mensajes y archivos y los reenvía a los demás   |
| `cliente_gui.py` | Cliente con ventana (Tkinter)                              |
| `cliente.py`     | Cliente de terminal                                        |

## ⚙️ Cómo funciona

```
 Cliente (Ana)  ──┐
                  │      TCP, puerto 5555
 Cliente (Bea)  ──┼──────────────────────►  Servidor (192.168.1.50)
                  │                            │
 Cliente (Luis) ──┘                            └─► reenvía cada mensaje a los demás
```

1. El **servidor** abre el puerto `5555` y se queda esperando conexiones.
2. Cada **cliente** se conecta a la IP del servidor y lo primero que envía es su nombre.
3. Cuando alguien manda un mensaje o un archivo, el servidor lo **reenvía a todos los demás**.
4. Se usan **hilos** (`threading`): el servidor atiende a cada usuario en un hilo distinto y el cliente escucha mientras tú escribes.

### El "protocolo" del chat

Cada mensaje viaja como **una línea de texto en formato JSON** terminada en `\n`. El `\n` sirve para saber dónde acaba un mensaje, porque TCP puede juntar o partir los datos.

```json
{"tipo": "nombre",   "nombre": "Ana"}
{"tipo": "texto",    "texto": "hola!"}
{"tipo": "archivo",  "nombre": "apuntes.pdf", "datos": "JVBERi0xLjQK..."}
{"tipo": "usuarios"}
```

Los archivos se convierten a **base64** (texto) para poder meterlos dentro del JSON.

### Conceptos de redes que se practican

- **Socket TCP** (`socket.SOCK_STREAM`) y las funciones `bind`, `listen`, `accept` y `connect`.
- **IP y puerto**: el servidor escucha en `0.0.0.0:5555`.
- **Protocolo de aplicación** propio con mensajes JSON delimitados por `\n`.
- **Codificación**: UTF-8 para el texto y base64 para los archivos.
- **VPN** (Tailscale) para conectar equipos de redes distintas.

## 📋 Requisitos

- Python 3 (no hace falta instalar librerías).
- Para el cliente con ventana en Ubuntu: `sudo apt install python3-tk`.

## 🚀 Uso en la misma red

**1. Arrancar el servidor**

```bash
python3 servidor.py
```

```
===== CHAT DE CLASE (v2) =====
Servidor encendido. Decid a vuestros compañeros que se conecten a: 192.168.1.50
```

**2. Conectarse** (cada compañero)

```bash
python3 cliente_gui.py
```

Pide la IP del servidor y tu nombre, y abre el chat.

O en la terminal:

```bash
python3 cliente.py
```

| Comando           | Qué hace                         |
|-------------------|----------------------------------|
| `/archivo ruta`   | Envía un archivo                 |
| `/usuarios`       | Muestra quién está conectado     |
| `/salir`          | Sale del chat                    |

> 💡 Para probarlo en un solo PC, abre varios clientes y usa la IP `127.0.0.1`.
> En Windows usa `python` en lugar de `python3`.

## 🌍 Uso desde fuera (con Tailscale)

[Tailscale](https://tailscale.com) crea una **red privada virtual (VPN)** entre vuestros equipos por internet, así que el chat funciona igual que en clase, estéis donde estéis. Además, el tráfico va cifrado.

1. Instalar Tailscale en cada PC (en Linux):
   ```bash
   curl -fsSL https://tailscale.com/install.sh | sh
   sudo tailscale up
   ```
2. Invitar a los compañeros a tu red de Tailscale desde el panel de administración.
3. Quien hace de servidor mira su IP de Tailscale:
   ```bash
   tailscale ip -4
   ```
   Será algo como `100.101.102.103`.
4. Los demás se conectan con `cliente_gui.py` usando esa IP.

## 🛠️ Problemas frecuentes

- **No se puede conectar**: comprueba con `ping` que llegas al servidor.
- **El ping va pero el chat no**: el firewall puede estar bloqueando el puerto. En Ubuntu: `sudo ufw allow 5555/tcp`.
- **Se desconectan todos de golpe**: se ha cerrado el servidor.
- **`No module named 'tkinter'`**: `sudo apt install python3-tk`.

## 🔮 Posibles mejoras

- [x] Interfaz gráfica con Tkinter
- [x] Envío de archivos
- [ ] Guardar el historial del chat en un archivo `.txt`
- [ ] Mensajes privados (`/msg nombre texto`)
- [ ] Colores para cada usuario

## ⚠️ Aviso

Proyecto educativo para usar entre compañeros de confianza. Sin Tailscale, los mensajes viajan sin cifrar por la red local. No abras archivos recibidos de personas que no conoces.

## 👩‍💻 Autora

Beatriz García · [@bgarciaa181](https://github.com/bgarciaa181)