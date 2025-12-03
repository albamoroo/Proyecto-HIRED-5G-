import socket
import requests
import base64
import cv2
import threading
import queue
import numpy as np
import pickle
import time
from collections import OrderedDict


class VideoUDPReceiver:

    MAX_SEQUENCE_NUMBER = 5000 # Máximo número de secuencia antes de reiniciar
    RESET_THRESHOLD = 1000        # Umbral para detectar reinicio de secuencia
    SYNC_TIMEOUT = 10.0  # Timeout para considerar mensaje de sync perdido

    def __init__(self, host='0.0.0.0', port=5000, buffer_size=4*1024*1024, queue_size=10, 
                 socket_timeout=10, log_frequency=30, auto_start=True,
                 max_reorder_buffer=50, frame_timeout=5.0):
        """
        Receptor de video via UDP con reordenación completa
        
        Args:
            host: Direccion IP para escuchar
            port: Puerto UDP para escuchar  
            buffer_size: Tamaño del buffer de recepción UDP (esta puesto a 4 MB si no me equivoco)
            queue_size: Tamaño máximo de la cola interna de frames
            socket_timeout: Timeout del socket en segundos
            log_frequency: Frecuencia para imprimir logs
            auto_start: ejecuta VideoUDPReceiver.start() automaticamente
            max_reorder_buffer: Máximo frames en buffer para reordenar
            frame_timeout: Timeout para frames incompletos (segundos)
        """
        # Parámetros de configuración
        self.host = host
        self.port = port
        self.buffer_size = buffer_size
        self.queue_size = queue_size
        self.socket_timeout = socket_timeout
        self.log_frequency = log_frequency
        self.max_reorder_buffer = max_reorder_buffer
        self.frame_timeout = frame_timeout
        
        # Estado interno
        self.frame_queue = queue.Queue(maxsize=queue_size)
        self.stop_event = threading.Event()
        self.thread = threading.Thread(target=self._receiver, daemon=True)
        self.socket = None
        
        # Para reordenación
        self.next_expected_sequence = 0 # siguiente número de secuencia esperado
        self.reorder_buffer = OrderedDict()  #  buffer para reordenar frames
        self.sequence_counter = 0 # número de secuencia total de frames entregados

        # Para sincronización
        self.current_stream_id = None
        self.last_sync_time = 0
        self.sync_received = False
        
        if auto_start:
            self.start()

    def setup_udp_socket(self):
        """Configura el socket UDP"""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, self.buffer_size)
            self.socket.bind((self.host, self.port))
            self.socket.settimeout(self.socket_timeout)
            
            print("Socket UDP configurado:")
            print(f"  - Host: {self.host}")
            print(f"  - Puerto: {self.port}")
            print(f"  - Tamaño del buffer: {self.buffer_size} bytes")
            print(f"  - Tamaño de la cola: {self.queue_size}")
            
            return True
            
        except Exception as e:
            print(f"Error configurando socket UDP: {e}")
            return False

    def _receiver(self):
        """Hilo principal que recibe y reordena frames via UDP"""
        if not self.setup_udp_socket():
            return
            
        print(f"Esperando frames UDP en {self.host}:{self.port}...")
        
        # Variables para frames fragmentados
        expected_packets = 0 # número esperado de paquetes para el frame actual
        frame_data = {} # datos de fragmentos del frame actual
        current_sequence = 0 # número de secuencia del frame actual
        fragment_start_time = 0 # tiempo de inicio de recepción del frame fragmentado
        
        while not self.stop_event.is_set():
            try:
                # Espera a recibir datos UDP
                data, addr = self.socket.recvfrom(self.buffer_size)
                
                try:
                    #Deserializar paquete UDP
                    packet_info = pickle.loads(data)
                except Exception as e:
                    print(f"Error deserializando paquete UDP: {e}")
                    continue
                
                # Procesar segun tipo de paquete
                if 'type' in packet_info and packet_info['type'] == 'sync': # Paquete de sincronización
                    self._process_sync_packet(packet_info)
                    continue

                elif 'total_packets' in packet_info: # Si es un fragmento inicial
                    # Frame fragmentado - empezar reconstrucción
                    expected_packets = packet_info['total_packets']
                    frame_data = {}
                    current_sequence = packet_info.get('sequence', 0)
                    fragment_start_time = time.time()
                    print(f"Frame {current_sequence} fragmentado - esperando {expected_packets} paquetes")
                    
                elif 'packet_index' in packet_info and 'jpeg_data' in packet_info: # Si es fragmento de frame
                    packet_index = packet_info['packet_index']
                    frame_data[packet_index] = packet_info['jpeg_data']
                    print(f"Fragmento {packet_index}/{expected_packets} recibido para frame {current_sequence}")
                    
                    # Verificar si tenemos todos los fragmentos
                    if len(frame_data) >= expected_packets and expected_packets > 0: # Todos los fragmentos recibidos
                        self._reconstruct_fragmented_frame(frame_data, current_sequence, expected_packets)
                        expected_packets = 0
                        frame_data = {}
                
                elif 'jpeg_data' in packet_info:
                    # Frame completo
                    sequence = packet_info.get('sequence', 0)
                    
                    # Vreificar si es realmente frame completo
                    jpeg_data = packet_info['jpeg_data']
                    has_header = jpeg_data[:2] == b'\xff\xd8'
                    has_footer = jpeg_data[-2:] == b'\xff\xd9' if len(jpeg_data) >= 2 else False
                    
                    if has_header and has_footer:
                        # Es un frame completo válido
                        self._process_complete_frame(packet_info, addr, sequence)
                    else:
                        # Probablemente es un fragmento que no fue detectado
                        print(f"Frame {sequence} incompleto - header: {has_header}, footer: {has_footer}")
                        # Podemos intentar procesarlo de todos modos o ignorarlo
                        self._process_complete_frame(packet_info, addr, sequence)


                if self.sync_received and time.time() - self.last_sync_time > self.SYNC_TIMEOUT:
                    print(f"No se reciben syncs periodicos durante {self.SYNC_TIMEOUT} - stream inestable")
                    self.sync_received = False        
                
                # Timeout para frames fragmentados incompletos
                if expected_packets > 0 and time.time() - fragment_start_time > self.frame_timeout:
                    print(f"Timeout - descartando frame fragmentado incompleto {current_sequence}")
                    expected_packets = 0
                    frame_data = {}
                    
            except socket.timeout:
                # Verificar timeouts durante el timeout del socket
                if expected_packets > 0 and time.time() - fragment_start_time > self.frame_timeout:
                    print(f"Timeout - descartando frame fragmentado incompleto {current_sequence}")
                    expected_packets = 0
                    frame_data = {}
                continue
            except Exception as e:
                if not self.stop_event.is_set():
                    print(f"Error recibiendo datos UDP: {e}")


    def _process_sync_packet(self, sync_packet):
        """Procesa mensaje de sincronización con stream_id"""
        stream_id = sync_packet.get('stream_id')
        new_sequence = sync_packet.get('current_sequence', 0)
        is_new_stream = sync_packet.get('is_new_stream', False)
        sync_sequence = sync_packet.get('sync_sequence', 0)
        
        print(f"Sync recibido numero {sync_sequence} - Stream: {stream_id}, Secuencia: {new_sequence}, Nuevo: {is_new_stream}")
        
        # Sincronización y manejo de cambios de stream
        if self.current_stream_id is None: # Primer sync recibido
            # Primer sync recibido
            self.current_stream_id = stream_id
            self.next_expected_sequence = new_sequence
            self.reorder_buffer.clear()
            print(f"Sync inicial - Stream ID: {stream_id}, empezando en secuencia: {new_sequence}")
            
        elif self.current_stream_id != stream_id: # Cambio de stream detectado
            print(f"Nuevo stream detectado: {self.current_stream_id} -> {stream_id}")
            self.current_stream_id = stream_id
            self.next_expected_sequence = new_sequence
            self.reorder_buffer.clear()
            
        elif is_new_stream: # Reinicio del mismo stream
            print(f"Reinicio de stream - Nueva secuencia: {new_sequence}")
            self.next_expected_sequence = new_sequence
            self.reorder_buffer.clear()
            
        else:
            # Sync periódico normal - solo log y corrección  de drift
            packet_drift = new_sequence - self.next_expected_sequence
            if abs(packet_drift) > 100:  # Umbral para corrección
                print(f"Corrigiendo drift: {packet_drift} paquetes")
                self.next_expected_sequence = new_sequence
        
        self.last_sync_time = time.time()
        self.sync_received = True


    def _process_complete_frame(self, message, addr, sequence):
        """Procesa un frame completo y lo reordena"""
        try:
            # Verificar si es un frame duplicado
            if sequence in self.reorder_buffer:
                print(f"Frame duplicado {sequence} - ignorando")
                return

            jpeg_data = message['jpeg_data']
             
            # Intentar decodificar con diferentes métodos
            np_data = np.frombuffer(jpeg_data, dtype=np.uint8)
            frame = cv2.imdecode(np_data, cv2.IMREAD_COLOR)
            
            if frame is None:
                # Intentar métodos alternativos
                frame = cv2.imdecode(np_data, cv2.IMREAD_ANYCOLOR)
                
            if frame is None:
                frame = cv2.imdecode(np_data, cv2.IMREAD_UNCHANGED)
            
            if frame is not None:
                self._add_to_reorder_buffer(sequence, frame, addr)
            else:
                print(f"Todos los métodos de decodificación fallaron para frame {sequence}")

                        
        except Exception as e:
            print(f"Error procesando frame {sequence}: {e}")

    def _reconstruct_fragmented_frame(self, frame_data, sequence, total_packets):
        """Reconstruye y reordena un frame fragmentado"""
        try:

            # Verificar si es un frame duplicado ANTES de procesar
            if sequence in self.reorder_buffer:
                print(f"Frame fragmentado duplicado {sequence} - ignorando")
                return

            # Verificar que tenemos todos los paquetes
            if len(frame_data) < total_packets: # Si la cantidad de fragmentos es menor que la esperada
                print(f"Faltan paquetes para frame {sequence}: {len(frame_data)}/{total_packets}")
                return
            
            # Reordenar fragmentos por índice
            sorted_indices = sorted(frame_data.keys())  # Indices ordenados
            if sorted_indices != list(range(total_packets)): # Si faltan índices
                print(f"Paquetes faltantes en frame {sequence}: {sorted_indices}")
                return
            
            # Reensamblar frame
            jpeg_combined = b''.join([frame_data[i] for i in sorted_indices]) # Combinar fragmentos concatenando bytes
            np_data = np.frombuffer(jpeg_combined, dtype=np.uint8)
            frame = cv2.imdecode(np_data, cv2.IMREAD_COLOR)
            
            # Añadir frame al buffer de reordenación
            if frame is not None:
                self._add_to_reorder_buffer(sequence, frame, None)
            else:
                print(f"Error decodificando frame fragmentado {sequence}")
                    
        except Exception as e:
            print(f"Error reconstruyendo frame {sequence}: {e}")


    def _add_to_reorder_buffer(self, sequence, frame, addr):
        """Añade frame al buffer de reordenación con lógica de auto-reparación"""
        
        if sequence < self.next_expected_sequence and \
       (self.next_expected_sequence - sequence) > self.MAX_SEQUENCE_NUMBER - self.RESET_THRESHOLD:
        
            print(f"Frame {sequence}: Detectado posible reinicio de secuencia. Forzando SYNC.")
            self.next_expected_sequence = sequence # Establece a 0
            self.reorder_buffer.clear() # Limpia todo


        # Si acabamos de arrancar (esperamos 0) y recibimos un numero alto (ej. 6000),
        # y el buffer está vacío, saltamos directamente a ese número.
        if not self.sync_received and self.next_expected_sequence == 0 and sequence > 10 and len(self.reorder_buffer) == 0:
            print(f"Saltando a secuencia {sequence} (sin mensaje de sync previo)")
            self.next_expected_sequence = sequence

        # Guardar frame en buffer de reordenación
        self.reorder_buffer[sequence] = {
            'frame': frame,
            'timestamp': time.time(),
            'addr': addr
        }

        # Si el buffer está lleno, significa que hay un hueco que no se ha llenado.
        # Debemos forzar el avance para no quedarnos atascados esperando un frame perdido.
        if len(self.reorder_buffer) >= self.max_reorder_buffer:
            # Encontrar el número de secuencia más bajo disponible en el buffer
            min_seq_in_buffer = min(self.reorder_buffer.keys())
            
            # Si lo que estamos esperando es menor que lo más viejo que tenemos en el buffer,
            # significa que el frame esperado se perdió para siempre y debemos saltar.
            if self.next_expected_sequence < min_seq_in_buffer:
                lost_count = min_seq_in_buffer - self.next_expected_sequence
                print(f"Buffer lleno. Saltando {lost_count} frames perdidos ({self.next_expected_sequence} -> {min_seq_in_buffer})")
                self.next_expected_sequence = min_seq_in_buffer
            
            # Si aún así sigue lleno , eliminar el más viejo 
            if len(self.reorder_buffer) >= self.max_reorder_buffer:
                oldest_seq = min(self.reorder_buffer.keys())
                del self.reorder_buffer[oldest_seq]
                # Si eliminamos justo el que esperabamos, avanzamos el contador
                if oldest_seq == self.next_expected_sequence:
                     self.next_expected_sequence += 1
        
        # Entregar frames en orden
        self._deliver_ordered_frames()

    def _deliver_ordered_frames(self):
        """Entrega frames en orden secuencial a la cola principal"""
        # Entregar todos los frames en orden secuencial
        while self.next_expected_sequence in self.reorder_buffer:
            # Obtener frame del buffer
            frame_data = self.reorder_buffer[self.next_expected_sequence]
            # Extraer frame y dirección del remitente
            frame = frame_data['frame']
            addr = frame_data['addr']
            
            # Añadir a cola principal
            self._add_to_queue(frame)
            
            # Logear entrega
            self.sequence_counter += 1
            if self.sequence_counter % self.log_frequency == 0:
                addr_str = f"de {addr[0]}:{addr[1]}" if addr else "fragmentado"
                print(f"Frame {self.sequence_counter} entregado ({self.next_expected_sequence}) {addr_str}")
            
            # Limpiar buffer y avanzar
            del self.reorder_buffer[self.next_expected_sequence]
            self.next_expected_sequence += 1
        
        # Limpiar frames muy viejos en el buffer
        current_time = time.time()
        expired_sequences = []
        # Buscar frames que han excedido el timeout
        for seq, data in self.reorder_buffer.items():
            if current_time - data['timestamp'] > self.frame_timeout:
                expired_sequences.append(seq)
        
        # Eliminar frames expirados
        for seq in expired_sequences:
            del self.reorder_buffer[seq]
            print(f"Timeout - descartando frame {seq} del buffer de reordenación")

    def _add_to_queue(self, frame):
        """Añade frame a la cola interna"""
        try:
            self.frame_queue.put_nowait(frame)
        except queue.Full:
            try:
                self.frame_queue.get_nowait()
            except queue.Empty:
                pass
            self.frame_queue.put_nowait(frame)

    def get_frame(self, timeout=None):
        if self.stop_event.is_set():
            return None
        try:
            return self.frame_queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def start(self):
        if not self.thread.is_alive():
            self.thread.start()
            print("Receptor UDP iniciado")

    def release(self):
        self.stop_event.set()
        if self.socket:
            self.socket.close()
        if self.thread.is_alive():
            self.thread.join(timeout=5)
        print("Receptor UDP cerrado")

    def get_queue_size(self):
        return self.frame_queue.qsize()

    def is_alive(self):
        return self.thread.is_alive()
    
    # Consulta el stream_id actual (se usa para identificar cambios de stream
    # y reiniciar las métricas)
    def get_stream_id(self):
        return self.current_stream_id



# Clase para enviar frames a un servidor HTTP
class VideoHTTPSender:
    def __init__(self, upload_url):
        self.upload_url = upload_url

    # Envía un frame (imagen) a un servidor HTTP en formato base64
    def send_frame(self, sessionId, frame, car_count, person_count, bici_count):
        # Codificar el frame como JPEG
        _, buf = cv2.imencode(".jpg", frame)

        # Codificar a base64
        jpg_as_text = base64.b64encode(buf).decode()

        # Enviar el frame al servidor HTTP
        try:
            requests.post(
                self.upload_url,
                json={
                    "sessionId": sessionId,
                    "frame": f"data:image/jpeg;base64,{jpg_as_text}",
                    "metric_car_count": car_count,
                    "metric_person_count": person_count,
                    "metric_bici_count": bici_count,
                },
                timeout=1,
            )
        except requests.exceptions.RequestException:
            time.sleep(0.1)
