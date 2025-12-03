import cv2
import numpy
import uuid
from network_utils import VideoHTTPSender
import threading
import queue


# Función principal para capturar y procesar el video
def video_loop(
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
):
    """Función principal para capturar y procesar el video."""

    frame_queue = queue.Queue(maxsize=PROCESSING_QUEUE_SIZE)  # Puedes ajustar el tamaño

    # Inicializar el sender HTTP si se especifica la URL del servidor
    if SERVER_URL:
        sender = VideoHTTPSender(SERVER_URL)

    def capture_frames():
        no_frame_count = 0 # Contador de frames sin recibir
        max_no_frames = 50  # Máximo 5 segundos sin frames
        last_stream_id = None # Ultimo id del stream (identifica la conexion con el emisor)
        
        while True:

            if hasattr(cap, "get_stream_id"):
                current_stream_id = cap.get_stream_id()
                if current_stream_id != last_stream_id:
                    # Resetear métricas
                    shared_data["total_count"] = 0
                    shared_data["already_counted"] = set()
                    shared_data["track_last_positions"] = {}
                    shared_data["car_count"] = 0
                    shared_data["person_count"] = 0
                    shared_data["bici_count"] = 0
                    last_stream_id = current_stream_id


            if hasattr(cap, "get_frame"):
                frame = cap.get_frame(timeout=None)
               
                if frame is None:
                    # No hay frame disponible: continuar
                    no_frame_count += 1
                    if no_frame_count >= max_no_frames:
                        print("Timeout - no se reciben frames. Saliendo...")
                        break
                    continue
                elif not isinstance(frame, numpy.ndarray):
                    print("Frame recibido no válido. Saliendo...")
                    break
                else:
                    no_frame_count = 0  # Resetear contador
            else:
                ret, frame = cap.read()
                if not ret or frame is None:
                    print("No se reciben frames desde la fuente de vídeo. Saliendo...")
                    break
            frame_queue.put(frame)
        frame_queue.put(None)  # Señal para terminar

    def process_frames():
        while True:
            frame = frame_queue.get()
            if frame is None:
                break
            # Cambiar frame a resolución consistente
            if frame.shape[1] != IMG_SIZE[0] or frame.shape[0] != IMG_SIZE[1]:
                frame = cv2.resize(frame, IMG_SIZE)
            annotated_frame, car_count, person_count, bici_count = process_frame(
                frame,
                model,
                DETECTION_CLASSES,
                CONFIDENCE,
                IOU,
                IMG_SIZE,
                TRACKER,
                LINE_ORIENTATION,
                shared_data,
            )
            # Cambiar frame a resolución consistente
            annotated_frame_resized = cv2.resize(annotated_frame, IMG_SIZE)

            # Enviar el frame al servidor HTTP si se especifica
            if sender:
                    try:
                        sender.send_frame(
                            sessionId=uuid.uuid4().hex,
                            frame=annotated_frame_resized,
                            car_count=car_count,
                            person_count=person_count,
                            bici_count=bici_count,
                        )
                    except Exception as e:
                        print(f"Servidor no disponible. Reintentando en siguiente frame... ({e})")

            # Mostrar el frame si se pide
            if SHOW_WINDOW:
                cv2.imshow("Deteccion de coches", annotated_frame_resized)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break

        cv2.destroyAllWindows()

    # Lanzar los hilos
    thread_capture = threading.Thread(target=capture_frames)
    thread_process = threading.Thread(target=process_frames)
    thread_capture.start()
    thread_process.start()
    thread_capture.join()
    thread_process.join()


