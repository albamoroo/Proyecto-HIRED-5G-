from ultralytics import YOLO
import cv2
import json
import threading
from video_utils import video_loop
from network_utils import VideoUDPReceiver

# Se cargan las opciones del fichero model.json
with open("./config/model.json") as config_file:
    model_config = json.load(config_file)

# Se cargan las opciones del fichero video.json
with open("./config/video.json") as config_file:
    video_config = json.load(config_file)

# Se cargan las opciones del fichero network.json
with open("./config/network.json") as config_file:
    network_config = json.load(config_file)

# Parámetros del modelo
MODEL_PATH = model_config["MODEL_PATH"]  # Ruta al modelo YOLOv8 preentrenado
CONFIDENCE = model_config[
    "CONFIDENCE"
]  # Confianza mínima para considerar una detección válida
IOU = model_config["IOU"]  # Umbral de IoU
IMG_SIZE = tuple(model_config["IMG_SIZE"])  # Tamaño de la imagen para el modelo
FPS_CAP = model_config["FPS_CAP"]  # Limitar los FPS para mejorar rendimiento
DETECTION_CLASSES = model_config[
    "DETECTION_CLASSES"
]  # Clases a detectar (1: bicicleta, 2: coche,3: moto, 5: bus, 7: camión)
TRACKER = model_config["TRACKER"]  # Ruta al archivo de configuración del tracker
LINE_ORIENTATION = model_config["LINE_ORIENTATION"]  # Orientación de la línea de conteo

# Parámetros de la captura de video
VIDEO_SOURCE = video_config["VIDEO_SOURCE"]  # Fuente de video
OUTPUT_PATH = video_config["OUTPUT_PATH"]  # Ruta de salida para el video procesado
SHOW_WINDOW = video_config["SHOW_WINDOW"]  # Mostrar o no ventana de video
PROCESSING_QUEUE_SIZE = video_config[
    "PROCESSING_QUEUE_SIZE"
]  # Tamaño de la cola de procesamiento

# Parámetros de la red
SENDER_HOST = network_config.get("SENDER_HOST")  # Dirección IP a recibir por UDP
SENDER_PORT = network_config.get("SENDER_PORT")  # Puerto UDP
QUEUE_SIZE = network_config.get("QUEUE_SIZE")  # Tamaño de la cola del receptor UDP
SERVER_URL = network_config.get("SERVER_URL")  # URL del servidor HTTP para enviar video


# Usamos UDP para recibir video
if VIDEO_SOURCE == "socket":
    receiver = VideoUDPReceiver(
        host=SENDER_HOST,
        port=SENDER_PORT,
        queue_size=QUEUE_SIZE,
        auto_start=True
    )
    # Los demás parámetros usarán valores por defecto
    cap = receiver
else:
    # Capturamos el vídeo desde la interfaz deseada
    cap = cv2.VideoCapture(VIDEO_SOURCE)

    # Configuramos el tamaño y los FPS de la captura
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, IMG_SIZE[0])
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, IMG_SIZE[1])
    cap.set(cv2.CAP_PROP_FPS, FPS_CAP)

    if not cap.isOpened():
        print("Error: no se puede abrir el vídeo:", VIDEO_SOURCE)
        exit()


# Cargamos el modelo YOLOv8
model = YOLO(MODEL_PATH)
model.fuse()  # Optimiza el modelo

# Variables compartidas entre hilos
shared_data = {
    "total_count": 0,  # Contador total de coches
    "already_counted": set(),  # IDs de objetos ya contados
    "track_last_positions": {},  # última posición del objeto a contar
    "car_count": 0,
    "person_count": 0,
    "bici_count": 0,
}


# Programa principal

# Hilo creado para la captura y procesamiento de video
video_thread = threading.Thread(
    target=video_loop,
    args=(
        cap,
        model,
        DETECTION_CLASSES,
        CONFIDENCE,
        IOU,
        IMG_SIZE,
        TRACKER,
        LINE_ORIENTATION,
        SHOW_WINDOW,
        SERVER_URL,
        PROCESSING_QUEUE_SIZE,
        shared_data,
    ),
)

video_thread.start()  # Inicia el hilo
try:
    while video_thread.is_alive():
        video_thread.join(timeout=1)  # Espera con timeout para poder capturar Ctrl+C
except KeyboardInterrupt:
    print("Interrupción detectada. Cerrando...")
finally:
    if hasattr(cap, "release"):
        cap.release()  # Liberar recursos de la captura
    cv2.destroyAllWindows()  # Cerrar todas las ventanas de OpenCV
