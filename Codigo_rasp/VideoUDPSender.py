import cv2
import socket
import pickle
import numpy as np
import time
import threading
import random

class VideoUDPSender:
    MAX_SEQUENCE_NUMBER = 5000
    SYNC_INTERVAL = 3.0  # Segundos entre mensajes de sincronizacion

    def __init__(self, host='localhost', port=5000, max_packet_size=60000, jpeg_quality=60):
        """
        Emisor de video UDP con numero de secuencia para reordenar frames y sync periódico
        
        Argumentos:
            host: Dirección IP destino
            port: Puerto UDP destino  
            max_packet_size: Tamaño máximo por paquete UDP (bytes)
        """
        self.host = host # Dirección IP destino
        self.port = port # Puerto UDP destino
        self.max_packet_size = max_packet_size # Tamaño máximo por paquete UDP
        self.jpeg_quality = jpeg_quality # Calidad JPEG (1-100)
        self.socket = None # Socket UDP
        self.sequence_number = 0  # Secuencia inicial
        self.frame_count = 0 # Contador de frames enviados
        self.last_log_time = time.time() # Tiempo del último log

        # Variables para sincronizacion
        self.stream_id = random.randint(0, 0x7FFFFFFF)  # ID del stream
        self.sync_sequence = 0
        self.last_sync_time = 0
        self.is_streaming = False
        self.sync_thread = None

        # Configurar el socket inmediatamente
        if self.setup_udp_socket():
            # Enviar el paquete de sincronización si el socket se configuró bien
            self.send_sync(is_new_stream=True)
        
    def setup_udp_socket(self):
        """Configura el socket UDP para envío"""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 65536)
            print(f"Socket UDP configurado para enviar a {self.host}:{self.port}")
            return True
        except Exception as e:
            print(f"Error configurando socket UDP: {e}")
            return False

    def _sync_worker(self):
        """Hilo para enviar mensajes de sincronización periódicos"""
        while self.is_streaming:
            self.send_sync(is_new_stream=False)
            time.sleep(self.SYNC_INTERVAL)

    def start_periodic_sync(self):
        """Inicia el envío periodico de mensajes de sincronización"""
        if self.is_streaming:
            return
            
        self.is_streaming = True
        self.sync_thread = threading.Thread(target=self._sync_worker, daemon=True)
        self.sync_thread.start()
        print("Envío de mensajes de sincronizacion periódicos iniciado")

    def stop_periodic_sync(self):
        """Detiene el envío periódico de mensajes de sincronizacion"""
        self.is_streaming = False
        if self.sync_thread and self.sync_thread.is_alive():
            self.sync_thread.join(timeout=1.0)
        print("DDetenido envío de mensajes de sincronizacion periódicos")


    def send_sync(self, is_new_stream=False):
        """
        Envía mensaje de sincronización
        
        Argumentos:
            is_new_stream: Si es True, indica reinicio de stream
        """
        if self.socket is None:
            if not self.setup_udp_socket():
                return
                
        sync_message = {
            'type': 'sync',
            'sync_sequence': self.sync_sequence,
            'current_sequence': self.sequence_number,
            'stream_id': self.stream_id,
            'frame_count': self.frame_count,
            'timestamp': time.time(),
            'is_new_stream': is_new_stream
        }
        
        try:
            self.socket.sendto(pickle.dumps(sync_message), (self.host, self.port))
            
            if is_new_stream:
                print(f"Sincronización inicial - Stream: {self.stream_id}, Secuencia: {self.sequence_number}")
            else:
                # Logear cada 2 mensajes de sync
                if self.sync_sequence % 2 == 0:
                    print(f"Sincronización periódica número {self.sync_sequence} - Frame: {self.sequence_number}")
            
            self.sync_sequence += 1
            self.last_sync_time = time.time()
            
        except Exception as e:
            print(f"Error enviando SYNC: {e}")



    def send_frame(self, frame: np.ndarray) -> bool:
        """
        Envía un frame via UDP con número de secuencia consecutivo
        
        Argumentos:
            frame: Frame de video como numpy array
            
        Devuelve:
            bool: True si se envió correctamente
        """
        
        if self.socket is None:
            if not self.setup_udp_socket():
                return False
        
        # Iniciar la sincronización periódica si no está activa al enviar el primer frame
        if not self.is_streaming:
            self.start_periodic_sync()

        # Reinicio si el número de secuencia alcanza el máximo
        if self.sequence_number >= self.MAX_SEQUENCE_NUMBER:
            print(f"LÍMITE ALCANZADO: Reiniciando secuencia de {self.sequence_number} a 0")
            self.sequence_number = 0
            self.send_sync(is_new_stream=True)  # Mensaje de sincronización de reinicio

        try:
            # Codificar frame a JPEG
            encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), self.jpeg_quality]
            result, encoded_frame = cv2.imencode('.jpg', frame, encode_param)
            
            if not result:
                print("Error codificando frame a JPEG")
                return False
            
            jpeg_data = encoded_frame.tobytes()
            
            # Crear mensaje con secuencia y datos
            message = {
                'sequence': self.sequence_number,  #id para reordenar
                'jpeg_data': jpeg_data, # Datos JPEG
                'timestamp': time.time(), # Marca de tiempo
                'frame_shape': frame.shape, # Forma del frame
                'frame_count': self.frame_count, # Contador de frames enviados
                'stream_id': self.stream_id # id del stream
            }
            
            # Serializar y enviar
            data = pickle.dumps(message)
            
            # Verificar si necesita fragmentación
            if len(data) > self.max_packet_size:
                success = self._send_fragmented(frame)
            else:
                self.socket.sendto(data, (self.host, self.port))
                success = True
            
            if success:
                # INCREMENTAR secuencia después de enviar exitosamente
                self.sequence_number += 1
                self.frame_count += 1
                
                # Log cada segundo
                current_time = time.time()
                if current_time - self.last_log_time >= 1.0:
                    print(f"Frame {self.sequence_number} enviado")
                    self.last_log_time = current_time
                
            return success
                
        except Exception as e:
            print(f"Error enviando frame: {e}")
            return False

    def _send_fragmented(self, frame: np.ndarray) -> bool:
        """
        Envía un frame fragmentado con la misma secuencia para todos los fragmentos
        """
        try:
            # Codificar frame a JPEG
            encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), self.jpeg_quality]
            result, encoded_frame = cv2.imencode('.jpg', frame, encode_param)
            
            if not result:
                return False
            
            jpeg_data = encoded_frame.tobytes()

            # Verificar datos JPEG antes de enviar
            if not self._verify_jpeg_data(jpeg_data, self.sequence_number):
                print(f"Frame {self.sequence_number}: JPEG inválido - no enviado")
                return False
            
            # Fragmentar los datos JPEG
            total_packets = (len(jpeg_data) + self.max_packet_size - 1) // self.max_packet_size
            
            # Enviar paquete de inicio con metadata
            start_message = {
                'total_packets': total_packets,
                'sequence': self.sequence_number,  # Misma secuencia para todos los fragmentos
                'frame_shape': frame.shape,
                'frame_count': self.frame_count,
                'stream_id': self.stream_id
            }
            self.socket.sendto(pickle.dumps(start_message), (self.host, self.port))
            
            # Enviar fragmentos con la misma secuencia
            for i in range(total_packets):
                start_idx = i * self.max_packet_size
                end_idx = start_idx + self.max_packet_size
                packet_data = jpeg_data[start_idx:end_idx]
                
                packet_message = {
                    'packet_index': i,
                    'jpeg_data': packet_data,
                    'sequence': self.sequence_number  # Misma secuencia
                }
                
                self.socket.sendto(pickle.dumps(packet_message), (self.host, self.port))

                time.sleep(0.0005)  # Pequeña pausa para evitar congestion
            
            return True
            
        except Exception as e:
            print(f"Error enviando frame fragmentado: {e}")
            return False


    def _verify_jpeg_data(self, jpeg_data: bytes, sequence: int) -> bool:
        """
        Verifica que los datos JPEG sean válidos antes de enviarlos
        """
        try:
            # Verificar tamaño mínimo
            if len(jpeg_data) < 100:  # JPEG muy pequeño probablemente corrupto
                print(f"  ERROR Frame {sequence}: JPEG demasiado pequeño ({len(jpeg_data)} bytes)")
                return False
                
            # Verificar cabecera JPEG (FF D8)
            if jpeg_data[:2] != b'\xff\xd8':
                print(f"  ERROR Frame {sequence}: Cabecera JPEG inválida: {jpeg_data[:2].hex()}")
                return False
                
            # Verificar que podemos decodificar el JPEG localmente
            test_np = np.frombuffer(jpeg_data, dtype=np.uint8)
            test_frame = cv2.imdecode(test_np, cv2.IMREAD_COLOR)
            
            if test_frame is None:
                print(f"  ERROR Frame {sequence}: No se puede decodificar localmente")
                return False
                
            # Verificar dimensiones del frame decodificado
            if test_frame.size == 0:
                print(f"  ERROR Frame {sequence}: Frame decodificado vacío")
                return False
                
           # #Para debugging: Mostrar info del JPEG válido
           # if self.sequence_number % 50 == 0:  # Log cada 50 frames
           #     print(f"Frame {sequence}: JPEG válido - {len(jpeg_data)} bytes, shape: {test_frame.shape}")
                
            return True
            
        except Exception as e:
            print(f"  ERROR Frame {sequence}: Excepción en verificación: {e}")
            return False

    def get_stats(self):
        """Retorna estadísticas de envío"""
        return {
            'frames_sent': self.frame_count,
            'current_sequence': self.sequence_number,
            'target': f"{self.host}:{self.port}"
        }

    def release(self):
        """Cierra la conexión UDP"""
        if self.socket:
            self.socket.close()
            self.socket = None
        print("Emisor UDP cerrado")