let lastGPS = null;
const TIMEOUT = 10000; // 10 segundos para considerar la coordenada "reciente"

function saveGPS(req, res) {
    const { latitud, longitud } = req.body;

    if (!latitud || !longitud) {
        return res.status(400).json({ error: "Missing lat/lon" });
    }

    lastGPS = { latitud, longitud, timestamp: Date.now() };
    console.log("GPS recibido:", lastGPS);

    res.json({ status: "OK" });
}

// Devuelve la última coordenada solo si es reciente
function getGPS(req, res) {
    if (!lastGPS) {
        return res.status(404).json({ error: "No GPS data yet" });
    }

    const now = Date.now();
    if (now - lastGPS.timestamp > TIMEOUT) {
        // La coordenada ya no es reciente → consideramos que no hay datos
        return res.status(404).json({ error: "No recent GPS data" });
    }

    res.json(lastGPS);
}

module.exports = { saveGPS, getGPS };
