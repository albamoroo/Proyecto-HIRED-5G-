// Node.js application
// import the express application

const app = require('./app/app');
const http = require('http');
const {Server} = require('socket.io');
const videoRoutesModule = require('./app/routes/video.routes');
const server = http.createServer(app);
const io = new Server(server);

videoRoutesModule.setSocket(io);

io.on('connection', (socket) => {
  console.log('Client connected to Socket.IO:', socket.id);
});

// Listening for request at port 3000
const port = process.env.PORT || 3000;
server.listen(port, () => {
  console.log(`Service listening at ${port}`);
});

