module.exports = (sequelize, Sequelize) => {
  const Video = sequelize.define("videos", {
    id_video: {
      type: Sequelize.INTEGER,
      autoIncrement: true,
      primaryKey: true
    },
    nombre: {
      type: Sequelize.STRING(255),
      allowNull: false
    },
    fecha_hora: {
      type: Sequelize.DATE,
      allowNull: true
    },
    metrica_coches: {
      type: Sequelize.INTEGER,
      allowNull: true
    },
     metrica_personas: {
      type: Sequelize.INTEGER,
      allowNull: true
    },
     metrica_bici: {
      type: Sequelize.INTEGER,
      allowNull: true
    },
    duracion: {
      type: Sequelize.INTEGER,
      allowNull: true
    },
    ruta_archivo: {
      type: Sequelize.STRING(500),
      allowNull: true
    },
    procesado: {
      type: Sequelize.TINYINT,
      allowNull: true
    }
   
  }, {
    tableName: "videos", // ← asegura que Sequelize use exactamente este nombre
    timestamps: false    // ← si no tienes createdAt / updatedAt en la tabla
  });

  return Video;
};
