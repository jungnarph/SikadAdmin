// server.js (ESM version) - CORRECTED STRUCTURE
import mqtt from "mqtt";
import admin from "firebase-admin";
import express from "express";
import crypto from "crypto";
import * as turf from "@turf/turf";
import fs from "fs";
import fetch from "node-fetch";

// ==================== FIREBASE INIT ====================
let serviceAccount;
if (process.env.FIREBASE_KEY_JSON) {
  serviceAccount = JSON.parse(process.env.FIREBASE_KEY_JSON);
  console.log("🔑 Using FIREBASE_KEY_JSON from environment.");
} else {
  serviceAccount = JSON.parse(fs.readFileSync("./firebase-key.json", "utf8"));
  console.log("🔑 Using local firebase-key.json file.");
}

admin.initializeApp({
  credential: admin.credential.cert(serviceAccount),
  databaseURL: "https://cit306-finalproject-default-rtdb.firebaseio.com/",
});

const rtdb = admin.database();
const firestore = admin.firestore();

// ==================== EXPRESS INIT (MUST BE EARLY) ====================
const app = express();
const PORT = process.env.PORT || 3000;
app.use(express.json());

// ==================== MQTT SETUP ====================
const options = {
  host: "8cc8aa8a96bb432a8176c3457b76204c.s1.eu.hivemq.cloud",
  port: 8883,
  protocol: "mqtts",
  username: "esp32-client",
  password: "SikadRocks19!",
};

const client = mqtt.connect(options);

client.on("connect", () => {
  console.log("✅ Connected to HiveMQ");
  client.subscribe("esp32/gps/#", (err) => {
    if (!err) console.log("📡 Subscribed to esp32/gps/#");
  });
  client.subscribe("esp32/alerts", (err) => {
    if (!err) console.log("📡 Subscribed to esp32/alerts");
  });
});

// ==================== GEOFENCE CACHE ====================
let cachedGeofences = [];
let lastCacheTime = 0;
const CACHE_DURATION = 60 * 1000; // 1 minute

async function getActiveGeofences() {
  const now = Date.now();
  if (cachedGeofences.length && now - lastCacheTime < CACHE_DURATION) {
    return cachedGeofences;
  }

  const geofenceSnap = await firestore
    .collection("geofence")
    .where("is_active", "==", true)
    .get();

  const geofences = [];

  geofenceSnap.forEach((doc) => {
    const data = doc.data();
    if (data.points && data.points.length) {
      const coordinates = data.points.map((p) => [
        p.location.longitude,
        p.location.latitude,
      ]);

      // close the polygon if not closed
      if (
        coordinates[0][0] !== coordinates[coordinates.length - 1][0] ||
        coordinates[0][1] !== coordinates[coordinates.length - 1][1]
      ) {
        coordinates.push(coordinates[0]);
      }

      geofences.push({
        name: data.name,
        description: data.description,
        polygon: turf.polygon([coordinates]),
        color: data.color_code,
      });
    }
  });

  cachedGeofences = geofences;
  lastCacheTime = now;
  console.log(`📦 Cached ${geofences.length} active geofences`);
  return geofences;
}

// ==================== GEOFENCE CROSSING TRACKER ====================
const geofenceCrossings = {};
const CROSS_THRESHOLD = 3; // triggers alert after 3 crossings

// ==================== MOVEMENT ALERT TRACKER ====================
const movementAlerts = {};

// ==================== PHILSMS CONFIG ====================
const PHILSMS_API_TOKEN = "3186|RQCCqdWxPG9SuGOrqPvBdDoFIfeOmw0WqVDev9Vg";
const PHILSMS_SENDER_ID = "PhilSMS";

