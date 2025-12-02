// Database configuration file
const host = process.env.DATABASE_HOST || '192.168.0.211';
const port = process.env.DATABASE_PORT || '3306';
const user = process.env.DATABASE_USER || 'grupo4';
const password = process.env.DATABASE_PASSWORD || '123456';
const database = process.env.DATABASE_NAME || 'hired_db';

module.exports = {
    HOST: host,
    PORT: port,
    USER: user,
    PASSWORD: password,
    DB: database,
    dialect: 'mysql',
    pool: {
        max: 5,
        min: 0,
        idle: 10000,
        acquire: 30000,
    }
};