import serial
import time
import re
import json
import requests

PORT = "/dev/ttyUSB2"
BAUD = 115200

SERVER_IP = "192.168.0.211"
URL = f"http://{SERVER_IP}:3000/gps"

# ---------------------------------------------------------
# Convertir coordenadas NMEA a decimal
# ---------------------------------------------------------
def nmea_to_decimal(value):
    """
    Convierte '4321.6677N' o '00551.6287W' en decimal.
    """
    direction = value[-1]        # N / S / E / W
    raw = value[:-1]             # '4321.6677'

    if direction in ["N", "S"]:
        deg = int(raw[:2])
        minutes = float(raw[2:])
    else:
        deg = int(raw[:3])
        minutes = float(raw[3:])

    decimal = deg + minutes / 60.0

    if direction in ["S", "W"]:
        decimal = -decimal

    return decimal


# ---------------------------------------------------------
def obtener_gps(ser):
    ser.write(b"AT+QGPSLOC?\r")
    time.sleep(0.5)
    data = ser.read(2000).decode(errors="ignore")

    print("\n======= RAW DATA =======")
    print(repr(data))
    print("========================\n")

    m = re.search(r'\+QGPSLOC:\s*([^ \r\n]+)', data)
    if not m:
        return None

    campos = m.group(1).split(',')
    lat_raw = campos[1]
    lon_raw = campos[2]

    # Convertir a decimal
    lat_dec = nmea_to_decimal(lat_raw)
    lon_dec = nmea_to_decimal(lon_raw)

    return lat_dec, lon_dec


# ---------------------------------------------------------
def main():
    ser = serial.Serial(PORT, BAUD, timeout=1)
    time.sleep(1)

    print("Activando GPS ...")
    ser.write(b"AT+QGPS=1\r")
    time.sleep(2)
    ser.read(2000)

    print("GPS activado.\n")

    last_lat = None
    last_lon = None

    while True:
        pos = obtener_gps(ser)

        if pos:
            last_lat, last_lon = pos
            print("[OK] Decimal:", last_lat, last_lon)
        else:
            print("[FALLO] No se encontró +QGPSLOC en la respuesta.")

        if last_lat:
            payload = {
                "latitud": last_lat,
                "longitud": last_lon
            }

            print("POST a:", URL)
            print("Payload:", payload)

            try:
                r = requests.post(URL, json=payload)
                print("→ Enviado, status:", r.status_code)
            except Exception as e:
                print("Error enviando:", e)

        print()
        time.sleep(2)


if __name__ == "__main__":
    main()
