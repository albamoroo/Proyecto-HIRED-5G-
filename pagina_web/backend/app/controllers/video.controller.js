const Video = require('../models/db').Video;
const path = require('path');
const VideoConfig = require('../config/video.config');
const fs = require('fs');

// Obtener todos los vídeos
module.exports.getAll = async (req, res, next) => {
    const videos = await Video.findAll();
    res.status(200).json(videos);
};

// Obtener video por ID
module.exports.get = async (req, res,next) => {
  const video =  await Video.findByPk(req.params.id);
    if (video) {
        res.status(200).json(video);
    } else {
        res.status(404).json({ message: "Video no encontrado" });
    }
};


// Variables para la grabación de frames
let lastMetricCarCount = 0;
let lastMetricPersonCount = 0;
let lastMetricBiciCount = 0;
let frameCount = 0;
let frameFiles = [];
let staleTimer = null;
const STALE_MS = 3000;
const ffmpeg = require('fluent-ffmpeg');
const ffmpegPath = require('ffmpeg-static');
const ffprobePath = require('ffprobe-static').path;
ffmpeg.setFfmpegPath(ffmpegPath);
ffmpeg.setFfprobePath(ffprobePath);


// Manejar un frame recibido
module.exports.handleFrame = (frameData, metric_car_count, metric_person_count, metric_bici_count) => {
    // Directorio de uploads
    const uploadsDir = path.join(__dirname, '../../uploads');
    // Crea el directorio si no existe
    if (!fs.existsSync(uploadsDir)) fs.mkdirSync(uploadsDir);

    // Guarda cada frame con nombre secuencial
    const filePath = path.join(uploadsDir, `frame_${String(frameCount).padStart(5, '0')}.jpg`);
    // Escribe el archivo en el sistema
    fs.writeFileSync(filePath, Buffer.from(frameData.replace(/^data:image\/jpeg;base64,/, ''), 'base64'));
    // Agrega el archivo a la lista
    frameFiles.push(filePath);
    // Incrementa el contador de frames
    frameCount++;

    // Actualiza el conteo
    lastMetricCarCount = metric_car_count;
    lastMetricPersonCount = metric_person_count;
    lastMetricBiciCount = metric_bici_count;

    if (staleTimer) clearTimeout(staleTimer);
    // Si no llegan nuevos frames en STALE_MS tiempo guarda el vídeo
    staleTimer = setTimeout(async () => {
    const tempPath = await exports.framesToVideo();
    if (tempPath) {
        await exports.registerVideo(tempPath);
    }
}, STALE_MS);
};

// Función para guardar el vídeo a partir de los frames capturados
module.exports.framesToVideo = async () => {
    if (frameFiles.length === 0) return null;
    const uploadsDir = path.join(__dirname, '../../uploads');
    const fileName = `video_${Date.now()}.avi`;
    const relativePath = path.join('uploads', fileName);
    const inputPattern = path.join(uploadsDir, 'frame_%05d.jpg');

    // Crea el video a partir de los frames
    await new Promise((resolve, reject) => {
        ffmpeg(inputPattern)
            .inputFPS(20)
            .output(relativePath)
            .on('end', resolve)
            .on('error', reject)
            .run();
    });

    // "Guarda" el video en la base de datos
    const video = await Video.create({
        nombre: fileName,
        fecha_hora: new Date(),
        metrica_coches: lastMetricCarCount,
        metrica_personas: lastMetricPersonCount,
        metrica_bici: lastMetricBiciCount,
        duracion: 0,
        ruta_archivo: relativePath,
        procesado: false
    });

    // Limpia los frames temporales
    for (let i = 0; i < frameCount; i++) {
        const f = path.join(uploadsDir, `frame_${String(i).padStart(5, '0')}.jpg`);
        if (fs.existsSync(f)) fs.unlinkSync(f);
    }
    frameFiles = [];
    frameCount = 0;

    return relativePath;
};


module.exports.registerVideo = async (outputPath) => {
     const fileName = path.basename(outputPath);
    const videosDir = path.join(__dirname, '../../videos');
    const relativePath = path.join('videos', fileName.replace('.avi', '.mp4'));
    const finalPath = path.join(videosDir, fileName.replace('.avi', '.mp4'));

    // Crea el directorio si no existe
    if (!fs.existsSync(videosDir)) fs.mkdirSync(videosDir);

    // Convierte a MP4
    await new Promise((resolve, reject) => {
        ffmpeg(path.join(__dirname, '../../', outputPath))
            .output(finalPath)
            .videoCodec('libx264')
            .on('end', resolve)
            .on('error', reject)
            .run();
    });

    // Borra el archivo temporal
    fs.unlinkSync(path.join(__dirname, '../../', outputPath));

    // Usa la ruta absoluta para ffprobe
    const absolutePath = path.resolve(finalPath);

    // Verifica que el archivo existe y no está vacío
    if (!fs.existsSync(absolutePath) || fs.statSync(absolutePath).size === 0) {
        console.error('El archivo de vídeo no existe o está vacío:', absolutePath);
        return;
    }

    const duracion = await getVideoDuration(absolutePath);

    // Busca el vídeo por nombre
    const video = await Video.findOne({ where: { nombre: fileName } });
    if (video) {
        video.nombre = fileName.replace('.avi', '.mp4');
        video.duracion = duracion;
        video.ruta_archivo = relativePath;
        video.procesado = 1;
        await video.save();
        console.log('Vídeo actualizado en la base de datos:', relativePath);
    } else {
        console.warn('No se encontró el registro del vídeo para actualizar.');
    }
};


// Función auxiliar para obtener la duración del video
async function getVideoDuration(filePath) {
    return new Promise((resolve, reject) => {
        ffmpeg.ffprobe(filePath, (err, metadata) => {
            if (err) return reject(err);
            resolve(Math.round(metadata.format.duration)); // duración en segundos
        });
    });
}


