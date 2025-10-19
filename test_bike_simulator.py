#!/usr/bin/env python3
"""
Bike Location Simulator - For testing real-time map updates
Simulates bikes moving around Bulacan area
"""

import time
import random
import json
import paho.mqtt.client as mqtt
from datetime import datetime

# MQTT Configuration
MQTT_BROKER = "8cc8aa8a96bb432a8176c3457b76204c.s1.eu.hivemq.cloud"
MQTT_PORT = 8883
MQTT_USERNAME = "esp32-client"
MQTT_PASSWORD = "SikadRocks19!"

# Starting location (Bulacan center)
BASE_LAT = 14.8433
BASE_LNG = 120.8111

# Simulate these bikes
BIKES = [
    {"id": "BIKE001", "model": "Mountain Bike Pro", "type": "MOUNTAIN", "status": "IN_USE"},
    {"id": "BIKE002", "model": "City Cruiser", "type": "REGULAR", "status": "IN_USE"},
    {"id": "BIKE003", "model": "E-Bike Deluxe", "type": "ELECTRIC", "status": "IN_USE"},
    {"id": "BIKE004", "model": "Road Racer", "type": "REGULAR", "status": "AVAILABLE"},
    {"id": "BIKE005", "model": "Mountain Explorer", "type": "MOUNTAIN", "status": "IN_USE"},
]

class BikeSimulator:
    def __init__(self):
        self.client = mqtt.Client()
        self.client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
        self.client.tls_set()
        
        # Callbacks
        self.client.on_connect = self.on_connect
        self.client.on_publish = self.on_publish
        
        # Track bike positions
        self.positions = {}
        for bike in BIKES:
            self.positions[bike['id']] = {
                'lat': BASE_LAT + random.uniform(-0.05, 0.05),
                'lng': BASE_LNG + random.uniform(-0.05, 0.05),
                'speed': random.uniform(10, 25) if bike['status'] == 'IN_USE' else 0,
                'bearing': random.uniform(0, 360)  # Direction in degrees
            }
    
    def on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            print("✅ Connected to MQTT Broker")
        else:
            print(f"❌ Failed to connect, return code {rc}")
    
    def on_publish(self, client, userdata, mid):
        pass  # Silent publish confirmation
    
    def connect(self):
        """Connect to MQTT broker"""
        try:
            print(f"🔌 Connecting to {MQTT_BROKER}:{MQTT_PORT}...")
            self.client.connect(MQTT_BROKER, MQTT_PORT, 60)
            self.client.loop_start()
            time.sleep(2)  # Wait for connection
        except Exception as e:
            print(f"❌ Connection error: {e}")
            raise
    
    def disconnect(self):
        """Disconnect from MQTT broker"""
        self.client.loop_stop()
        self.client.disconnect()
        print("👋 Disconnected from MQTT Broker")
    
    def move_bike(self, bike_id):
        """
        Simulate bike movement
        Bikes move in somewhat realistic patterns
        """
        pos = self.positions[bike_id]
        
        # Find bike data
        bike_data = next(b for b in BIKES if b['id'] == bike_id)
        
        if bike_data['status'] == 'IN_USE':
            # Moving bikes: update position based on speed and bearing
            # Approximate: 1 degree latitude ≈ 111 km
            # Speed is in km/h, we update every 5 seconds
            distance_km = (pos['speed'] / 3600) * 5  # Distance in 5 seconds
            distance_deg = distance_km / 111
            
            # Convert bearing to radians
            import math
            bearing_rad = math.radians(pos['bearing'])
            
            # Update position
            pos['lat'] += distance_deg * math.cos(bearing_rad)
            pos['lng'] += distance_deg * math.sin(bearing_rad) / math.cos(math.radians(pos['lat']))
            
            # Randomly change direction slightly (simulate turns)
            pos['bearing'] += random.uniform(-15, 15)
            pos['bearing'] = pos['bearing'] % 360
            
            # Randomly change speed slightly
            pos['speed'] += random.uniform(-2, 2)
            pos['speed'] = max(5, min(30, pos['speed']))  # Keep between 5-30 km/h
            
            # Keep within bounds (Bulacan area)
            if abs(pos['lat'] - BASE_LAT) > 0.1:
                pos['bearing'] = (pos['bearing'] + 180) % 360  # Turn around
            if abs(pos['lng'] - BASE_LNG) > 0.1:
                pos['bearing'] = (pos['bearing'] + 180) % 360  # Turn around
        else:
            # Stationary bikes: no movement, speed = 0
            pos['speed'] = 0
    
    def publish_location(self, bike):
        """Publish bike location to MQTT"""
        bike_id = bike['id']
        pos = self.positions[bike_id]
        
        # Prepare GPS data
        gps_data = {
            "latitude": round(pos['lat'], 7),
            "longitude": round(pos['lng'], 7),
            "speed": round(pos['speed'], 2),
            "bike_model": bike['model'],
            "bike_type": bike['type'],
            "status": bike['status'],
            "current_zone_id": "ZONE001" if bike['status'] == 'IN_USE' else "",
            "timestamp": datetime.now().isoformat()
        }
        
        # Publish to MQTT topic
        topic = f"esp32/gps/{bike_id}"
        payload = json.dumps(gps_data)
        
        result = self.client.publish(topic, payload, qos=1)
        
        if result.rc == mqtt.MQTT_ERR_SUCCESS:
            print(f"📍 {bike_id}: [{gps_data['latitude']:.6f}, {gps_data['longitude']:.6f}] "
                  f"@ {gps_data['speed']:.1f} km/h - {bike['status']}")
        else:
            print(f"❌ Failed to publish for {bike_id}")
    
    def run(self, duration_minutes=10, update_interval=5):
        """
        Run simulation
        
        Args:
            duration_minutes: How long to run simulation (minutes)
            update_interval: Seconds between updates
        """
        print(f"\n🚴 Starting bike simulation for {duration_minutes} minutes...")
        print(f"📊 Simulating {len(BIKES)} bikes")
        print(f"⏱️  Update interval: {update_interval} seconds\n")
        
        start_time = time.time()
        end_time = start_time + (duration_minutes * 60)
        iteration = 0
        
        try:
            while time.time() < end_time:
                iteration += 1
                print(f"\n--- Update #{iteration} [{datetime.now().strftime('%H:%M:%S')}] ---")
                
                # Update and publish each bike
                for bike in BIKES:
                    self.move_bike(bike['id'])
                    self.publish_location(bike)
                
                # Wait for next update
                time.sleep(update_interval)
            
            print(f"\n✅ Simulation completed after {duration_minutes} minutes")
            
        except KeyboardInterrupt:
            print("\n\n⚠️  Simulation interrupted by user")
        except Exception as e:
            print(f"\n❌ Error during simulation: {e}")
    
    def simulate_alert(self, bike_id, alert_type="crash"):
        """
        Simulate a bike alert (crash, movement, etc.)
        
        Args:
            bike_id: ID of the bike
            alert_type: Type of alert ('crash', 'movement', 'tamper')
        """
        pos = self.positions.get(bike_id)
        if not pos:
            print(f"❌ Bike {bike_id} not found")
            return
        
        alert_data = {
            "bike_id": bike_id,
            "type": alert_type,
            "latitude": round(pos['lat'], 7),
            "longitude": round(pos['lng'], 7),
            "timestamp": datetime.now().isoformat()
        }
        
        topic = "esp32/alerts"
        payload = json.dumps(alert_data)
        
        result = self.client.publish(topic, payload, qos=1)
        
        if result.rc == mqtt.MQTT_ERR_SUCCESS:
            print(f"🚨 Alert sent: {bike_id} - {alert_type}")
        else:
            print(f"❌ Failed to send alert for {bike_id}")


