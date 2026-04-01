import asyncio
import websockets
from mss import mss
from PIL import Image
import io
import json
from pynput.mouse import Controller as MouseController, Button
from pynput.keyboard import Controller as KeyboardController, Key
import socket
from http.server import BaseHTTPRequestHandler, HTTPServer
import threading
from pymongo import MongoClient # Import MongoClient
from datetime import datetime # Import datetime for timestamp

# Initialize pynput controllers
mouse = MouseController()
keyboard = KeyboardController()

# Function to get the local IP address
def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # Doesn't actually connect, just used to find the local IP
        s.connect(('10.254.254.254', 1)) 
        IP = s.getsockname()[0]
    except Exception:
        IP = '127.0.0.1' # Fallback to localhost if no network connection
    finally:
        s.close()
    return IP

# Global variable to store the local IP, once determined
SERVER_IP = get_local_ip()
HTTP_DISCOVERY_PORT = 8001 # A different port for HTTP discovery

# MongoDB Configuration (UPDATED WITH YOUR PROVIDED URI)
MONGO_URI = "mongodb+srv://alaekekaebuka200:Ebscojebscojjj20$@cohort5wilmer.r1c8m.mongodb.net/takeover"
MONGO_DB_NAME = "takeover" # Using the database name from your URI
MONGO_COLLECTION_NAME = "active_servers" # You can change this if you prefer a different collection name

class DiscoveryHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/discover':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*') # Allow CORS for web client
            self.end_headers()
            response_data = {'ip': SERVER_IP, 'ws_port': 8080, 'http_port': HTTP_DISCOVERY_PORT}
            self.wfile.write(json.dumps(response_data).encode('utf-8'))
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b'Not Found')

# This function will run the HTTP server in a separate thread
def start_http_server_sync():
    server_address = (SERVER_IP, HTTP_DISCOVERY_PORT)
    httpd = HTTPServer(server_address, DiscoveryHandler)
    print(f"HTTP Discovery server started on http://{SERVER_IP}:{HTTP_DISCOVERY_PORT}/discover")
    httpd.serve_forever()

async def send_screen_data(websocket):
    sct = mss()
    try:
        while True:
            # Capture the screen
            sct_img = sct.grab(sct.monitors[0]) # Capture the primary monitor

            # Convert to PIL Image
            img = Image.frombytes("RGB", sct_img.size, sct_img.rgb)

            # Convert to JPEG bytes
            byte_arr = io.BytesIO()
            img.save(byte_arr, format='JPEG', quality=80) # Adjust quality as needed
            jpeg_data = byte_arr.getvalue()
            
            # Send the image bytes over WebSocket
            await websocket.send(jpeg_data)
            
            # You can adjust this delay to control the frame rate
            await asyncio.sleep(0.05) # ~20 frames per second
            
    except websockets.exceptions.ConnectionClosedOK:
        print("Client disconnected gracefully during screen send.")
    except Exception as e:
        print(f"An error occurred during screen send: {e}")

async def receive_input_data(websocket):
    try:
        async for message in websocket:
            try:
                data = json.loads(message)
                print(f"Received input: {data}") # Keep for debugging if needed

                if data['type'] == 'mousemove':
                    mouse.position = (data['x'], data['y'])
                elif data['type'] == 'mousedown':
                    button = Button.left if data['button'] == 0 else Button.right # 0 for left, 2 for right
                    mouse.press(button)
                    print(f"Simulating mouse press: {button}") # Add this
                elif data['type'] == 'mouseup':
                    button = Button.left if data['button'] == 0 else Button.right
                    mouse.release(button)
                    print(f"Simulating mouse release: {button}") # Add this
                elif data['type'] == 'click':
                    button = Button.left if data['button'] == 0 else Button.right
                    mouse.click(button)
                elif data['type'] == 'keydown':
                    try:
                        # Handle special keys (e.g., 'space', 'enter', 'shift')
                        key_to_press = getattr(Key, data['key'].lower(), data['key'])
                        keyboard.press(key_to_press)
                        print(f"Simulating keydown: {key_to_press}") # Add this
                    except AttributeError:
                        # If it's not a special key, it's likely a character
                        keyboard.press(data['key'])
                        print(f"Simulating keydown (char): {data['key']}") # Add this
                elif data['type'] == 'keyup':
                    try:
                        key_to_release = getattr(Key, data['key'].lower(), data['key'])
                        keyboard.release(key_to_release)
                        print(f"Simulating keyup: {key_to_release}") # Add this
                    except AttributeError:
                        keyboard.release(data['key'])
                        print(f"Simulating keyup (char): {data['key']}") # Add this
            except json.JSONDecodeError:
                print(f"Received non-JSON message: {message}")
            except Exception as e:
                print(f"Error processing input message: {e}")
                # Add this specific check for pynput related errors
                if "pynput" in str(e).lower() or "permission" in str(e).lower():
                    print("HINT: Input simulation might be failing due to permissions or pynput issues.")
                    print("Try running server.py as Administrator.")
    except websockets.exceptions.ConnectionClosedOK:
        print("Client disconnected gracefully during input receive.")
    except Exception as e:
        print(f"An error occurred during input receive: {e}")

async def websocket_handler(websocket, path=None):
    print("Client connected")
    try:
        # Run both sending screen data and receiving input data concurrently
        await asyncio.gather(
            send_screen_data(websocket),
            receive_input_data(websocket)
        )
    except Exception as e:
        print(f"WebSocket handler error: {e}")
    finally:
        print("Client disconnected.")

# Function to update IP in MongoDB
def update_ip_in_mongodb(ip_address, ws_port, http_port):
    try:
        client = MongoClient(MONGO_URI)
        db = client[MONGO_DB_NAME]
        collection = db[MONGO_COLLECTION_NAME]

        # Use the IP address as a unique identifier for the document
        # This will insert a new document if the IP doesn't exist, or update it if it does
        collection.update_one(
            {'ip': ip_address},
            {'$set': {'ip': ip_address, 'ws_port': ws_port, 'http_port': http_port, 'last_seen': datetime.utcnow()}},
            upsert=True
        )
        print(f"IP address {ip_address} updated in MongoDB.")
        client.close()
    except Exception as e:
        print(f"Error updating IP in MongoDB: {e}")

async def main():
    global SERVER_IP
    SERVER_IP = get_local_ip()

    # Update IP in MongoDB (blocking call, but happens once on startup)
    update_ip_in_mongodb(SERVER_IP, 8080, HTTP_DISCOVERY_PORT)

    # Start HTTP server in a separate thread so it doesn't block the asyncio event loop
    http_thread = threading.Thread(target=start_http_server_sync, daemon=True)
    http_thread.start()

    # Start WebSocket server
    async with websockets.serve(websocket_handler, SERVER_IP, 8080):
        print(f"WebSocket server started on ws://{SERVER_IP}:8080")
        print(f"Clients should connect to: ws://{SERVER_IP}:8080")
        await asyncio.Future()  # Run forever

if __name__ == "__main__":
    asyncio.run(main())