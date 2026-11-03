# 💬 Chat de clase por red local

Chat de consola hecho en **Python** con **sockets** y **hilos**. Un equipo hace de servidor y el resto de compañeros se conectan como clientes desde la misma red local para hablar entre ellos.

Proyecto personal para practicar redes (modelo cliente-servidor, TCP, IPs y puertos) mientras estudio el Grado Superior de ASIR.

## 📁 Archivos

| Archivo       | Qué es                                                        |
|---------------|---------------------------------------------------------------|
| `servidor.py`    | Recibe los mensajes y los reenvía a todos los conectados   |
| `cliente.py`     | Cliente de terminal para entrar al chat                    |
| `cliente_gui.py` | Cliente con ventana (Tkinter): caja de mensajes y botones  |

## ⚙️ Cómo funciona

```
 Cliente (Ana)  ──┐
                  │      TCP, puerto 5555
 Cliente (Bea)  ──┼──────────────────────►  Servidor (192.168.1.50)
                  │                            │
 Cliente (Luis) ──┘                            └─► reenvía cada mensaje a los demás
```

1. El **servidor** abre el puerto `5555` y se queda esperando conexiones, como una centralita.
2. Cada **cliente** se conecta a la IP del servidor y lo primero que envía es su nombre.
3. Cuando alguien escribe un mensaje, viaja al servidor y este lo **reenvía a todos los demás**.
4. Se usan **hilos** (`threading`) para hacer varias cosas a la vez:
   - El servidor atiende a cada usuario en un hilo distinto, así no se bloquean entre ellos.
   - El cliente escucha los mensajes en un hilo mientras tú escribes en el otro.

### Conceptos de redes que se practican

- **Socket TCP**: la conexión entre cliente y servidor (`socket.SOCK_STREAM`).
- **IP y puerto**: el servidor escucha en `0.0.0.0:5555` (todas sus tarjetas de red).
- **`bind`, `listen`, `accept`** en el servidor y **`connect`** en el cliente.
- **`encode` / `decode`**: por la red viajan bytes, así que el texto se convierte a UTF-8.

## 📋 Requisitos

- Python 3 (no hace falta instalar ninguna librería, todo viene incluido).
- Todos los equipos conectados a la misma red local.

## 🚀 Uso

### 1. Arrancar el servidor

En el equipo que hará de servidor:

```bash
python3 servidor.py
```

Mostrará la IP a la que se tienen que conectar los demás:

```
===== CHAT DE CLASE =====
Servidor encendido. Decid a vuestros compañeros que se conecten a: 192.168.1.50
Pulsa Ctrl+C para apagarlo.
```

### 2. Conectarse como cliente

En cada equipo que quiera entrar al chat:

```bash
python3 cliente.py
```

```
===== CHAT DE CLASE =====
IP del servidor: 192.168.1.50
Tu nombre: Ana
*** Bienvenido al chat de clase! Escribe /usuarios para ver quien esta y /salir para irte ***
```

### 3. O usar el cliente con ventana

```bash
python3 cliente_gui.py
```

Pide la IP y el nombre en dos ventanitas y abre el chat. Se puede enviar con Enter o con el botón **Enviar**, y el botón **👥 Usuarios** muestra quién está conectado. Los clientes de terminal y de ventana pueden estar en el chat a la vez.

> Si sale `No module named 'tkinter'`, en Ubuntu se instala con `sudo apt install python3-tk`.

> 💡 Para probarlo en un solo PC, abre varias terminales y usa la IP `127.0.0.1`.

> En Windows usa `python` en lugar de `python3`.

### Comandos

| Comando     | Qué hace                         |
|-------------|----------------------------------|
| `/usuarios` | Muestra quién está conectado     |
| `/salir`    | Sale del chat                    |

## 🛠️ Problemas frecuentes

- **No se puede conectar**: comprueba con `ping 192.168.1.50` que llegas al servidor.
- **El ping va pero el chat no**: el firewall puede estar bloqueando el puerto. En Ubuntu: `sudo ufw allow 5555/tcp`.
- **Se desconectan todos de golpe**: se ha cerrado el servidor.

## 🔮 Posibles mejoras

- [ ] Guardar el historial del chat en un archivo `.txt`
- [ ] Mensajes privados (`/msg nombre texto`)
- [ ] Colores en la consola para cada usuario
- [x] Interfaz gráfica con Tkinter

## ⚠️ Aviso

Proyecto educativo para usar en una red local de confianza (por ejemplo, el aula y con permiso del profesor). Los mensajes viajan sin cifrar.

## 👩‍💻 Autora

Beatriz García · [@bgarciaa181](https://github.com/bgarciaa181)