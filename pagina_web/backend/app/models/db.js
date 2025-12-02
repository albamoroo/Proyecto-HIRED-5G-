
// Database creation 

// Import modules
const dbConfig = require('../config/db.config.js');
const Sequelize = require('sequelize');

// Create a connection pool to the database
const sequelize = new Sequelize(dbConfig.DB, dbConfig.USER, dbConfig.PASSWORD, {
    host: dbConfig.HOST,
    port: dbConfig.PORT,
    dialect: dbConfig.dialect,
    operatorAliases: false,
    logging: false,
    pool: {
        max: dbConfig.max,
        min: dbConfig.min,
        idle: dbConfig.idle,
        acquire: dbConfig.acquire
    }
});

const db = {};

db.Sequelize = Sequelize;
db.sequelize = sequelize;

// Load models
db.Video = require('./video.model.js')(sequelize, Sequelize);

module.exports = db;