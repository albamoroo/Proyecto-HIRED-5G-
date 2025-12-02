const child_process = require('child_process');

exports.encodeMp4 = (inputVideoPath, outputVideoPath) => {
// video with id=x -> inputVideoPath = /uploads/video-x.???
// video with id=x -> outputVideoPath = /videos/video-x.mp4
    return new Promise((resolve, reject) => {
        // ffmpeg command to convert the video to mp4 format with stardard codec
        const command = `ffmpeg -y -i ${inputVideoPath} ${outputVideoPath}`;

        // Encode
        child_process.exec(command, (err, stdout, stderr) => {
        if (err) {
            return reject(new Error(`Encoding error. ${stderr}`));
        }
        resolve(outputVideoPath);
        });
    });
}


function executeCommand(command, args) {
  return new Promise((resolve, reject) => {
      const process = child_process.spawn(command, args);

      process.on('error', (error) => {
          reject(new Error(`Failed to start command: ${command}`));
      });

      process.on('exit', (code, signal) => {
          if (code !== 0) {
              reject(new Error(`Command exited with code ${code}`));
          } else if (signal) {
              reject(new Error(`Command was killed with signal ${signal}`));
          } else {
              resolve();
          }
      });
  });
}


