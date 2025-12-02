const express = require("express");
const router = express.Router();

const { saveGPS, getGPS } = require("../controllers/gps.controller");

router.post("/", saveGPS);
router.get("/", getGPS);

module.exports = router;