# Función para procesar cada frame , detectar coches y dibujar las cajas
def process_frame(
    frame,
    model,
    DETECTION_CLASSES,
    CONFIDENCE,
    IOU,
    IMG_SIZE,
    TRACKER,
    line_orientation,
    shared_data,
):
    """Función para procesar cada frame,
    detectar coches y dibujar las cajas"""
    # Acceder a las variables compartidas
    total_count = shared_data["total_count"]
    car_count = shared_data.get("car_count", 0)
    person_count = shared_data.get("person_count", 0)
    bici_count = shared_data.get("bici_count", 0)
    already_counted = shared_data["already_counted"]
    track_last_positions = shared_data["track_last_positions"]

    # Resultados de la detección y el tracking
    results = model.track(
        frame,
        conf=CONFIDENCE,
        iou=IOU,
        imgsz=IMG_SIZE,
        persist=True,
        tracker=TRACKER,
        verbose=False,
    )

    # Crear una copia del frame para anotaciones
    annotated_frame = frame.copy()

    # Dimensiones del frame
    height, width = annotated_frame.shape[:2]

    if line_orientation == "horizontal":
        # Línea horizontal a 2/3 de la altura
        line_pos = int(height * 2 / 3)
        cv2.line(annotated_frame, (0, line_pos), (width, line_pos), (0, 255, 255), 2)
    elif line_orientation == "vertical":
        # Líneas verticales a 1/4 y 3/4 del ancho
        line_left = int(width * 1 / 4)
        line_right = int(width * 3 / 4)
        cv2.line(annotated_frame, (line_left, 0), (line_left, height), (0, 255, 255), 2)
        cv2.line(
            annotated_frame, (line_right, 0), (line_right, height), (0, 255, 255), 2
        )
    else:
        raise ValueError("line_orientation debe ser 'horizontal' o 'vertical'")

    # Procesar tracking y detecciones
    if results[0].boxes.id is not None:
        for box, track_id, cls_id, conf in zip(
            results[0].boxes.xyxy,
            results[0].boxes.id,
            results[0].boxes.cls,
            results[0].boxes.conf,
        ):
            # Obtener coordenadas de la caja
            x1, y1, x2, y2 = map(int, box)

            # Calcular el centro de la caja
            centroid = ((x1 + x2) // 2, (y1 + y2) // 2)

            # Solo considerar detecciones con ID válido
            cls_id = int(cls_id)

            # Filtrar por clase
            if cls_id not in DETECTION_CLASSES:
                continue

            # Obtener el nombre de la clase desde el modelo
            class_name = model.names[cls_id] if hasattr(model, "names") else str(cls_id)
            # Obtener la confianza de la detección
            confidence = float(conf)

            cv2.rectangle(annotated_frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
            cv2.putText(
                annotated_frame,
                f"{class_name} {int(track_id)} {confidence:.2f}",
                (x1, y1 - 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.9,
                (0, 255, 0),
                2,
            )
            cv2.circle(annotated_frame, centroid, 4, (0, 0, 255), -1)

            # Solo cuenta si cruza las líneas
            # según la orientación de la línea
            # Si es horizontal:
            if line_orientation == "horizontal":
                # Obtener la posición anterior del objeto
                prev_pos = track_last_positions.get(int(track_id), None)
                if (
                    prev_pos is not None  # Si existe una posición anterior
                    and prev_pos < line_pos  # Estaba por encima de la línea
                    and centroid[1] >= line_pos  # Ahora está por debajo
                    and track_id not in already_counted  # No se ha contado ya
                ):
                    total_count += 1  # Incrementar el contador
                    # Incrementar el contador específico según la clase
                    if class_name.lower() in ['car']: # Si es coche
                        car_count += 1 # Incrementar contador de coches
                    elif class_name.lower() in ['person']:
                        person_count += 1 # Incrementar contador de persona
                    elif class_name.lower() in ['bicycle']:
                        bici_count += 1 # Incrementar contador de bicicleta
                    already_counted.add(track_id) # Marcar como contado
                track_last_positions[int(track_id)] = centroid[1] # Actualizar la última posición
            elif line_orientation == "vertical": # Si es vertical:
                prev_pos = track_last_positions.get(int(track_id), None) # Posición anterior
                if (
                    prev_pos is not None
                    and prev_pos > line_left
                    and centroid[0] <= line_left
                    and track_id not in already_counted
                ):
                    total_count += 1
                    if class_name.lower() in ['car']:
                        car_count += 1
                    elif class_name.lower() in ['person']:
                        person_count += 1
                    elif class_name.lower() in ['bicycle']:
                        bici_count += 1
                    already_counted.add(track_id)
                elif (
                    prev_pos is not None
                    and prev_pos < line_right
                    and centroid[0] >= line_right
                    and track_id not in already_counted
                ):
                    total_count += 1
                    if class_name.lower() in ['car']:
                        car_count += 1
                    elif class_name.lower() in ['person']:
                        person_count += 1
                    elif class_name.lower() in ['bicycle']:
                        bici_count += 1
                    already_counted.add(track_id)
                track_last_positions[int(track_id)] = centroid[0]

    # Mostrar contadores en el frame
    cv2.putText(
        annotated_frame,
        f"Total: {total_count}",
        (10, 30),
        cv2.FONT_HERSHEY_SIMPLEX,
        1,
        (0, 0, 255),
        2,
    )
    cv2.putText(
        annotated_frame,
        f"Coches: {car_count}",
        (10, 70),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.7,
        (0, 255, 0),
        2,
    )
    cv2.putText(
        annotated_frame,
        f"Personas: {person_count}",
        (10, 110),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.7,
        (255, 0, 0),
        2,
    )
    cv2.putText(
        annotated_frame,
        f"Bicis: {bici_count}",
        (10, 150),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.7,
        (0, 165, 255),
        2,
    )

    # Actualizar variables compartidas
    shared_data["total_count"] = total_count
    shared_data["car_count"] = car_count
    shared_data["person_count"] = person_count
    shared_data["bici_count"] = bici_count
    shared_data["already_counted"] = already_counted
    shared_data["track_last_positions"] = track_last_positions

    return annotated_frame, car_count, person_count, bici_count
