#!/usr/bin/env python3
import cv2
import time
from VideoUDPSender import VideoUDPSender
from picamera2 import Picamera2

def main():
    # Configuración
    SERVER_IP = "192.168.0.211"  # Cambia por la IP de tu servidor
    SERVER_PORT = 5000
    FPS = 30
    FRAME_INTERVAL = 1.0 / FPS
    
    # Inicializar cámara
    print("Inicializando Picamera2...")
    picam2 = Picamera2()
    config = picam2.create_preview_configuration(main={"size": (640, 480)})
    picam2.configure(config)
    picam2.start()
    time.sleep(2)  # Esperar inicio cámara
    
    # Inicializar emisor UDP
    sender = VideoUDPSender(host=SERVER_IP, port=SERVER_PORT, jpeg_quality=60)
    
    print("Iniciando transmisión...")
    print(f"{FPS} FPS -> {SERVER_IP}:{SERVER_PORT}")
    print("Presiona Ctrl+C para detener\n")
    
    frame_count = 0
    start_time = time.time()
    last_frame_time = 0
    
    try:
        while True:
            current_time = time.time()
            
            # Control de FPS
            if current_time - last_frame_time >= FRAME_INTERVAL:
                # Capturar frame
                frame = picam2.capture_array()
                frame_bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
                
                # Enviar frame
                sender.send_frame(frame_bgr)
                frame_count += 1
                last_frame_time = current_time
                
                # Log cada segundo
                if frame_count % FPS == 0:
                    elapsed = time.time() - start_time
                    actual_fps = frame_count / elapsed
                    print(f"Frame {frame_count} | FPS: {actual_fps:.1f}")
            
            time.sleep(0.001)
            
    except KeyboardInterrupt:
        print("\nDetenido por usuario")
    finally:
        # Limpieza
        picam2.stop()
        picam2.close()
        sender.release()

if __name__ == "__main__":
    main()