async function sendSMSAlert(bikeId, alertType = "geofence_cross") {
  const randomTag = Math.floor(Math.random() * 1000);

  let MESSAGE;
  if (alertType === "movement") {
    MESSAGE = `Notice: Bike ${bikeId} moved while parked. Ref#${randomTag}`;
  } else if (alertType === "crash") {
    MESSAGE = `ALERT: Bike ${bikeId} crash detected while on ride! Ref#${randomTag}`;
  } else {
    MESSAGE = `ALERT: Bike ${bikeId} exited geofence (Ref: ${randomTag})`;
  }

  try {
    const adminSnap = await firestore.collection("admin_accounts").get();
    const recipients = adminSnap.docs
      .map((doc) => doc.data().Number)
      .filter((num) => !!num);

    if (recipients.length === 0) {
      console.log("⚠️ No admin phone numbers found in admin_accounts.");
      return;
    }

    console.log(`📱 Sending ${alertType} alert to ${recipients.length} admin(s):`, recipients);

    const sendPromises = recipients.map(async (TO_NUMBER) => {
      try {
        const response = await fetch("https://app.philsms.com/api/v3/sms/send", {
          method: "POST",
          headers: {
            Authorization: `Bearer ${PHILSMS_API_TOKEN}`,
            "Content-Type": "application/json",
            Accept: "application/json",
          },
          body: JSON.stringify({
            recipient: TO_NUMBER,
            sender_id: PHILSMS_SENDER_ID,
            type: "plain",
            message: MESSAGE,
          }),
        });

        const text = await response.text();
        let result;
        try {
          result = JSON.parse(text);
        } catch {
          result = { status: "error", message: "Invalid JSON", raw: text };
        }

        if (result.message && result.message.includes("Telco Issues")) {
          console.log(`⚠️ Telco issue for ${TO_NUMBER}. Retrying...`);
          await new Promise((resolve) => setTimeout(resolve, 2000));
          // Retry logic here if needed
        }

        console.log(`SMS Result for ${TO_NUMBER}:`, result);
      } catch (err) {
        console.error(`❌ SMS failed for ${TO_NUMBER}:`, err.message);
      }
    });

    await Promise.all(sendPromises);
  } catch (err) {
    console.error("❌ sendSMSAlert error:", err);
  }
}

// ==================== MQTT MESSAGE HANDLER ====================
client.on("message", async (topic, message) => {
  try {
    const msg = message.toString();
    console.log(`📨 Received on ${topic}: ${msg}`);

    // Handle GPS location updates
    if (topic.startsWith("esp32/gps/")) {
      const bikeId = topic.split("/")[2];

      try {
        const data = JSON.parse(msg);

        if (!data.latitude || !data.longitude) {
          console.log(`⚠️ Invalid GPS data for ${bikeId}`);
          return;
        }

        // ===== 1. UPDATE FIREBASE RTDB (Real-time) =====
        await rtdb.ref(`bikes/${bikeId}`).update({
          latitude: data.latitude,
          longitude: data.longitude,
          speed: data.speed || 0,
          bike_model: data.bike_model || "Unknown",
          bike_type: data.bike_type || "REGULAR",
          status: data.status || "AVAILABLE",
          current_zone_id: data.current_zone_id || "",
          last_update: admin.database.ServerValue.TIMESTAMP,
        });

        console.log(`✅ Updated RTDB for bike ${bikeId}: [${data.latitude}, ${data.longitude}]`);

        // ===== 2. UPDATE FIRESTORE (Historical) =====
        const bikeRef = firestore.collection("bikes").doc(bikeId);
        await bikeRef.set(
          {
            current_location: new admin.firestore.GeoPoint(
              data.latitude,
              data.longitude
            ),
            status: data.status || "AVAILABLE",
            bike_model: data.bike_model || "Unknown",
            bike_type: data.bike_type || "REGULAR",
            current_zone_id: data.current_zone_id || "",
            updated_at: admin.firestore.FieldValue.serverTimestamp(),
          },
          { merge: true }
        );

        // ===== 3. ADD TO LOCATION HISTORY =====
        await bikeRef.collection("location_history").add({
          location: new admin.firestore.GeoPoint(data.latitude, data.longitude),
          speed: data.speed || 0,
          recorded_at: admin.firestore.FieldValue.serverTimestamp(),
        });

        // ===== 4. CHECK GEOFENCE VIOLATIONS =====
        const geofences = await getActiveGeofences();
        const point = turf.point([data.longitude, data.latitude]);
        let insideAnyFence = false;

        for (const gf of geofences) {
          if (turf.booleanPointInPolygon(point, gf.polygon)) {
            insideAnyFence = true;
            break;
          }
        }

        if (!insideAnyFence) {
          if (!geofenceCrossings[bikeId]) {
            geofenceCrossings[bikeId] = 0;
          }
          geofenceCrossings[bikeId]++;

          console.log(
            `⚠️ Bike ${bikeId} outside geofence (${geofenceCrossings[bikeId]}/${CROSS_THRESHOLD})`
          );

          if (geofenceCrossings[bikeId] >= CROSS_THRESHOLD) {
            await sendSMSAlert(bikeId, "geofence_cross");

            await firestore.collection("geofence_violations").add({
              bike_id: bikeId,
              location: new admin.firestore.GeoPoint(data.latitude, data.longitude),
              timestamp: admin.firestore.FieldValue.serverTimestamp(),
              violation_type: "GEOFENCE_EXIT",
            });

            geofenceCrossings[bikeId] = 0;
          }
        } else {
          geofenceCrossings[bikeId] = 0;
        }
      } catch (parseError) {
        console.error(`❌ Error parsing GPS data for ${bikeId}:`, parseError);
      }
    }

    // Handle alert messages
    if (topic === "esp32/alerts") {
      try {
        const alertData = JSON.parse(msg);
        const bikeId = alertData.bike_id;
        const alertType = alertData.type;

        console.log(`🚨 Alert from bike ${bikeId}: ${alertType}`);

        // Update bike status in RTDB
        await rtdb.ref(`bikes/${bikeId}`).update({
          status: alertType === "crash" ? "OFFLINE" : "MAINTENANCE",
          last_alert: alertType,
          last_alert_time: admin.database.ServerValue.TIMESTAMP,
        });

        // Send SMS alert
        await sendSMSAlert(bikeId, alertType);

        // Log alert to Firestore
        await firestore.collection("bike_alerts").add({
          bike_id: bikeId,
          alert_type: alertType,
          latitude: alertData.latitude || null,
          longitude: alertData.longitude || null,
          timestamp: admin.firestore.FieldValue.serverTimestamp(),
          status: "PENDING",
        });
      } catch (alertError) {
        console.error("❌ Error processing alert:", alertError);
      }
    }
  } catch (error) {
    console.error("❌ Error handling MQTT message:", error);
  }
});