def main():
    """Main function"""
    import sys
    
    print("=" * 60)
    print("🚴 SIKAD Bike Location Simulator")
    print("=" * 60)
    
    simulator = BikeSimulator()
    
    try:
        # Connect to MQTT broker
        simulator.connect()
        
        # Check command line arguments
        if len(sys.argv) > 1:
            if sys.argv[1] == "alert":
                # Simulate an alert
                bike_id = sys.argv[2] if len(sys.argv) > 2 else "BIKE001"
                alert_type = sys.argv[3] if len(sys.argv) > 3 else "crash"
                simulator.simulate_alert(bike_id, alert_type)
                time.sleep(2)
            elif sys.argv[1] == "once":
                # Send one update for all bikes
                print("\n📍 Sending single location update for all bikes...\n")
                for bike in BIKES:
                    simulator.publish_location(bike)
                time.sleep(2)
            else:
                duration = int(sys.argv[1])
                interval = int(sys.argv[2]) if len(sys.argv) > 2 else 5
                simulator.run(duration_minutes=duration, update_interval=interval)
        else:
            # Default: run for 10 minutes with 5 second updates
            simulator.run(duration_minutes=10, update_interval=5)
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
    finally:
        simulator.disconnect()
        print("\n" + "=" * 60)


if __name__ == "__main__":
    # Check if paho-mqtt is installed
    try:
        import paho.mqtt.client as mqtt
    except ImportError:
        print("❌ paho-mqtt not installed!")
        print("📦 Install it with: pip install paho-mqtt")
        exit(1)
    
    print("\n💡 Usage:")
    print("  python test_bike_simulator.py              # Run for 10 minutes")
    print("  python test_bike_simulator.py 5            # Run for 5 minutes")
    print("  python test_bike_simulator.py 10 3         # Run 10 min, update every 3 sec")
    print("  python test_bike_simulator.py once         # Send one update")
    print("  python test_bike_simulator.py alert BIKE001 crash  # Send crash alert")
    print()
    
    main()