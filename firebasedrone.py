import time
from dronekit import connect, VehicleMode, LocationGlobalRelative
import firebase_admin
from firebase_admin import credentials, db

# Firebase setup
cred = credentials.Certificate('/home/tihan/Downloads/leader.json')
firebase_admin.initialize_app(cred, {'databaseURL': 'https://drone-2037a-default-rtdb.firebaseio.com'})

# References for Firebase Realtime Database
ground_coords_ref = db.reference('ground_coordinates')
drone_coords_ref = db.reference('drone_coordinates')

# Connect to the drone
connection_string = '/dev/ttyACM0'
baud_rate = 57600
vehicle = connect(connection_string, baud=baud_rate, wait_ready=True)

# Function to set the drone to follow a target GPS coordinate with 10-meter altitude
def follow_ground_station(lat, lon):
    vehicle.mode = VehicleMode("GUIDED")
    while not vehicle.mode.name == "GUIDED":
        time.sleep(1)

    if not vehicle.armed:
        vehicle.armed = True
        print("Arming the drone and taking off...")
        vehicle.simple_takeoff(10)

        while vehicle.location.global_relative_frame.alt < 10 * 0.95:
            time.sleep(1)

    # Move the drone to the target GPS coordinate at 10 meters altitude
    point = LocationGlobalRelative(lat, lon, 10)
    vehicle.simple_goto(point)

# Initialize metrics for data tracking
total_data_received = 0
packet_loss_count = 0
expected_packets = 0  # Total packets expected to receive based on time
start_time = time.time()
interval = 1  # Expected interval in seconds

# Create a new log file with headers if it doesn't already exist
with open("firebasedrone_log5.txt", "w") as log:
    log.write(f"{'Receive Time':<20}{'Latitude':<15}{'Longitude':<15}{'Data Rate (B/s)':<15}{'Latency (ms)':<15}{'Packet Size (B)':<15}{'Packet Loss (%)':<15}\n")
    log.write("=" * 115 + "\n")

try:
    while True:
        # Increment expected packets count
        expected_packets += 1
        
        # Read the ground station GPS data from Firebase
        ground_data = ground_coords_ref.get()
        if ground_data:
            latitude = ground_data.get("latitude")
            longitude = ground_data.get("longitude")
            send_time = ground_data.get("timestamp")
            receive_time = time.time()

            # Calculate latency in milliseconds
            latency = (receive_time - send_time) * 1000  # Convert to ms

            # Calculate packet size
            packet_size = len(f"{latitude},{longitude},{send_time}".encode())
            total_data_received += packet_size

            # Calculate data rate (bytes per second)
            elapsed_time = receive_time - start_time
            data_rate = total_data_received / elapsed_time if elapsed_time > 0 else 0

            # Calculate packet loss percentage
            packet_loss_percentage = (packet_loss_count / expected_packets) * 100 if expected_packets > 0 else 0

            # Log received data to file
            with open("firebasedrone_log5.txt", "a") as log:
                log.write(f"{receive_time:<20.3f}{latitude:<15.8f}{longitude:<15.8f}{data_rate:<15.2f}{latency:<15.2f}{packet_size:<15}{packet_loss_percentage:<15.2f}\n")

            # Display received data for tracking
            print("\n--- Data Received ---")
            print(f"Latitude:           {latitude}")
            print(f"Longitude:          {longitude}")
            print(f"Data Rate:          {data_rate:.2f} B/s")
            print(f"Latency:            {latency:.2f} ms")
            print(f"Packet Size:        {packet_size} bytes")
            print(f"Total Data:         {total_data_received} bytes")
            print(f"Elapsed Time:       {elapsed_time:.2f} seconds")
            print(f"Packet Loss:        {packet_loss_percentage:.2f}%")
            print("-----------------------\n")

            # Command the drone to follow the ground station's location
            follow_ground_station(latitude, longitude)

            # Send current drone location to Firebase
            current_lat = vehicle.location.global_frame.lat
            current_lon = vehicle.location.global_frame.lon
            drone_coords_ref.set({
                "timestamp": receive_time,
                "latitude": current_lat,
                "longitude": current_lon,
                "altitude": vehicle.location.global_relative_frame.alt,
                "data_rate": data_rate,
                "latency": latency,
                "packet_size": packet_size,
                "packet_loss_percentage": packet_loss_percentage
            })

        # Check for packet loss (e.g., no data received in this cycle)
        else:
            packet_loss_count += 1

        # Wait before the next update
        time.sleep(interval)

except KeyboardInterrupt:
    print("Exiting...")

finally:
    # Close connection to drone
    vehicle.close()
