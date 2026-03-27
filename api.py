from flask import Flask, jsonify
from pymongo import MongoClient
from datetime import datetime, timedelta
from flask_cors import CORS # Import CORS

app = Flask(__name__)
CORS(app) # Enable CORS for all routes

# MongoDB Configuration (Use the same URI as in server.py)
MONGO_URI = "mongodb+srv://alaekekaebuka200:Ebscojebscojjj20$@cohort5wilmer.r1c8m.mongodb.net/takeover"
MONGO_DB_NAME = "takeover"
MONGO_COLLECTION_NAME = "active_servers"

# Initialize MongoDB client
client = MongoClient(MONGO_URI)
db = client[MONGO_DB_NAME]
active_servers_collection = db[MONGO_COLLECTION_NAME]

@app.route('/api/servers', methods=['GET'])
def get_active_servers():
    # Define a threshold for "active" servers (e.g., last seen within the last 5 minutes)
    # This helps filter out servers that might have gone offline without explicitly disconnecting
    active_threshold = datetime.utcnow() - timedelta(minutes=5)
    
    # Query MongoDB for servers that have been seen recently
    servers = active_servers_collection.find(
        {'last_seen': {'$gte': active_threshold}},
        {'_id': 0, 'ip': 1, 'ws_port': 1, 'http_port': 1} # Exclude _id, include other fields
    )
    
    server_list = list(servers)
    return jsonify(server_list)

if __name__ == '__main__':
    # In a production environment, you would use a production-ready WSGI server
    # like Gunicorn or uWSGI. For local testing, Flask's built-in server is fine.
    app.run(host='0.0.0.0', port=5000, debug=True)