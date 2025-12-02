// Express application

// Import modules
const express = require('express'); // Web framework for Node.js
const path = require('path');  // Utilities for working with file and directory paths
const fileUpload = require('express-fileupload'); // Para subir videos
const cors = require('cors'); // Middleware para habilitar CORS
//const videos = require('./routes/video.routes'); // Import the videos routes module

const { router: videos, setSocket } = require('./routes/video.routes');
const gps = require('./routes/gps.routes'); 
const db = require('./models/db'); // Import the database module
const winston = require('winston'); // Logging library
const expressWinston = require('express-winston'); // Middleware for logging HTTP requests and responses
const bodyParser = require('body-parser'); // Middleware to parse incoming request bodies

const app = express(); // Create an Express application

db.sequelize.sync(); // Sync database models
 

app.use(expressWinston.logger({
    transports: [
      new winston.transports.Console(),
    ]
}));

app.use(cors()); 
app.use(express.json({ limit: '20mb' })); // Middleware to parse JSON request bodies with a size limit

app.use(bodyParser.json()); 
app.use(bodyParser.urlencoded({ extended: true }));
app.use(express.static(path.join(__dirname, '../../frontend')));
app.use('/video', videos); 
app.use('/videos', express.static(path.join(__dirname, '../videos')));
app.use('/gps', gps);

// Ruta para la página index.html
app.get('/', (req, res) => {
    res.sendFile(path.join(__dirname, '../../frontend', 'index.html'));
});

// Ruta para conocer el estado
app.get('/status', (req, res) => {
    res.json({message: 'This is a video service for HIRED-5G project'});
});

// Se exporta la app para que index.js pueda usarla 
module.exports = app;
