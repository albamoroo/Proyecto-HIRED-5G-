import serial
import time
import re

PORT = "/dev/ttyUSB2"
BAUD = 115200


# Convertir coordenadas NMEA a decimal

def nmea_to_decimal(value):
    direction = value[-1]
    raw = value[:-1]

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


def obtener_gps():
    ser = serial.Serial(PORT, BAUD, timeout=1)
    time.sleep(1)

    # Activar GPS
    ser.write(b"AT+QGPS=1\r")
    time.sleep(2)
    ser.read(2000)

    # Solicitar posición
    ser.write(b"AT+QGPSLOC?\r")
    time.sleep(0.5)
    data = ser.read(2000).decode(errors="ignore")

    #print("\n======= RAW DATA =======")
    #print(repr(data))
    #print("========================\n")

    m = re.search(r'\+QGPSLOC:\s*([^ \r\n]+)', data)
    if not m:
        print("No se pudo leer QGPSLOC")
        return None

    campos = m.group(1).split(',')
    lat_raw = campos[1]
    lon_raw = campos[2]

    lat_dec = nmea_to_decimal(lat_raw)
    lon_dec = nmea_to_decimal(lon_raw)

    return lat_dec, lon_dec


if __name__ == "__main__":
    res = obtener_gps()

    if res:
        lat, lon = res
        print("   Latitud :", lat)
        print("   Longitud:", lon)
    else:
        print("No se obtuvo ninguna coordenada.")
