const express = require('express');
const router = express.Router();
const videoController = require('../controllers/video.controller.js'); 
let io = null;

function setSocket(socketIo) {
    io = socketIo;

    // Opcional: log cuando un cliente se conecta
    io.on('connection', (socket) => {
        console.log('Socket connected:', socket.id);
    });
}

// Rutas REST para videos
router.get('/', videoController.getAll);       // Obtener todos los videos
router.get('/:id', videoController.get);      // Obtener video por ID

router.post('/', async (req, res) => {
    const { frame, metric_car_count, metric_person_count, metric_bici_count } = req.body;
    console.log('Recibido:', { frame: !!frame, metric_car_count, metric_person_count, metric_bici_count }); // Muestra si llega el dato
    if (!frame) return res.status(400).json({ message: 'No frame provided' });

    // Emitir con el nombre de evento que el frontend ya espera: "frame"
    if (io) {
        io.emit('frame', { frame, metric_car_count, metric_person_count, metric_bici_count });
        videoController.handleFrame(frame, metric_car_count, metric_person_count, metric_bici_count); //Llama al controlador para guardar frame
        return res.sendStatus(200);
    } else {
        // Si no hay socket conectado al servidor todavía, devolver 503
        return res.status(503).json({ message: 'Socket.IO not initialized on server' });
    }
});

module.exports = {router,setSocket};