// ==================== EXPRESS API ENDPOINTS ====================

// Health check
app.get("/", (req, res) => {
  res.json({ status: "SIKAD Server Running", timestamp: new Date().toISOString() });
});

// Token generator
function generateToken() {
  return crypto.randomBytes(16).toString("hex");
}

app.get("/generate-token", async (req, res) => {
  const { bikeId, qrCode } = req.query;
  if (!bikeId || !qrCode) {
    return res.status(400).json({ error: "Missing bikeId or qrCode" });
  }

  const token = generateToken();
  const expiresAt = Date.now() + 5 * 60 * 1000;

  await firestore
    .collection("bikes")
    .doc(bikeId)
    .collection("tokens")
    .doc(token)
    .set({
      qrCode,
      createdAt: admin.firestore.FieldValue.serverTimestamp(),
      expiresAt,
      used: false,
    });

  res.json({ token });
});

// Payment success endpoint (existing)
app.get("/success", async (req, res) => {
  const { bikeId, qrCode, token, userId, rideTime, amount } = req.query;
  if (!bikeId || !qrCode || !token || !userId || !amount) {
    return res.status(400).send("Missing parameters.");
  }

  try {
    const tokenRef = firestore
      .collection("bikes")
      .doc(bikeId)
      .collection("tokens")
      .doc(token);
    const tokenSnap = await tokenRef.get();
    if (!tokenSnap.exists) return res.status(400).send("Invalid token.");
    const tokenData = tokenSnap.data();
    if (tokenData.used) return res.status(400).send("Token already used.");
    if (Date.now() > tokenData.expiresAt) return res.status(400).send("Token expired.");

    await tokenRef.update({ used: true });

    const paymentRef = await firestore.collection("payments").add({
      uid: userId,
      paymentAccount: "miggy account",
      paymentType: "gcash",
      paymentStatus: "successful",
      amount,
      paymentDate: admin.firestore.FieldValue.serverTimestamp(),
      isDeleted: false,
      deletedAt: null,
    });

    const paymentId = paymentRef.id;

    const rideRef = await firestore.collection("ride_logs").add({
      bikeId,
      userId,
      paymentId,
      startTime: admin.firestore.FieldValue.serverTimestamp(),
      endTime: null,
      points: [],
      isDeleted: false,
      deletedAt: null,
    });

    const rideId = rideRef.id;

    await firestore.collection("bikes").doc(bikeId).update({
      status: "paid",
      isActive: true,
      rentedBy: userId,
      activeRideId: rideId,
    });

    const blinkPayload = {
      command: "blink",
      qrCode,
      userId,
      rideTime,
    };
    client.publish(`esp32/cmd/${bikeId}`, JSON.stringify(blinkPayload));

    console.log(
      `⬇️ Ride started for ${bikeId}, rideId: ${rideId}, paymentId: ${paymentId}, amount: ${amount}, rideTime: ${rideTime}`
    );

    const redirectUrl = `myapp://main?payment_status=success&bikeId=${bikeId}&rideId=${rideId}&userId=${userId}`;
    res.redirect(redirectUrl);
  } catch (err) {
    console.error("❌ /success error:", err);
    res.status(500).send("Internal server error.");
  }
});

