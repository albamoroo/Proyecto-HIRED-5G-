from telegram.ext import ApplicationBuilder, CommandHandler
import subprocess
import io
from staticmap import StaticMap, CircleMarker

TOKEN = "" # TOKEN eliminado por seguridad

# Python del entorno conjunto
PYTHON_ENV = "/home/grupo4/entorno/bin/python3"

# Scripts
UDP_SCRIPT = "/home/grupo4/camera_UDP/UDP_envio_def/main.py"
GPS_SCRIPT = "/home/grupo4/gps.py"
POS_SCRIPT = "/home/grupo4/posicion.py"



#  /hola

async def hola_handler(update, context):
    await update.message.reply_text(
        "¡Hola! Soy el bot del grupo 4 del Hired, creado para la asignatura "
        "“Internet de Nueva Generación”. ¿En qué puedo ayudarte?"
    )



#  /comandos

async def comandos_handler(update, context):
    await update.message.reply_text(
        "*Comandos disponibles:*\n\n"
        "/hola — Saludo\n"
        "/comandos — Lista de comandos\n"
        "/cam — Iniciar cámara\n"
        "/camstop — Parar cámara\n"
        "/gps — Iniciar GPS\n"
        "/gpsstop — Parar GPS\n"
        "/posicion — Obtener mapa con coordenada actual\n"
        "/5G — Activar 5G\n",
        parse_mode="Markdown"
    )




#  /cam

async def cam_handler(update, context):
    await update.message.reply_text("Iniciando camara...")
    subprocess.Popen([PYTHON_ENV, UDP_SCRIPT])
    await update.message.reply_text("Camara grabando")



#  /camstop 

async def camstop_handler(update, context):
    await update.message.reply_text("Cortando camara...")
    subprocess.run(["pkill", "-f", "UDPv5.py"])
    await update.message.reply_text("Camara apagada")



#  /gps 

async def gps_handler(update, context):
    await update.message.reply_text("Iniciando GPS...")
    subprocess.Popen([PYTHON_ENV, GPS_SCRIPT])
    await update.message.reply_text("GPS lanzando")



#  /gpsstop

async def gpsstop_handler(update, context):
    await update.message.reply_text("Cortando GPS...")
    subprocess.run(["pkill", "-f", "gps.py"])
    await update.message.reply_text("GPS cortado")



#  /posicion

async def posicion_handler(update, context):
    await update.message.reply_text("Obteniendo posición actual...")

    try:
        output = subprocess.check_output(
            [PYTHON_ENV, POS_SCRIPT],
            stderr=subprocess.STDOUT
        ).decode().strip()
    except subprocess.CalledProcessError as e:
        await update.message.reply_text("Error ejecutando posicion.py")
        return

    if "No se obtuvo ninguna coordenada" in output:
        await update.message.reply_text("No se pudo obtener la posición GPS.")
        return

    try:
        lines = output.splitlines()
        lat_line = [l for l in lines if "Latitud" in l][0]
        lon_line = [l for l in lines if "Longitud" in l][0]

        lat = float(lat_line.split(":")[1])
        lon = float(lon_line.split(":")[1])
    except Exception:
        await update.message.reply_text(
            "No se pudieron interpretar las coordenadas:\n" + output
        )
        return

    # Generar el mapa
    try:
        m = StaticMap(600, 400)
        marker = CircleMarker((lon, lat), "red", 12)
        m.add_marker(marker)
        image = m.render()

        buf = io.BytesIO()
        image.save(buf, format="PNG")
        buf.seek(0)

        caption = f"Posición actual:\nLat: {lat:.5f}\nLon: {lon:.5f}"
        await update.message.reply_photo(photo=buf, caption=caption)
    except Exception as e:
        await update.message.reply_text(f"Error generando mapa: {e}")



#  /5G 

async def cincoG_handler(update, context):
    await update.message.reply_text("Conectando a la red 5G...")
    subprocess.Popen(["sudo", "ip", "link", "set", "wwan0", "up"])
    subprocess.Popen(["sudo", "waveshare-CM"])
    await update.message.reply_text("Red 5G conectada.")


def main():
    print("Entré al main()")
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("hola", hola_handler))
    app.add_handler(CommandHandler("comandos", comandos_handler))

    app.add_handler(CommandHandler("cam", cam_handler))
    app.add_handler(CommandHandler("camstop", camstop_handler))

    app.add_handler(CommandHandler("gps", gps_handler))
    app.add_handler(CommandHandler("gpsstop", gpsstop_handler))

    app.add_handler(CommandHandler("posicion", posicion_handler))

    app.add_handler(CommandHandler("5G", cincoG_handler))


    app.run_polling()


if __name__ == "__main__":
    print("Arrancando el bot...")
    main()
