require('dotenv').config(); // si usas .env

const mysql = require('mysql2');

const db = mysql.createConnection({
  host: process.env.DATABASE_HOST || '192.168.0.211',
  user: process.env.DATABASE_USER || 'grupo4',
  password: process.env.DATABASE_PASSWORD || '123456',
  database: process.env.DATABASE_NAME || 'hired_db',
  port: process.env.DATABASE_PORT || 3306
});

db.connect((err) => {
  if (err) {
    console.error('❌ Error de conexión:', err.message);
  } else {
    console.log('✅ Conexión correcta a la base de datos');
  }
  db.end();
});