// ==================== NEW API ENDPOINTS FOR BIKE LOCATION ====================

// Manual bike location update
app.post("/api/bikes/:bikeId/location", async (req, res) => {
  try {
    const { bikeId } = req.params;
    const { latitude, longitude, speed, status } = req.body;

    if (!latitude || !longitude) {
      return res.status(400).json({ error: "Latitude and longitude are required" });
    }

    // Update RTDB
    await rtdb.ref(`bikes/${bikeId}`).update({
      latitude: parseFloat(latitude),
      longitude: parseFloat(longitude),
      speed: speed ? parseFloat(speed) : 0,
      status: status || "AVAILABLE",
      last_update: admin.database.ServerValue.TIMESTAMP,
    });

    // Update Firestore
    const bikeRef = firestore.collection("bikes").doc(bikeId);
    await bikeRef.update({
      current_location: new admin.firestore.GeoPoint(
        parseFloat(latitude),
        parseFloat(longitude)
      ),
      status: status || "AVAILABLE",
      updated_at: admin.firestore.FieldValue.serverTimestamp(),
    });

    res.json({
      success: true,
      message: `Location updated for bike ${bikeId}`,
    });
  } catch (error) {
    console.error("Error updating bike location:", error);
    res.status(500).json({ error: error.message });
  }
});

// Get all bikes
app.get("/api/bikes", async (req, res) => {
  try {
    const snapshot = await rtdb.ref("bikes").once("value");
    const bikes = [];

    snapshot.forEach((childSnapshot) => {
      bikes.push({
        bike_id: childSnapshot.key,
        ...childSnapshot.val(),
      });
    });

    res.json({ success: true, bikes });
  } catch (error) {
    console.error("Error fetching bikes:", error);
    res.status(500).json({ error: error.message });
  }
});

// ==================== CLEANUP FUNCTION ====================
async function cleanupInactiveBikes() {
  try {
    const snapshot = await rtdb.ref("bikes").once("value");
    const now = Date.now();
    const INACTIVE_THRESHOLD = 24 * 60 * 60 * 1000; // 24 hours

    snapshot.forEach((childSnapshot) => {
      const bikeData = childSnapshot.val();
      const lastUpdate = bikeData.last_update || 0;

      if (now - lastUpdate > INACTIVE_THRESHOLD) {
        console.log(`🗑️ Removing inactive bike: ${childSnapshot.key}`);
        rtdb.ref(`bikes/${childSnapshot.key}`).remove();
      }
    });
  } catch (error) {
    console.error("Error cleaning up bikes:", error);
  }
}

// Run cleanup every hour
setInterval(cleanupInactiveBikes, 60 * 60 * 1000);

// ==================== START SERVER ====================
app.listen(PORT, () => {
  console.log(`🚀 Server running on port ${PORT}`);
  console.log(`📍 API: http://localhost:${PORT}`);
  console.log(`🗺️  Bikes API: http://localhost:${PORT}/api/bikes`);
});