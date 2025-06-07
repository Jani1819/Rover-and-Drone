import time
from dronekit import connect, VehicleMode
import firebase_admin
from firebase_admin import credentials, db

# Firebase setup
cred = credentials.Certificate('/home/tihan/Downloads/leader.json')
firebase_admin.initialize_app(cred, {'databaseURL': 'https://drone-2037a-default-rtdb.firebaseio.com'})
ground_coords_ref = db.reference('ground_coordinates')

# Connect to the Pixhawk
pixhawk = connect('/dev/ttyACM0', baud=57600, wait_ready=True)
pixhawk.mode = VehicleMode("GUIDED")  # Set initial mode to GUIDED

# Initialize metrics for data tracking
total_data_sent = 0
packet_loss_count = 0
total_packets_sent = 0  # Initialize for calculation but not logging
start_time = time.time()
interval = 1  # Sending interval in seconds

# Create a new log file with headers if it doesn't already exist
with open("firebaseground_vehicle_log2.txt", "w") as log:
    log.write(f"{'Timestamp':<20}{'Latitude':<15}{'Longitude':<15}{'Data Rate (B/s)':<15}{'Latency (ms)':<15}{'Packet Size (B)':<15}{'Packet Loss (%)':<15}\n")
    log.write("=" * 100 + "\n")

try:
    while True:
        # Check GPS status for valid satellite fix
        if pixhawk.gps_0.satellites_visible > 0 and pixhawk.gps_0.fix_type >= 2:
            # Retrieve current GPS coordinates
            latitude = pixhawk.location.global_frame.lat
            longitude = pixhawk.location.global_frame.lon
            send_start_time = time.time()  # Start time for latency measurement

            # Update metrics for sent packets
            total_packets_sent += 1
            packet_size = len(f"{latitude},{longitude},{send_start_time}".encode())
            total_data_sent += packet_size

            # Calculate data rate (bytes per second)
            elapsed_time = time.time() - start_time
            data_rate = total_data_sent / elapsed_time if elapsed_time > 0 else 0

            # Calculate latency
            latency = (time.time() - send_start_time) * 1000  # Convert to milliseconds

            # Send data to Firebase Realtime Database
            ground_coords_ref.set({
                "timestamp": send_start_time,
                "latitude": latitude,
                "longitude": longitude,
                "data_rate": data_rate,
                "latency": latency,
                "packet_size": packet_size,
                "packet_loss_count": packet_loss_count
            })

            # Calculate packet loss percentage
            packet_loss_percentage = (packet_loss_count / total_packets_sent * 100) if total_packets_sent > 0 else 0

            # Log data to file for tracking
            with open("firebaseground_vehicle_log2.txt", "a") as log:
                log.write(f"{send_start_time:<20.3f}{latitude:<15.8f}{longitude:<15.8f}{data_rate:<15.2f}{latency:<15.2f}{packet_size:<15}{packet_loss_percentage:<15.2f}\n")

            # Print summary of sent data for clarity
            print("\n--- Data Sent to Firebase ---")
            print(f"Latitude:           {latitude}")
            print(f"Longitude:          {longitude}")
            print(f"Data Rate:          {data_rate:.2f} B/s")
            print(f"Latency:            {latency:.2f} ms")
            print(f"Packet Size:        {packet_size} bytes")
            print(f"Packet Loss Count:  {packet_loss_count}")
            print(f"Packet Loss (%):    {packet_loss_percentage:.2f}%")
            print(f"Total Data Sent:    {total_data_sent} bytes")
            print(f"Elapsed Time:       {elapsed_time:.2f} seconds")
            print("-----------------------------\n")

        else:
            # Increment packet loss if GPS fix is not available
            packet_loss_count += 1

        # Wait before sending the next update
        time.sleep(interval)

except KeyboardInterrupt:
    print("Exiting...")

finally:
    # Close connection to Pixhawk
    pixhawk.close()
