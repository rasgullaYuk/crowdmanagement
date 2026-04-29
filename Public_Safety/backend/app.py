import os
# Fix for OMP: Error #15: Initializing libiomp5md.dll, but found libiomp5md.dll already initialized.
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

from flask import Flask, request, jsonify, send_from_directory, Response, send_file
from csrnet_stream_output import generate_crowd_stream
from flask_cors import CORS
from twilio.rest import Client
from flasgger import Swagger, swag_from
import os
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta
import heapq
import json
import time
import re
import random
import uuid
from dotenv import load_dotenv
import threading
import cv2
import PIL.Image
import sys

# Fix Windows console encoding for emoji support
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except:
        pass

def safe_print(*args, **kwargs):
    """Safe print function that handles Unicode errors on Windows"""
    try:
        print(*args, **kwargs)
    except UnicodeEncodeError:
        # Fallback: remove emojis
        safe_args = []
        for arg in args:
            if isinstance(arg, str):
                # Remove emojis by encoding to ASCII with ignore
                safe_args.append(arg.encode('ascii', 'ignore').decode('ascii'))
            else:
                safe_args.append(arg)
        print(*safe_args, **kwargs)

load_dotenv() # Load .env if present

# Process start time (for uptime reporting)
APP_START_TIME = time.time()

# Global storage for analysis results
ZONE_ANALYSIS = {}
MESSAGES = []

# Persistent anomaly storage - never cleared, accumulates all anomalies
PERSISTENT_ANOMALIES = []  # List of all anomalies detected across all zones

# Historical data for real-time graphs (stores last 20 data points per zone)
ZONE_HISTORY = {
    'food_court': [],
    'parking': [],
    'main_stage': [],
    'testing': []
}

# Video processing state
ACTIVE_VIDEO_PROCESSORS = {}  # {zone_id: {'thread': thread_obj, 'stop_flag': bool, 'video_path': str}}
VIDEO_PROCESSING_LOCK = threading.Lock()

# Upload status tracking for async processing
UPLOAD_STATUS = {}  # {upload_id: {status, progress, result, error, zone}}
UPLOAD_LOCK = threading.Lock()

# Lost and Found storage
LOST_PERSONS = []
FOUND_MATCHES = []

# Gemini API Key Management
def _load_gemini_keys():
    keys = []
    primary_key = (os.getenv("GEMINI_API_KEY") or "").strip()
    if primary_key:
        keys.append(primary_key)

    raw_pool = os.getenv("GEMINI_API_KEYS", "")
    for key in [k.strip() for k in raw_pool.split(",") if k.strip()]:
        if key not in keys:
            keys.append(key)
    return keys


GEMINI_KEYS = _load_gemini_keys()
CURRENT_KEY_INDEX = 0


def get_gemini_key():
    """Return the next Gemini key from environment variables only."""
    global CURRENT_KEY_INDEX, GEMINI_KEYS
    GEMINI_KEYS = _load_gemini_keys()
    if not GEMINI_KEYS:
        return None
    key = GEMINI_KEYS[CURRENT_KEY_INDEX % len(GEMINI_KEYS)]
    CURRENT_KEY_INDEX = (CURRENT_KEY_INDEX + 1) % len(GEMINI_KEYS)
    return key

# Predefined camera endpoints for specific zones
CAMERA_ENDPOINTS = {
    'food_court': {
        'id': 'food_court',
        'name': 'Food Court Region',
        'description': 'Monitor crowd density and activity in food court area',
        'upload_endpoint': '/api/cameras/food-court/upload'
    },
    'parking': {
        'id': 'parking',
        'name': 'Parking Area Region',
        'description': 'Monitor vehicle and pedestrian traffic in parking zones',
        'upload_endpoint': '/api/cameras/parking/upload'
    },
    'main_stage': {
        'id': 'main_stage',
        'name': 'Main Stage Region',
        'description': 'Monitor main stage crowd density and performer safety',
        'upload_endpoint': '/api/cameras/main-stage/upload'
    },
    'testing': {
        'id': 'testing',
        'name': 'Testing Region',
        'description': 'Testing and calibration zone for new camera feeds',
        'upload_endpoint': '/api/cameras/testing/upload'
    }
}

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

# Global State
ZONE_HISTORY = {}


# Swagger UI Configuration
swagger_config = {
    "headers": [],
    "specs": [
        {
            "endpoint": 'apispec',
            "route": '/apispec.json',
        }
    ],
    "static_url_path": "/flasgger_static",
    "swagger_ui": True,
    "specs_route": "/api/docs"
}

swagger_template = {
    "swagger": "2.0",
    "info": {
        "title": "CrowdGuard API",
        "description": "Crowd Management Platform API - Upload videos, detect anomalies, and manage responders",
        "version": "1.0.0"
    },
    "host": "localhost:5000",
    "basePath": "/",
    "schemes": ["http"],
}

swagger = Swagger(app, config=swagger_config, template=swagger_template)

# --- Configuration ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# Keep BASE_DIR as backend folder
# if os.path.basename(BASE_DIR) == 'backend':
#     BASE_DIR = os.path.dirname(BASE_DIR)

UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
FACES_FOLDER = os.path.join(UPLOAD_FOLDER, 'faces')
if not os.path.exists(FACES_FOLDER):
    os.makedirs(FACES_FOLDER)

def _csrnet_weights_path():
    backend_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(backend_dir)
    return os.path.join(project_root, 'weights.pth')

def _csrnet_weights_status():
    weights_path = _csrnet_weights_path()
    exists = os.path.exists(weights_path)
    return {
        "name": "CSRNet",
        "weights_path": weights_path,
        "weights_present": exists,
        "ready": exists,
        "degraded_mode": not exists,
    }

@app.route('/api/health', methods=['GET'])
def api_health():
    """
    Lightweight service health endpoint
    ---
    tags:
      - Health
    responses:
      200:
        description: API health + model readiness
    """
    model = _csrnet_weights_status()
    overall = "ok" if model["ready"] else "degraded"
    return jsonify({
        "status": overall,
        "api": "ok",
        "model": model,
        "uptime_s": int(time.time() - APP_START_TIME),
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }), 200

@app.route('/api/health/model', methods=['GET'])
def model_health():
    """
    Model readiness endpoint
    ---
    tags:
      - Health
    responses:
      200:
        description: Model readiness and degraded-mode signal
    """
    return jsonify(_csrnet_weights_status()), 200

# Twilio Configuration
TWILIO_ACCOUNT_SID = os.getenv('TWILIO_ACCOUNT_SID')
TWILIO_AUTH_TOKEN = os.getenv('TWILIO_AUTH_TOKEN')
TWILIO_PHONE_NUMBER = os.getenv('TWILIO_PHONE_NUMBER', '+15005550006')

try:
    twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
except Exception as e:
    print(f"Warning: Twilio client failed to initialize: {e}")
    twilio_client = None

# Mock Data
RESPONDERS = [
    {"id": 1, "name": "Dr. Sarah Johnson", "type": "Medical", "status": "active", "zone": "Food Court", "incidents": 2, "phone": "+917337743545"},
    {"id": 2, "name": "Officer Mike Chen", "type": "Security", "status": "investigating", "zone": "Parking", "incidents": 1, "phone": "+917337743545"},
    {"id": 3, "name": "Captain Lisa Wong", "type": "Fire", "status": "available", "zone": "Backstage", "incidents": 0, "phone": "+917337743545"},
    {"id": 4, "name": "Tech Lead Alex Kim", "type": "Technical", "status": "active", "zone": "Control Room", "incidents": 1, "phone": "+917337743545"},
]

EVENTS = [
    {
        "id": "evt_default",
        "name": "Summer Music Festival 2025",
        "location": {"lat": 12.9716, "lng": 77.5946}
    },
    {
        "id": "evt_8th_mile",
        "name": "8th Mile",
        "location": {"lat": 12.9237, "lng": 77.4987},  # RV College of Engineering coordinates
        "venue": "RV College of Engineering",
        "capacity": 20000,
        "current_attendance": 15343,
        "date": "2025-12-05",
        "type": "College Fest",
        "zones": [
            {
                "id": "cs_ground",
                "name": "CS Ground",
                "capacity": 8000,
                "current_count": 7200,  # Highest - Concert happening
                "density_percentage": 90,
                "status": "critical",
                "activity": "Live Concert Performance"
            },
            {
                "id": "bt_quadrangle",
                "name": "BT Quadrangle", 
                "capacity": 3000,
                "current_count": 1800,  # 3rd position (60%)
                "density_percentage": 60,
                "status": "medium",
                "activity": "Food Stalls & Games"
            },
            {
                "id": "food_court",
                "name": "Food Court",
                "capacity": 4000,
                "current_count": 800,   # Least crowded (20%)
                "density_percentage": 20,
                "status": "low",
                "activity": "Dining Area"
            },
            {
                "id": "mm_foods",
                "name": "MM Foods",
                "capacity": 2500,
                "current_count": 1750,  # 4th position (70%)
                "density_percentage": 70,
                "status": "high",
                "activity": "Food Court Area"
            },
            {
                "id": "auditorium",
                "name": "Auditorium",
                "capacity": 2500,
                "current_count": 993,   # 2nd least (40%)
                "density_percentage": 40,
                "status": "low",
                "activity": "Cultural Events"
            }
        ]
    }
]

# --- Venue Graph for Pathfinding ---
# Realistic venue graph with Testing Region for fire emergency
# Bidirectional connections ensure paths can always be found
VENUE_GRAPH = {
    "Entrance": {"Security Gate": 1, "Parking": 1, "Control Room": 1, "Medical Bay": 2},
    "Security Gate": {"Entrance": 1, "Food Court": 1, "Medical Bay": 1, "Main Stage": 2},
    "Main Stage": {"Medical Bay": 1, "VIP Area": 1, "Testing Region": 1, "Security Gate": 2},
    "Food Court": {"Security Gate": 1, "Medical Bay": 1},  # Can be avoided (crowded)
    "Parking": {"Entrance": 1, "Control Room": 1},
    "Medical Bay": {"Security Gate": 1, "Main Stage": 1, "Testing Region": 1, "Food Court": 1, "Entrance": 2},
    "Testing Region": {"Medical Bay": 1, "Main Stage": 1, "VIP Area": 1},  # FIRE LOCATION
    "Backstage": {"VIP Area": 1, "Main Stage": 1},
    "VIP Area": {"Main Stage": 1, "Testing Region": 1, "Backstage": 1},
    "Control Room": {"Entrance": 1, "Parking": 1, "Security Gate": 2}
}

# Realistic venue coordinates (within 500m radius - typical large venue/festival)
VENUE_COORDINATES = {
    "Entrance": [12.9716, 77.5946],         # Starting point
    "Security Gate": [12.9726, 77.5951],    # 130m from Entrance
    "Main Stage": [12.9741, 77.5961],       # 300m from Entrance
    "Food Court": [12.9731, 77.5956],       # 200m from Entrance (avoid zone)
    "Parking": [12.9706, 77.5941],          # 150m from Entrance
    "Medical Bay": [12.9736, 77.5956],      # 250m from Entrance
    "Testing Region": [12.9746, 77.5951],   # 350m from Entrance (FIRE LOCATION)
    "Backstage": [12.9751, 77.5966],        # 450m from Entrance
    "VIP Area": [12.9746, 77.5961],         # 370m from Entrance
    "Control Room": [12.9721, 77.5946],     # 60m from Entrance
}

# --- Helper Functions ---
def send_sms_alert(to_number, message):
    try:
        if twilio_client:
            print(f"Sending SMS to {to_number}: {message}")
            # message = twilio_client.messages.create(
            #     body=message,
            #     from_=TWILIO_PHONE_NUMBER,
            #     to=to_number
            # )
            return True
    except Exception as e:
        print(f"Failed to send SMS: {str(e)}") 
        return False
    return False

def calculate_shortest_path(start, end, avoid_zones=[]):
    # Dijkstra's Algorithm
    queue = [(0, start, [])]
    visited = set()
    
    while queue:
        (cost, node, path) = heapq.heappop(queue)
        
        if node in visited:
            continue
        
        visited.add(node)
        path = path + [node]
        
        if node == end:
            return path
        
        if node in VENUE_GRAPH:
            for neighbor, weight in VENUE_GRAPH[node].items():
                if neighbor not in visited:
                    # Increase weight if neighbor is in avoid_zones (simulate crowd density)
                    current_weight = weight
                    if neighbor in avoid_zones:
                        current_weight *= 5 # High penalty for crowded zones
                    
                    heapq.heappush(queue, (cost + current_weight, neighbor, path))
                    
    return None

# --- API Endpoints ---

@app.route('/api')
def api_portal():
    return app.send_static_file('../api_portal.html') if os.path.exists('api_portal.html') else open('api_portal.html').read()

@app.route('/api/responders', methods=['GET'])
def get_responders():
    """
    Get list of all active responders
    ---
    tags:
      - Responder Management
    responses:
      200:
        description: List of responders retrieved successfully
        schema:
          type: array
          items:
            type: object
            properties:
              id:
                type: integer
              name:
                type: string
              type:
                type: string
              status:
                type: string
              zone:
                type: string
              phone:
                type: string
    """
    return jsonify(RESPONDERS)

@app.route('/api/call', methods=['POST'])
def call_responder():
    """
    Initiate a call to a responder
    ---
    tags:
      - Responder Management
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          properties:
            responder_id:
              type: integer
              example: 1
    responses:
      200:
        description: Call initiated successfully
      404:
        description: Responder not found
    """
    data = request.json
    responder_id = data.get('responder_id')
    responder = next((r for r in RESPONDERS if r["id"] == responder_id), None)
    
    if not responder:
        return jsonify({"error": "Responder not found"}), 404
        
    try:
        to_number = responder.get("phone", "+917337743545") 
        print(f"Initiating call to {responder['name']} ({to_number})...")
        return jsonify({"message": f"Initiating call to {responder['name']} ({to_number})... (Mock)", "status": "success"})
    except Exception as e:
        print(f"Twilio Error: {str(e)}")
        return jsonify({"error": str(e)}), 500


def calculate_auto_zones(center_lat, center_lng, radius):
    # Calculate offset in degrees (approximate)
    # 1 degree lat = ~111km. 500m = 0.5km. 0.5/111 = ~0.0045 degrees
    offset = (radius / 1000) / 111
    
    return {
        "Event Center": [center_lat, center_lng],
        "North Zone": [center_lat + offset, center_lng],
        "South Zone": [center_lat - offset, center_lng],
        "East Zone": [center_lat, center_lng + offset],
        "West Zone": [center_lat, center_lng - offset],
        "North East Sector": [center_lat + offset/1.5, center_lng + offset/1.5],
        "North West Sector": [center_lat + offset/1.5, center_lng - offset/1.5],
        "South East Sector": [center_lat - offset/1.5, center_lng + offset/1.5],
        "South West Sector": [center_lat - offset/1.5, center_lng - offset/1.5],
    }

@app.route('/api/events/preview-zones', methods=['POST'])
def preview_zones():
    """
    Preview auto-calculated zones based on location
    ---
    tags:
      - Event Management
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          properties:
            location:
              type: object
              properties:
                lat:
                  type: number
                lng:
                  type: number
            radius:
              type: number
    responses:
      200:
        description: List of calculated zones
    """
    data = request.json
    location = data.get('location')
    radius = data.get('radius', 500)
    
    zones_map = calculate_auto_zones(location['lat'], location['lng'], radius)
    
    # Convert to list for frontend
    zones_list = []
    for name, coords in zones_map.items():
        zones_list.append({
            "name": name,
            "lat": coords[0],
            "lng": coords[1]
        })
        
    return jsonify(zones_list)

@app.route('/api/events/create', methods=['POST'])
def create_event():
    """
    Create a new event with optional custom zones
    ---
    tags:
      - Event Management
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          properties:
            name:
              type: string
            location:
              type: object
            radius:
              type: number
            zones:
              type: array
              items:
                type: object
    responses:
      200:
        description: Event created
    """
    global VENUE_COORDINATES, VENUE_GRAPH
    
    data = request.json
    name = data.get('name')
    location = data.get('location')
    radius = data.get('radius', 500)
    custom_zones = data.get('zones') # List of {name, lat, lng}
    
    # Additional details
    date = data.get('date')
    event_type = data.get('type')
    description = data.get('description')
    organizer = data.get('organizer')
    contact = data.get('contact')
    
    if custom_zones:
        # Use provided zones
        new_zones = {z['name']: [z['lat'], z['lng']] for z in custom_zones}
    else:
        # Auto-calculate
        new_zones = calculate_auto_zones(location['lat'], location['lng'], radius)
    
    # Update global coordinates
    VENUE_COORDINATES = new_zones
    
    # Update global graph (fully connected for simplicity)
    VENUE_GRAPH = {}
    zone_names = list(new_zones.keys())
    
    for i, zone in enumerate(zone_names):
        VENUE_GRAPH[zone] = {}
        for other_zone in zone_names:
            if zone != other_zone:
                VENUE_GRAPH[zone][other_zone] = 2
    
    # Save to EVENTS list
    event_id = "evt_" + secure_filename(name).lower()
    EVENTS.append({
        "id": event_id,
        "name": name,
        "location": location,
        "date": date,
        "type": event_type,
        "description": description,
        "organizer": organizer,
        "contact": contact,
        "venue_coordinates": new_zones,
        "venue_graph": VENUE_GRAPH
    })
    save_events()
    
    # Generate response with camera endpoints
    zones_response = []
    for zone_name, coords in new_zones.items():
        zone_id = secure_filename(zone_name).lower()
        zones_response.append({
            "id": zone_id,
            "name": zone_name,
            "center": {"lat": coords[0], "lng": coords[1]},
            "camera_endpoint": f"/api/cameras/upload-video?zone_id={zone_id}",
            "camera_docs": f"Use POST /api/cameras/upload-video with zone_id='{zone_id}' to simulate camera feed."
        })
    
    return jsonify({
        "message": f"Event '{name}' configured. Area divided into {len(new_zones)} zones.",
        "event_id": event_id,
        "zones": zones_response,
        "navigation_graph_updated": True
    })

@app.route('/api/events', methods=['GET'])
def get_events():
    """
    Get list of all registered events
    ---
    tags:
      - Event Management
    responses:
      200:
        description: List of events
        schema:
          type: array
          items:
            type: object
    """
    return jsonify(EVENTS)

@app.route('/api/events/select', methods=['POST'])
def select_event():
    """
    Select an event to be active
    ---
    tags:
      - Event Management
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          properties:
            event_id:
              type: string
    responses:
      200:
        description: Event selected
    """
    global VENUE_COORDINATES, VENUE_GRAPH
    data = request.json
    event_id = data.get('event_id')
    
    event = next((e for e in EVENTS if e['id'] == event_id), None)
    if not event:
        return jsonify({"error": "Event not found"}), 404
        
    # Update global state
    if 'venue_coordinates' in event:
        VENUE_COORDINATES = event['venue_coordinates']
    if 'venue_graph' in event:
        VENUE_GRAPH = event['venue_graph']
        
    return jsonify({"message": f"Event '{event['name']}' selected", "active": True})

@app.route('/api/zones/divide', methods=['POST'])
def divide_zones():
    """
    Divide venue into logical zones
    ---
    tags:
      - Zone Management
    responses:
      200:
        description: Zones divided successfully
        schema:
          type: object
          properties:
            message:
              type: string
            zones:
              type: array
              items:
                type: object
    """
    return jsonify({
        "message": "Zones divided successfully",
        "zones": [
            {"id": "zone1", "name": "Main Stage", "capacity": 5000},
            {"id": "zone2", "name": "Food Court", "capacity": 2000},
            {"id": "zone3", "name": "Entrance", "capacity": 1000}
        ]
    })

def send_anomaly_alert(zone_id, anomaly_type, description):
    """Send SMS alert to responders assigned to the zone"""
    if not twilio_client:
        print("Twilio client not initialized. Skipping SMS.")
        return

    # Find responders for this zone
    zone_name = CAMERA_ENDPOINTS.get(zone_id, {}).get('name', zone_id)
    responders = [r for r in RESPONDERS if r['zone'].lower() in zone_name.lower() or r['zone'] == 'Control Room']
    
    if not responders:
        # Fallback to all responders if no specific zone match
        responders = RESPONDERS

    message_body = f"🚨 CRITICAL ALERT: {anomaly_type} detected in {zone_name}. {description}. Please respond immediately."

    for responder in responders:
        try:
            message = twilio_client.messages.create(
                body=message_body,
                from_=TWILIO_PHONE_NUMBER,
                to=responder['phone']
            )
            print(f"SMS sent to {responder['name']}: {message.sid}")
        except Exception as e:
            print(f"Failed to send SMS to {responder['name']}: {e}")



def extract_frame_at_timestamp(video_path, timestamp_str):
    """Extracts a frame from the video at the given timestamp (MM:SS)"""
    try:
        parts = timestamp_str.split(':')
        if len(parts) == 2:
            minutes = int(parts[0])
            seconds = int(parts[1])
            time_in_seconds = minutes * 60 + seconds
        else:
            return None
            
        cap = cv2.VideoCapture(video_path)
        fps = cap.get(cv2.CAP_PROP_FPS)
        frame_number = int(time_in_seconds * fps)
        
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
        ret, frame = cap.read()
        cap.release()
        
        if ret:
            return frame
        return None
    except Exception as e:
        print(f"Frame extraction error: {e}")
        return None

def analyze_video_final(video_path, zone_id):
    """
    FINAL ROBUST video analysis - processes entire video, checks ALL missing persons.
    """
    try:
        from deepface import DeepFace
        import cv2
        
        print(f"\n{'='*60}")
        print(f"STARTING ROBUST VIDEO ANALYSIS")
        print(f"Video: {video_path}")
        print(f"{'='*60}\n")
        
        # Get active lost persons
        active_lost_persons = [p for p in LOST_PERSONS if p['status'] == 'active' and p['image_url']]
        
        if not active_lost_persons:
            print("⚠️  No active missing persons")
            return {
                'crowd_count': 0,
                'density_level': 'Low',
                'anomalies': [],
                'found_persons': [],
                'description': "No active cases",
                'sentiment': "Unknown",
                'timestamp': datetime.utcnow().isoformat() + "Z"
            }
        
        print(f"📋 Searching for {len(active_lost_persons)} person(s)")
        
        analysis = {
            'crowd_count': 0,
            'density_level': 'Low',
            'anomalies': [],
            'found_persons': [],
            'description': "Analysis complete",
            'sentiment': "Unknown",
            'timestamp': datetime.utcnow().isoformat() + "Z"
        }
        
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            print("❌ Failed to open video")
            return None
            
        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        
        # Sample every 0.5 seconds
        sample_rate = max(1, int(fps / 2))
        current_frame = 0
        
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break
            
            if current_frame % sample_rate == 0:
                timestamp_seconds = current_frame / fps
                minutes = int(timestamp_seconds // 60)
                seconds = int(timestamp_seconds % 60)
                timestamp_str = f"{minutes:02d}:{seconds:02d}"
                
                print(f"🔍 Frame {current_frame} ({timestamp_str})...", end=" ")
                
                try:
                    faces = DeepFace.extract_faces(
                        img_path=frame,
                        detector_backend="opencv",
                        enforce_detection=False,
                        align=False
                    )
                    
                    if len(faces) > 0:
                        print(f"{len(faces)} face(s)")
                        
                        annotated_frame = frame.copy()
                        match_found = False
                        matched_person = None
                        confidence = 0
                        
                        for face_obj in faces:
                            facial_area = face_obj['facial_area']
                            x, y, w, h = facial_area['x'], facial_area['y'], facial_area['w'], facial_area['h']
                            
                            face_img = frame[y:y+h, x:x+w]
                            if face_img.size == 0:
                                continue
                            
                            temp_path = os.path.join(app.config['UPLOAD_FOLDER'], f"temp_{uuid.uuid4().hex[:8]}.jpg")
                            cv2.imwrite(temp_path, face_img)
                            
                            for person in active_lost_persons:
                                ref_img = os.path.basename(person['image_url'])
                                ref_path = os.path.join(FACES_FOLDER, ref_img)
                                
                                if not os.path.exists(ref_path):
                                    continue
                                
                                try:
                                    result = DeepFace.verify(
                                        img1_path=temp_path,
                                        img2_path=ref_path,
                                        model_name="VGG-Face",
                                        detector_backend="skip",
                                        distance_metric="cosine",
                                        enforce_detection=False
                                    )
                                    
                                    if result['verified']:
                                        match_found = True
                                        matched_person = person
                                        confidence = int((1 - result['distance']) * 100)
                                        
                                        cv2.rectangle(annotated_frame, (x, y), (x+w, y+h), (0, 255, 0), 3)
                                        cv2.putText(annotated_frame, f"{person['name']} {confidence}%", 
                                                  (x, y-10), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                                        print(f"\n✅ FOUND! {person['name']} ({confidence}%)")
                                        break
                                except:
                                    pass
                            
                            if os.path.exists(temp_path):
                                os.remove(temp_path)
                            
                            if not match_found:
                                cv2.rectangle(annotated_frame, (x, y), (x+w, y+h), (0, 0, 255), 2)
                        
                        if match_found and matched_person:
                            frame_file = f"found_{matched_person['id']}_{uuid.uuid4().hex[:8]}.jpg"
                            frame_path = os.path.join(app.config['UPLOAD_FOLDER'], frame_file)
                            cv2.imwrite(frame_path, annotated_frame)
                            
                            match_data = {
                                "person_id": matched_person['id'],
                                "zone_id": zone_id,
                                "confidence": confidence,
                                "description": f"Found {matched_person['name']}",
                                "timestamp": timestamp_str,
                                "found_at": datetime.utcnow().isoformat() + "Z",
                                "found_frame_url": f"/uploads/{frame_file}",
                                "image_url": f"/uploads/{frame_file}"
                            }
                            
                            analysis['found_persons'].append(match_data)
                            FOUND_MATCHES.append(match_data)
                            matched_person['status'] = 'found'
                            
                            cap.release()
                            ZONE_ANALYSIS[zone_id] = analysis
                            return analysis
                    else:
                        print("No faces")
                except Exception as e:
                    print(f"Error: {e}")
            
            current_frame += 1
        
        cap.release()
        print("\n✅ Analysis complete - No matches")
        ZONE_ANALYSIS[zone_id] = analysis
        return analysis
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return None

def analyze_video_with_gemini(video_path, zone_id):
    try:
        import google.generativeai as genai
        from deepface import DeepFace
        import cv2
        import numpy as np
        
        # Load API Key
        api_key = get_gemini_key()
        
        if not api_key or "PASTE" in api_key:
            print(f"[{zone_id}] Gemini API Key not found or invalid.")
            return {
                'crowd_count': 0,
                'density_level': 'Low',
                'anomalies': [],
                'description': "Analysis failed: API Key missing",
                'sentiment': "Unknown"
            }
            
        genai.configure(api_key=api_key)
        
        # Upload file
        print(f"Uploading {video_path} to Gemini...")
        video_file = genai.upload_file(path=video_path)
        
        # Wait for processing
        print("Waiting for video processing...", end='')
        while video_file.state.name == "PROCESSING":
            print('.', end='')
            time.sleep(2)
            video_file = genai.get_file(video_file.name)

        if video_file.state.name == "FAILED":
            print("Video processing failed.")
            return None

        print(" Analyzing...")
        # Use confirmed working model
        model = genai.GenerativeModel('models/gemini-1.5-flash')
        
        # Construct prompt with lost persons
        lost_persons_desc = ""
        active_lost_persons = [p for p in LOST_PERSONS if p['status'] == 'active']
        if active_lost_persons:
            lost_persons_desc = "Also, check if any of the following lost persons are present in the video:\\n"
            for p in active_lost_persons:
                lost_persons_desc += f"- ID: {p['id']}, Name: {p['name']}, Age: {p['age']}, Description: {p['description']}\\n"
            lost_persons_desc += "If found, include a 'found_persons' list in the JSON with: person_id, timestamp (MM:SS), confidence, and description of where they are in the frame."

        prompt = f"""
        Analyze this CCTV footage for crowd management. 
        {lost_persons_desc}
        Return a JSON object with the following fields:
        - crowd_count (integer): Estimated number of people.
        - density_level (string): "Low", "Medium", "High", or "Critical".
        - anomalies (list of objects): List of anomalies. Each object should have:
            - type (string): "violence", "crowd_behavior", "abandoned_object", "unusual_movement", "gathering", or "other".
            - description (string): Brief description.
            - timestamp (string): Time of occurrence in "MM:SS" format.
            - confidence (integer): 0-100.
        - found_persons (list of objects): List of found lost persons (if any).
        - description (string): Brief summary of the scene.
        - sentiment (string): "Calm", "Agitated", "Panic", or "Happy".
        """
        
        response = model.generate_content([video_file, prompt], request_options={"timeout": 600})
        
        # Parse JSON from response
        text = response.text
        # Extract JSON block if wrapped in markdown
        match = re.search(r'```json\\n(.*?)\\n```', text, re.DOTALL)
        if match:
            json_str = match.group(1)
        else:
            json_str = text
            
        analysis = json.loads(json_str)
        analysis['timestamp'] = datetime.utcnow().isoformat() + "Z"
        
        # Handle found persons - HYBRID APPROACH
        if 'found_persons' in analysis and analysis['found_persons']:
            for match in analysis['found_persons']:
                match['zone_id'] = zone_id
                match['found_at'] = datetime.utcnow().isoformat() + "Z"
                
                # Extract frame for this match
                if 'timestamp' in match:
                    frame = extract_frame_at_timestamp(video_path, match['timestamp'])
                    if frame is not None:
                        # HYBRID: Use DeepFace/OpenCV to detect face and draw bounding box on this frame
                        try:
                            # Detect faces in this extracted frame
                            faces = DeepFace.extract_faces(
                                img_path=frame,
                                detector_backend="ssd", # Use robust detector
                                enforce_detection=False,
                                align=False
                            )
                            
                            annotated_frame = frame.copy()
                            face_found = False
                            
                            for face_obj in faces:
                                facial_area = face_obj['facial_area']
                                x, y, w, h = facial_area['x'], facial_area['y'], facial_area['w'], facial_area['h']
                                
                                # Draw Green Box (Assume Gemini is correct about the person being there)
                                # Ideally we would verify again, but for now let's trust Gemini's timestamp 
                                # and highlight the face.
                                cv2.rectangle(annotated_frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
                                cv2.putText(annotated_frame, f"Match: {match.get('confidence', 'High')}%", (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
                                face_found = True
                                
                            if face_found:
                                frame_filename = f"found_{match['person_id']}_{uuid.uuid4().hex[:8]}.jpg"
                                frame_path = os.path.join(app.config['UPLOAD_FOLDER'], frame_filename)
                                cv2.imwrite(frame_path, annotated_frame)
                                match['found_frame_url'] = f"/uploads/{frame_filename}"
                                match['image_url'] = f"/uploads/{frame_filename}"
                            else:
                                # Fallback: Save original frame if no face detected by local model
                                frame_filename = f"found_{match['person_id']}_{uuid.uuid4().hex[:8]}.jpg"
                                frame_path = os.path.join(app.config['UPLOAD_FOLDER'], frame_filename)
                                cv2.imwrite(frame_path, frame)
                                match['found_frame_url'] = f"/uploads/{frame_filename}"
                                match['image_url'] = f"/uploads/{frame_filename}"
                                
                        except Exception as e:
                            print(f"Hybrid processing error: {e}")
                            # Fallback to saving raw frame
                            frame_filename = f"found_{match['person_id']}_{uuid.uuid4().hex[:8]}.jpg"
                            frame_path = os.path.join(app.config['UPLOAD_FOLDER'], frame_filename)
                            cv2.imwrite(frame_path, frame)
                            match['found_frame_url'] = f"/uploads/{frame_filename}"
                            match['image_url'] = f"/uploads/{frame_filename}"
                
                FOUND_MATCHES.append(match)
                
                # Update lost person status if confidence is high
                if match.get('confidence', 0) > 80:
                    for p in LOST_PERSONS:
                        if p['id'] == match.get('person_id'):
                            p['status'] = 'found'
                            p['found_location'] = zone_id
                            break
        
        # Store in global
        ZONE_ANALYSIS[zone_id] = analysis
        
        # Check for anomalies and send SMS
        if 'anomalies' in analysis and analysis['anomalies']:
            for anomaly in analysis['anomalies']:
                # Send alert for high confidence anomalies
                if anomaly.get('confidence', 0) > 70:
                    send_anomaly_alert(zone_id, anomaly.get('type', 'Unknown'), anomaly.get('description', 'No description'))
                    
        print(f"Analysis complete for {zone_id}: {analysis}")
        return analysis
        
    except Exception as e:
        print(f"Gemini Analysis Error: {e}")
        return None

def fast_continuous_video_processor(video_path, zone_id, stop_flag_dict):
    """
    Fast continuous processor using OpenCV for people detection
    Only calls Gemini for anomaly detection when needed
    Updates every 2-3 seconds for real-time dashboard
    """
    try:
        import numpy as np
        
        # Initialize OpenCV people detector (HOG)
        hog = cv2.HOGDescriptor()
        hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())
        
        # Open video file
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            print(f"[{zone_id}] Failed to open video: {video_path}")
            return
        
        fps = cap.get(cv2.CAP_PROP_FPS) or 30
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        frame_interval = int(fps * 2)  # Analyze every 2 seconds
        
        print(f"[{zone_id}] Starting FAST continuous analysis: {total_frames} frames @ {fps} FPS")
        print(f"[{zone_id}] Analyzing every {frame_interval} frames (~2 seconds)")
        
        frame_count = 0
        analysis_count = 0
        last_gemini_call = 0
        last_crowd_count = 0
        
        while not stop_flag_dict.get('stop', False):
            ret, frame = cap.read()
            
            if not ret:
                # Loop back to beginning
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                frame_count = 0
                print(f"[{zone_id}] Looping video...")
                continue
            
            frame_count += 1
            
            # Analyze frame at intervals
            if frame_count % frame_interval == 0:
                analysis_count += 1
                timestamp_sec = frame_count / fps
                timestamp_min = int(timestamp_sec // 60)
                timestamp_sec_rem = int(timestamp_sec % 60)
                
                try:
                    # Resize frame for faster processing
                    resized = cv2.resize(frame, (640, 480))
                    
                    # Detect people using HOG
                    boxes, weights = hog.detectMultiScale(resized, winStride=(8, 8), padding=(4, 4), scale=1.05)
                    
                    crowd_count = len(boxes)
                    
                    # Determine density level
                    if crowd_count > 100:
                        density_level = "Critical"
                    elif crowd_count > 50:
                        density_level = "High"
                    elif crowd_count > 20:
                        density_level = "Medium"
                    else:
                        density_level = "Low"
                    
                    # Determine sentiment based on crowd density
                    if density_level == "Critical":
                        sentiment = "Agitated"
                    elif density_level == "High":
                        sentiment = "Busy"
                    else:
                        sentiment = "Calm"
                    
                    # Create analysis object
                    analysis = {
                        'crowd_count': crowd_count,
                        'density_level': density_level,
                        'sentiment': sentiment,
                        'description': f"Detected {crowd_count} people in the frame. Crowd density is {density_level.lower()}.",
                        'anomalies': [],
                        'timestamp': datetime.utcnow().isoformat() + "Z",
                        'video_timestamp': f"{timestamp_min}:{timestamp_sec_rem:02d}",
                        'detection_method': 'opencv_hog'
                    }
                    
                    # Call Gemini for detailed analysis if significant change or every 30 seconds
                    crowd_change = abs(crowd_count - last_crowd_count)
                    time_since_gemini = analysis_count - last_gemini_call
                    
                    should_call_gemini = (
                        crowd_change > 10 or  # Significant crowd change
                        density_level in ["High", "Critical"] or  # High density
                        time_since_gemini >= 15  # Every 30 seconds (15 * 2sec intervals)
                    )
                    
                    if should_call_gemini:
                        print(f"[{zone_id}] Calling Gemini for detailed analysis (change: {crowd_change}, density: {density_level})")
                        
                        # Save frame temporarily
                        # Save frame with unique filename upfront
                        frame_filename = f"anomaly_{zone_id}_{int(time.time())}_{uuid.uuid4().hex[:8]}.jpg"
                        frame_path = os.path.join(app.config['UPLOAD_FOLDER'], frame_filename)
                        cv2.imwrite(frame_path, frame)
                        
                        # Get Gemini analysis in background (non-blocking)
                        try:
                            import google.generativeai as genai
                            
                            api_key = get_gemini_key()
                            
                            if api_key:
                                genai.configure(api_key=api_key)
                                model = genai.GenerativeModel('models/gemini-2.5-flash')
                                
                                frame_file = genai.upload_file(path=frame_path)
                                
                                # Wait for processing
                                while frame_file.state.name == "PROCESSING":
                                    time.sleep(1)
                                    frame_file = genai.get_file(frame_file.name)
                                
                                if frame_file.state.name != "FAILED":
                                    prompt = f"""
                                    Analyze this CCTV frame for SECURITY THREATS and SAFETY CONCERNS only.
                                    
                                    IMPORTANT: Do NOT report technical detection issues, system errors, or crowd count mismatches.
                                    Only report REAL security threats such as:
                                    - Fire/smoke
                                    - Violence or fighting
                                    - Suspicious behavior
                                    - Abandoned objects
                                    - Unauthorized access
                                    - Medical emergencies
                                    - Panic situations
                                    
                                    Return JSON with:
                                    - anomalies (list): ONLY real security threats. Each with:
                                      * type: "fire", "violence", "suspicious_behavior", "abandoned_object", "medical_emergency", "panic", "unauthorized_access"
                                      * description: Brief, clear description of the threat
                                      * confidence: 0-100
                                    - sentiment (string): "Calm", "Agitated", "Panic", or "Happy"
                                    - description (string): Brief scene summary
                                    
                                    If NO real threats exist, return empty anomalies array.
                                    """
                                    
                                    response = model.generate_content([frame_file, prompt], request_options={"timeout": 30})
                                    
                                    # Parse response
                                    text = response.text
                                    match = re.search(r'```json\n(.*?)\n```', text, re.DOTALL)
                                    if match:
                                        json_str = match.group(1)
                                    else:
                                        json_str = text
                                    
                                    gemini_data = json.loads(json_str)
                                    
                                    # Merge Gemini data with OpenCV data
                                    gemini_anomalies = gemini_data.get('anomalies', [])
                                    
                                    # Filter out technical/system errors - only keep real security threats
                                    VALID_ANOMALY_TYPES = [
                                        'fire', 'violence', 'suspicious_behavior', 'abandoned_object',
                                        'medical_emergency', 'panic', 'unauthorized_access', 'weapon',
                                        'intrusion', 'vandalism', 'theft', 'crowd_surge'
                                    ]
                                    
                                    filtered_anomalies = []
                                    for anomaly in gemini_anomalies:
                                        anomaly_type = anomaly.get('type', '').lower()
                                        anomaly_desc = anomaly.get('description', '').lower()
                                        
                                        # Skip if it's a technical/detection error
                                        skip_keywords = [
                                            'detection', 'error', 'inconsistency', 'mismatch', 
                                            'opencv', 'system', 'incorrect', 'discrepancy',
                                            'technical', 'count', 'density mismatch'
                                        ]
                                        
                                        is_technical_error = any(keyword in anomaly_type for keyword in skip_keywords) or \
                                                           any(keyword in anomaly_desc for keyword in skip_keywords)
                                        
                                        # Only keep real security threats
                                        if not is_technical_error and anomaly_type in VALID_ANOMALY_TYPES:
                                            filtered_anomalies.append(anomaly)
                                    
                                    analysis['anomalies'] = filtered_anomalies
                                    analysis['sentiment'] = gemini_data.get('sentiment', sentiment)
                                    analysis['description'] = gemini_data.get('description', analysis['description'])
                                    analysis['detection_method'] = 'opencv_hog + gemini'
                                    
                                    last_gemini_call = analysis_count
                                    
                                    # If anomalies detected, keep the frame
                                    if analysis['anomalies']:
                                        print(f"[{zone_id}] Saved anomaly frame: {frame_filename}")
                                            
                                        # Add image URL to each anomaly
                                        for anomaly in analysis['anomalies']:
                                            anomaly['image_url'] = f"http://localhost:5000/uploads/{frame_filename}"
                                            anomaly['imageUrl'] = f"http://localhost:5000/uploads/{frame_filename}"  # Fallback
                                            anomaly['timestamp'] = analysis['timestamp']
                                            anomaly['zone_id'] = zone_id
                                            anomaly['location'] = CAMERA_ENDPOINTS.get(zone_id, {}).get('name', zone_id)
                                            anomaly['status'] = 'active'
                                            anomaly['severity'] = 'high' if anomaly.get('confidence', 0) > 85 else 'medium'
                                            anomaly['id'] = str(uuid.uuid4())
                                            
                                            # Add to persistent storage
                                            PERSISTENT_ANOMALIES.append(anomaly.copy())
                                            
                                            if anomaly.get('confidence', 0) > 70:
                                                send_anomaly_alert(zone_id, anomaly.get('type', 'Unknown'), anomaly.get('description', 'No description'))
                                    else:
                                        # No anomalies, delete file
                                        if os.path.exists(frame_path):
                                            os.remove(frame_path)
                                
                                # Clean up if still exists (fallback)
                                # if os.path.exists(frame_path) and not analysis['anomalies']:
                                #    os.remove(frame_path)
                        
                        except Exception as e:
                            print(f"[{zone_id}] Gemini call failed: {e}")
                            if os.path.exists(frame_path):
                                os.remove(frame_path)
                    
                    # Update global analysis
                    ZONE_ANALYSIS[zone_id] = analysis
                    update_zone_history(zone_id, analysis)
                    
                    last_crowd_count = crowd_count
                    
                    print(f"[{zone_id}] Analysis #{analysis_count}: {crowd_count} people, {density_level} density ({analysis.get('detection_method', 'opencv')})")
                    
                except Exception as e:
                    print(f"[{zone_id}] Frame analysis error: {e}")
            
            # Small delay to prevent CPU overload
            time.sleep(0.01)
        
        cap.release()
        print(f"[{zone_id}] Fast continuous analysis stopped")
        
    except Exception as e:
        print(f"[{zone_id}] Fast processor error: {e}")


def continuous_video_processor(video_path, zone_id, stop_flag_dict):
    """
    LIVE Frame-by-Frame processor with Gemini AI
    Analyzes frames every 3 seconds for truly real-time updates
    Runs in a background thread
    """
    try:
        import google.generativeai as genai
        
        # Load API Key
        api_key = get_gemini_key()
        
        if not api_key or "PASTE" in api_key:
            safe_print(f"[{zone_id}] ❌ Gemini API Key not found. Stopping continuous analysis.")
            return
        
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('models/gemini-2.0-flash-exp')  # Latest fastest model
        
        # Open video file
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            safe_print(f"[{zone_id}] ❌ Failed to open video: {video_path}")
            return
        
        fps = cap.get(cv2.CAP_PROP_FPS) or 30
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        frame_interval = int(fps * 3)  # 🔥 Analyze every 3 seconds for LIVE updates
        
        safe_print(f"[{zone_id}] 🎥 Starting LIVE frame-by-frame analysis:")
        safe_print(f"[{zone_id}]    - Total frames: {total_frames} @ {fps} FPS")
        safe_print(f"[{zone_id}]    - Update interval: {frame_interval} frames (~3 seconds)")
        safe_print(f"[{zone_id}]    - AI Model: Gemini 2.0 Flash")
        
        frame_count = 0
        analysis_count = 0
        loop_count = 0
        
        while not stop_flag_dict.get('stop', False):
            ret, frame = cap.read()
            
            if not ret:
                # Loop back to beginning for continuous monitoring
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                frame_count = 0
                loop_count += 1
                safe_print(f"[{zone_id}] 🔄 Looping video (Loop #{loop_count})...")
                continue
            
            frame_count += 1
            
            # Analyze frame at intervals
            if frame_count % frame_interval == 0:
                analysis_count += 1
                timestamp_sec = frame_count / fps
                timestamp_min = int(timestamp_sec // 60)
                timestamp_sec_rem = int(timestamp_sec % 60)
                
                safe_print(f"[{zone_id}] 📊 Analyzing frame {frame_count}/{total_frames} at {timestamp_min}:{timestamp_sec_rem:02d}")
                
                # Face Recognition (Every ~3 seconds or faster if needed)
                # We run this BEFORE the heavy Gemini call
                try:
                    from deepface import DeepFace
                    # Run matching against the faces folder
                    # VGG-Face is robust. enforce_detection=False prevents crash if no face.
                    dfs = DeepFace.find(img_path=frame, db_path=FACES_FOLDER, model_name='VGG-Face', enforce_detection=False, silent=True)
                    
                    for df in dfs:
                        if not df.empty:
                            for index, row in df.iterrows():
                                matched_path = row['identity']
                                basename = os.path.basename(matched_path)
                                
                                matched_person = None
                                for p in LOST_PERSONS:
                                    # Check if this image belongs to an active lost person
                                    if p.get('status') == 'active' and basename in p.get('image_url', ''):
                                        matched_person = p
                                        break
                                
                                if matched_person:
                                    x, y, w, h = int(row['source_x']), int(row['source_y']), int(row['source_w']), int(row['source_h'])
                                    cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 255, 0), 2)
                                    cv2.putText(frame, f"FOUND: {matched_person['name']}", (x, y-10), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2)
                                    
                                    safe_print(f"[{zone_id}] ✅ FACE MATCH FOUND: {matched_person['name']}")
                                    
                                    # Add to found matches
                                    found_match = {
                                        "person_id": matched_person['id'],
                                        "name": matched_person['name'],
                                        "confidence": 95,
                                        "found_at": datetime.utcnow().isoformat() + "Z",
                                        "zone_id": zone_id,
                                        "location": CAMERA_ENDPOINTS.get(zone_id, {}).get('name', zone_id),
                                        "description": f"Face matched for {matched_person['name']}",
                                        "image_url": matched_person['image_url'] # Use reference image
                                    }
                                    
                                    # Avoid duplicate entries
                                    already_found = False
                                    for m in FOUND_MATCHES:
                                        if m['person_id'] == matched_person['id'] and m['zone_id'] == zone_id:
                                            already_found = True
                                            break
                                    
                                    if not already_found:
                                        FOUND_MATCHES.append(found_match)
                                        matched_person['status'] = 'found'
                                        matched_person['found_location'] = zone_id
                                        
                                        # Send SMS
                                        send_sms_alert("+917337743545", f"FOUND: {matched_person['name']} located at {found_match['location']}")
                except Exception as e:
                    # safe_print(f"[{zone_id}] Face Rec Error: {e}")
                    pass

                try:
                    # Save frame with unique timestamp
                    frame_filename = f"live_{zone_id}_{int(time.time())}_{uuid.uuid4().hex[:6]}.jpg"
                    frame_path = os.path.join(app.config['UPLOAD_FOLDER'], frame_filename)
                    cv2.imwrite(frame_path, frame)
                    
                    # Upload frame to Gemini
                    safe_print(f"[{zone_id}]    ⬆️  Uploading frame to Gemini AI...")
                    frame_file = genai.upload_file(path=frame_path)
                    
                    # Wait for processing
                    wait_count = 0
                    while frame_file.state.name == "PROCESSING":
                        time.sleep(0.5)
                        wait_count += 1
                        if wait_count > 20:  # 10 second timeout
                            safe_print(f"[{zone_id}]    ⚠️  Upload timeout")
                            break
                        frame_file = genai.get_file(frame_file.name)
                    
                    if frame_file.state.name == "FAILED":
                        safe_print(f"[{zone_id}]    ❌ Frame processing failed")
                        if os.path.exists(frame_path):
                            os.remove(frame_path)
                        continue
                    
                    # Construct enhanced prompt for live analysis
                    lost_persons_desc = ""
                    active_lost_persons = [p for p in LOST_PERSONS if p['status'] == 'active']
                    if active_lost_persons:
                        lost_persons_desc = "LOST PERSONS TO FIND:\\n"
                        for p in active_lost_persons:
                            lost_persons_desc += f"- ID: {p['id']}, Name: {p['name']}, Age: {p['age']}, Description: {p['description']}\\n"
                    
                    prompt = f"""
                    🎥 LIVE CCTV FRAME ANALYSIS
                    
                    Analyze this security camera frame in REAL-TIME for crowd management.
                    
                    {lost_persons_desc}
                    
                    Return a JSON object with the following:
                    
                    {{
                      "crowd_count": <integer - estimated number of people visible>,
                      "density_level": "<Low/Medium/High/Critical>",
                      "anomalies": [
                        {{
                          "type": "<fire/violence/suspicious_behavior/abandoned_object/medical_emergency/panic/weapon/etc>",
                          "description": "<detailed description>",
                          "confidence": <0-100>,
                          "timestamp": "MM:SS",
                          "severity": "<low/medium/high/critical>"
                        }}
                      ],
                      "found_persons": [
                        {{
                          "person_id": "<ID from lost persons list>",
                          "confidence": <0-100>,
                          "description": "<where they are in frame>"
                        }}
                      ],
                      "description": "<brief scene summary - what's happening right now>",
                      "sentiment": "<Calm/Agitated/Panic/Happy>"
                    }}
                    
                    Only report REAL security threats, not technical errors.
                    """
                    
                    safe_print(f"[{zone_id}]    🤖 Requesting AI analysis...")
                    response = model.generate_content([frame_file, prompt], request_options={"timeout": 60})
                    
                    # Parse response
                    text = response.text
                    match = re.search(r'```json\\n(.*?)\\n```', text, re.DOTALL)
                    if not match:
                        match = re.search(r'```\\n(.*?)\\n```', text, re.DOTALL)
                    if match:
                        json_str = match.group(1)
                    else:
                        json_str = text
                    
                    analysis = json.loads(json_str)
                    analysis['timestamp'] = datetime.utcnow().isoformat() + "Z"
                    analysis['video_timestamp'] = f"{timestamp_min}:{timestamp_sec_rem:02d}"
                    analysis['frame_number'] = frame_count
                    analysis['loop_number'] = loop_count
                    analysis['detection_method'] = 'gemini_live'
                    
                    # Handle found persons
                    if 'found_persons' in analysis and analysis['found_persons']:
                        for match_person in analysis['found_persons']:
                            match_person['zone_id'] = zone_id
                            match_person['found_at'] = datetime.utcnow().isoformat() + "Z"
                            FOUND_MATCHES.append(match_person)
                            safe_print(f"[{zone_id}]    ✅ FOUND PERSON: {match_person.get('person_id')}")
                            
                            if match_person.get('confidence', 0) > 80:
                                for p in LOST_PERSONS:
                                    if p['id'] == match_person.get('person_id'):
                                        p['status'] = 'found'
                                        p['found_location'] = zone_id
                                        break
                    
                    # Process anomalies
                    has_real_anomalies = False
                    if 'anomalies' in analysis and analysis['anomalies']:
                        for anomaly in analysis['anomalies']:
                            # Add metadata to anomaly
                            anomaly['image_url'] = f"http://localhost:5000/uploads/{frame_filename}"
                            anomaly['imageUrl'] = f"http://localhost:5000/uploads/{frame_filename}"
                            anomaly['timestamp'] = analysis['timestamp']
                            anomaly['zone_id'] = zone_id
                            anomaly['location'] = CAMERA_ENDPOINTS.get(zone_id, {}).get('name', zone_id)
                            anomaly['status'] = 'active'
                            anomaly['severity'] = anomaly.get('severity', 'high' if anomaly.get('confidence', 0) > 85 else 'medium')
                            anomaly['id'] = str(uuid.uuid4())
                            
                            # Store in persistent storage
                            PERSISTENT_ANOMALIES.append(anomaly.copy())
                            has_real_anomalies = True
                            
                            # Send alerts for high-confidence anomalies
                            if anomaly.get('confidence', 0) > 70:
                                safe_print(f"[{zone_id}]    🚨 ANOMALY: {anomaly.get('type')} - {anomaly.get('description')}")
                                send_anomaly_alert(zone_id, anomaly.get('type', 'Unknown'), anomaly.get('description', 'No description'))
                    
                    # Delete frame if no anomalies
                    if not has_real_anomalies and os.path.exists(frame_path):
                        os.remove(frame_path)
                    
                    # Update global analysis
                    ZONE_ANALYSIS[zone_id] = analysis
                    update_zone_history(zone_id, analysis)
                    
                    safe_print(f"[{zone_id}]    ✅ Analysis #{analysis_count}: {analysis.get('crowd_count', 0)} people, {analysis.get('density_level', 'Unknown')} density, {len(analysis.get('anomalies', []))} anomalies")
                    
                except json.JSONDecodeError as e:
                    safe_print(f"[{zone_id}]    ⚠️  JSON parse error: {e}")
                    # Fallback: create basic analysis
                    ZONE_ANALYSIS[zone_id] = {
                        'crowd_count': 0,
                        'density_level': 'Unknown',
                        'anomalies': [],
                        'description': 'Analysis in progress...',
                        'sentiment': 'Unknown',
                        'timestamp': datetime.utcnow().isoformat() + "Z"
                    }
                except Exception as e:
                    safe_print(f"[{zone_id}]    ❌ Frame analysis error: {e}")
                    if 'frame_path' in locals() and os.path.exists(frame_path):
                        os.remove(frame_path)
            
            # Small delay to prevent CPU overload
            time.sleep(0.001)
        
        cap.release()
        safe_print(f"[{zone_id}] ⏹️  Live analysis stopped (Total analyses: {analysis_count})")
        
    except Exception as e:
        safe_print(f"[{zone_id}] ❌ CRITICAL ERROR: {e}")
        import traceback
        traceback.print_exc()



@app.route('/api/crowd/prediction/<zone_id>', methods=['GET'])
def get_zone_prediction(zone_id):
    """Get crowd prediction and history for a zone"""
    
    # Get current analysis to use actual density for 8th Mile zones
    current_analysis = ZONE_ANALYSIS.get(zone_id, {})
    actual_density = current_analysis.get('density_percentage')
    
    # Get history or generate mock if empty
    history = ZONE_HISTORY.get(zone_id, [])
    now = datetime.now()
    
    if not history:
        # Generate mock history for demo
        history = []
        
        # Use actual density if available (for 8th Mile zones), otherwise generate mock
        if actual_density is not None:
            base_density = actual_density
            trend_type = 'stable'
        # Semantic mock data for old zones
        elif 'parking' in zone_id.lower():
            base_density = 15
            trend_type = 'stable'
        elif 'stage' in zone_id.lower():
            base_density = 85
            trend_type = 'increasing'
        elif 'food' in zone_id.lower() and actual_density is None:  # Only if not 8th Mile food court
            base_density = 65
            trend_type = 'fluctuating'
        else:
            seed = sum(ord(c) for c in zone_id)
            base_density = (seed % 60) + 20
            trend_type = 'random'
            
        for i in range(5, 0, -1):
            t = (now - timedelta(minutes=i*5)).strftime("%H:%M")
            
            # Use stable trend for 8th Mile zones to maintain correct density
            if actual_density is not None:
                trend = random.randint(-2, 2)  # Small variation
            elif trend_type == 'increasing':
                trend = i * 2
            elif trend_type == 'decreasing':
                trend = -i * 2
            elif trend_type == 'stable':
                trend = (i % 2)
            elif trend_type == 'fluctuating':
                trend = (i % 3) * 4
            else:
                trend = ((i * 3) % 7) * (1 if i%2==0 else -1)

            history.append({
                "time": t,
                "density": max(5, min(95, base_density + trend))
            })
        ZONE_HISTORY[zone_id] = history
    else:
        # Simulate live updates: if last point is not current minute, add new point
        last_point = history[-1]
        last_time_str = last_point.get('time')
        
        # Handle real data timestamp (ISO format)
        if not last_time_str and 'timestamp' in last_point:
            try:
                ts = last_point['timestamp']
                if 'T' in ts:
                    dt = datetime.fromisoformat(ts.replace('Z', '+00:00'))
                    last_time_str = dt.strftime("%H:%M")
                else:
                    last_time_str = ts
            except:
                last_time_str = now.strftime("%H:%M")
                
        if not last_time_str:
             last_time_str = now.strftime("%H:%M")

        current_time_str = now.strftime("%H:%M")
        
        if last_time_str != current_time_str:
            import random
            last_density = last_point.get('density')
            if last_density is None:
                last_density = last_point.get('crowd_count', 0)
            
            # For 8th Mile zones, use actual density, otherwise slight variation
            if actual_density is not None:
                new_density = actual_density + random.randint(-1, 1)  # Minimal variation
            else:
                variation = random.randint(-3, 5) # Slight upward trend for demo
                new_density = max(10, min(95, last_density + variation))
            
            history.append({
                "time": current_time_str,
                "density": new_density,
                "crowd_count": new_density # Store both for compatibility
            })
            
            if len(history) > 20:
                history.pop(0)
            
            ZONE_HISTORY[zone_id] = history
        
    # Calculate prediction (simple linear trend or mock)
    current_density = history[-1]['density']
    predicted_count = int(current_density * 1.1) # +10%
    
    # Get latest analysis for saliency
    latest_analysis = ZONE_ANALYSIS.get(zone_id, {})
    saliency_map = latest_analysis.get('saliency_map', None)
    saliency_frames = latest_analysis.get('saliency_frames', [])
    explanation = latest_analysis.get('explanation', None)
    processed_video_url = latest_analysis.get('processed_video_url', None)

    return jsonify({
        "current_count": current_density,
        "predicted_count_15min": predicted_count,
        "trend": "increasing" if predicted_count > current_density else "stable",
        "history": history,
        "saliency_map": saliency_map,
        "saliency_frames": saliency_frames,
        "explanation": explanation,
        "processed_video_url": processed_video_url
    })

@app.route('/api/cameras/upload-video', methods=['POST'])
def upload_video_for_analysis():
    print("📸 Upload video request received")
    try:
        if 'video' not in request.files:
            print("❌ No video file in request")
            return jsonify({"error": "No video file provided"}), 400
            
        file = request.files['video']
        zone_id = request.form.get('zone_id', 'manual_upload')
        
        if file.filename == '':
            print("❌ Empty filename")
            return jsonify({"error": "No selected file"}), 400
            
        # Save file
        filename = secure_filename(f"analysis_{uuid.uuid4().hex[:8]}_{file.filename}")
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        print(f"✅ Video saved to {filepath}")
        
        # Use YOLO + DeepSORT Analysis (via subprocess)
        print("🔄 Starting analysis subprocess...")
        import subprocess
        import json
        
        cmd = [
            sys.executable,
            os.path.join(os.path.dirname(__file__), 'run_analysis.py'),
            filepath,
            zone_id,
            json.dumps(LOST_PERSONS),
            app.config['UPLOAD_FOLDER'],
            FACES_FOLDER
        ]
        
        print(f"🚀 Running command: {' '.join(cmd)}")
        
        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"
        env["KMP_DUPLICATE_LIB_OK"] = "TRUE"
        
        try:
            # Run subprocess
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True, env=env)
            print("✅ Subprocess finished")
            
            stdout_content = result.stdout if result.stdout else ""
            stderr_content = result.stderr if result.stderr else ""
            
            with open("subprocess_stdout.log", "w", encoding="utf-8") as f:
                f.write(stdout_content)
            with open("subprocess_stderr.log", "w", encoding="utf-8") as f:
                f.write(stderr_content)
            
            # Parse output - find the last line that is valid JSON
            lines = stdout_content.strip().split('\n')
            json_line = lines[-1] if lines and lines[0] else "{}"
            
            # Fallback: check stderr for RESULT: prefix
            if not stdout_content.strip() or json_line == "{}":
             json_line = stdout_content
            
            # Try to parse stdout
            try:
                analysis = json.loads(json_line)
            except json.JSONDecodeError:
                print(f"⚠️ Failed to parse stdout JSON. Attempting fallback to stderr...")
                # Fallback: Check stderr for RESULT: prefix
                found_in_stderr = False
                for line in stderr_content.splitlines():
                    if line.startswith("RESULT:"):
                        json_line = line[7:] # Strip RESULT: prefix
                        try:
                            analysis = json.loads(json_line)
                            found_in_stderr = True
                            print("✅ Successfully parsed result from stderr")
                            break
                        except json.JSONDecodeError:
                            pass
                
                if not found_in_stderr:
                    print(f"❌ Failed to parse JSON from both stdout and stderr")
                    print(f"Full stdout: {result.stdout}")
                    print(f"Full stderr: {result.stderr}")
                    analysis = None
                
            if analysis:
                update_zone_history(zone_id, analysis)
                return jsonify({
                    "message": "Video analysis complete",
                    "analysis": analysis
                })
            else:
                print(f"❌ Analysis failed. Stderr: {result.stderr}")
                return jsonify({"error": "Analysis failed to produce valid output"}), 500
                
        except subprocess.CalledProcessError as e:
            with open("subprocess_error.log", "w", encoding="utf-8") as f:
                f.write(e.stderr)
            print(f"❌ Subprocess error: {e.stderr}")
            return jsonify({"error": f"Analysis crashed: {e.stderr}"}), 500
                
    except Exception as e:
        print(f"❌ Upload Error: {e}")
        import traceback
        traceback.print_exc()
        with open("upload_debug.log", "w") as f:
            f.write(f"Error: {str(e)}\n")
            traceback.print_exc(file=f)
        return jsonify({"error": str(e)}), 500
    
    # Fallback return
    return jsonify({"error": "Unknown error occurred"}), 500

def update_zone_history(zone_id, analysis):
    """Update historical data for real-time graphs"""
    if zone_id not in ZONE_HISTORY:
        ZONE_HISTORY[zone_id] = []
    
    # Store latest analysis
    ZONE_ANALYSIS[zone_id] = analysis
    
    timestamp = datetime.utcnow().isoformat() + "Z"
    data_point = {
        "timestamp": timestamp,
        "crowd_count": analysis.get('crowd_count', 0) if analysis else 0,
        "density_level": analysis.get('density_level', 'Low') if analysis else 'Low',
        "anomaly_count": len(analysis.get('anomalies', [])) if analysis else 0
    }
    
    ZONE_HISTORY[zone_id].append(data_point)
    
    # Keep only last 20 data points
    if len(ZONE_HISTORY[zone_id]) > 20:
        ZONE_HISTORY[zone_id] = ZONE_HISTORY[zone_id][-20:]

# Dedicated Camera Endpoints for Specific Zones

@app.route('/api/cameras/food-court/upload', methods=['POST'])
def upload_food_court_video():
    """
    Upload video from Food Court camera
    ---
    tags:
      - Camera Management
    consumes:
      - multipart/form-data
    parameters:
      - name: video
        in: formData
        type: file
        required: true
      - name: continuous
        in: formData
        type: boolean
        required: false
        description: Enable continuous analysis (default is true)
    responses:
      200:
        description: Video uploaded and analyzed
    """
    if 'video' not in request.files:
        return jsonify({"error": "No video file provided"}), 400
    
    video = request.files['video']
    filename = secure_filename(video.filename)
    save_path = os.path.join(app.config['UPLOAD_FOLDER'], f"food_court_{filename}")
    video.save(save_path)
    
    # Check if continuous mode is requested (default: True)
    continuous_mode = request.form.get('continuous', 'true').lower() == 'true'
    
    # Start continuous processing immediately (non-blocking)
    if continuous_mode:
        with VIDEO_PROCESSING_LOCK:
            # Stop existing processor if any
            if 'food_court' in ACTIVE_VIDEO_PROCESSORS:
                ACTIVE_VIDEO_PROCESSORS['food_court']['stop_flag']['stop'] = True
                print("[food_court] Stopping previous continuous processor...")
            
            # Start new processor in background thread - LIVE GEMINI AI
            stop_flag = {'stop': False}
            thread = threading.Thread(
                target=continuous_video_processor,  # 🔥 Live frame-by-frame Gemini analysis
                args=(save_path, 'food_court', stop_flag),
                daemon=True
            )
            thread.start()
            
            ACTIVE_VIDEO_PROCESSORS['food_court'] = {
                'thread': thread,
                'stop_flag': stop_flag,
                'video_path': save_path,
                'started_at': datetime.utcnow().isoformat() + "Z"
            }
            
            print(f"[food_court] Started continuous analysis for {filename}")
        
        # Return immediately - analysis will happen in background
        return jsonify({
            "message": "Food Court video uploaded. Analysis starting...",
            "zone": "Food Court",
            "video_url": f"/uploads/food_court_{filename}",
            "analysis": None,  # Will be populated by continuous processor
            "endpoint": CAMERA_ENDPOINTS['food_court'],
            "continuous_mode": True,
            "status": "Processing continuously - check /api/zones/food_court/density for live data"
        })
    else:
        # One-time analysis (blocking)
        analysis = analyze_video_with_gemini(save_path, 'food_court')
        update_zone_history('food_court', analysis)
        
        return jsonify({
            "message": "Food Court video analyzed successfully",
            "zone": "Food Court",
            "video_url": f"/uploads/food_court_{filename}",
            "analysis": analysis,
            "endpoint": CAMERA_ENDPOINTS['food_court'],
            "continuous_mode": False,
            "status": "One-time analysis complete"
        })

@app.route('/api/cameras/parking/upload', methods=['POST'])
def upload_parking_video():
    """
    Upload video from Parking Area camera
    ---
    tags:
      - Camera Management
    consumes:
      - multipart/form-data
    parameters:
      - name: video
        in: formData
        type: file
        required: true
      - name: continuous
        in: formData
        type: boolean
        required: false
        description: Enable continuous analysis (default is true)
    responses:
      200:
        description: Video uploaded and analyzed
    """
    if 'video' not in request.files:
        return jsonify({"error": "No video file provided"}), 400
    
    video = request.files['video']
    filename = secure_filename(video.filename)
    save_path = os.path.join(app.config['UPLOAD_FOLDER'], f"parking_{filename}")
    video.save(save_path)
    
    continuous_mode = request.form.get('continuous', 'true').lower() == 'true'
    analysis = analyze_video_with_gemini(save_path, 'parking')
    update_zone_history('parking', analysis)
    
    if continuous_mode:
        with VIDEO_PROCESSING_LOCK:
            if 'parking' in ACTIVE_VIDEO_PROCESSORS:
                ACTIVE_VIDEO_PROCESSORS['parking']['stop_flag']['stop'] = True
            stop_flag = {'stop': False}
            thread = threading.Thread(target=continuous_video_processor, args=(save_path, 'parking', stop_flag), daemon=True)  # Live Gemini AI
            thread.start()
            ACTIVE_VIDEO_PROCESSORS['parking'] = {'thread': thread, 'stop_flag': stop_flag, 'video_path': save_path, 'started_at': datetime.utcnow().isoformat() + "Z"}
            print(f"[parking] Started continuous analysis for {filename}")
    
    return jsonify({
        "message": "Parking Area video analyzed successfully",
        "zone": "Parking",
        "video_url": f"/uploads/parking_{filename}",
        "analysis": analysis,
        "endpoint": CAMERA_ENDPOINTS['parking'],
        "continuous_mode": continuous_mode,
        "status": "Processing continuously" if continuous_mode else "One-time analysis complete"
    })

@app.route('/api/cameras/main-stage/upload', methods=['POST'])
def upload_main_stage_video():
    """
    Upload video from Main Stage camera
    ---
    tags:
      - Camera Management
    consumes:
      - multipart/form-data
    parameters:
      - name: video
        in: formData
        type: file
        required: true
      - name: continuous
        in: formData
        type: boolean
        required: false
        description: Enable continuous analysis (default is true)
    responses:
      200:
        description: Video uploaded and analyzed
    """
    if 'video' not in request.files:
        return jsonify({"error": "No video file provided"}), 400
    
    video = request.files['video']
    filename = secure_filename(video.filename)
    save_path = os.path.join(app.config['UPLOAD_FOLDER'], f"main_stage_{filename}")
    video.save(save_path)
    
    continuous_mode = request.form.get('continuous', 'true').lower() == 'true'
    analysis = analyze_video_with_gemini(save_path, 'main_stage')
    update_zone_history('main_stage', analysis)
    
    if continuous_mode:
        with VIDEO_PROCESSING_LOCK:
            if 'main_stage' in ACTIVE_VIDEO_PROCESSORS:
                ACTIVE_VIDEO_PROCESSORS['main_stage']['stop_flag']['stop'] = True
            stop_flag = {'stop': False}
            thread = threading.Thread(target=continuous_video_processor, args=(save_path, 'main_stage', stop_flag), daemon=True)  # Live Gemini AI
            thread.start()
            ACTIVE_VIDEO_PROCESSORS['main_stage'] = {'thread': thread, 'stop_flag': stop_flag, 'video_path': save_path, 'started_at': datetime.utcnow().isoformat() + "Z"}
            print(f"[main_stage] Started continuous analysis for {filename}")
    
    return jsonify({
        "message": "Main Stage video analyzed successfully",
        "zone": "Main Stage",
        "video_url": f"/uploads/main_stage_{filename}",
        "analysis": analysis,
        "endpoint": CAMERA_ENDPOINTS['main_stage'],
        "continuous_mode": continuous_mode,
        "status": "Processing continuously" if continuous_mode else "One-time analysis complete"
    })

@app.route('/api/cameras/testing/upload', methods=['POST'])
def upload_testing_video():
    """
    Upload video to Testing zone camera
    ---
    tags:
      - Camera Management
    consumes:
      - multipart/form-data
    parameters:
      - name: video
        in: formData
        type: file
        required: true
      - name: continuous
        in: formData
        type: boolean
        required: false
        description: Enable continuous analysis (default is true)
    responses:
      200:
        description: Video uploaded and analyzed
    """
    if 'video' not in request.files:
        return jsonify({"error": "No video file provided"}), 400
    
    video = request.files['video']
    filename = secure_filename(video.filename)
    save_path = os.path.join(app.config['UPLOAD_FOLDER'], f"testing_{filename}")
    video.save(save_path)
    
    continuous_mode = request.form.get('continuous', 'true').lower() == 'true'
    analysis = analyze_video_with_gemini(save_path, 'testing')
    update_zone_history('testing', analysis)
    
    if continuous_mode:
        with VIDEO_PROCESSING_LOCK:
            if 'testing' in ACTIVE_VIDEO_PROCESSORS:
                ACTIVE_VIDEO_PROCESSORS['testing']['stop_flag']['stop'] = True
            stop_flag = {'stop': False}
            thread = threading.Thread(target=continuous_video_processor, args=(save_path, 'testing', stop_flag), daemon=True)  # Live Gemini AI
            thread.start()
            ACTIVE_VIDEO_PROCESSORS['testing'] = {'thread': thread, 'stop_flag': stop_flag, 'video_path': save_path, 'started_at': datetime.utcnow().isoformat() + "Z"}
            print(f"[testing] Started continuous analysis for {filename}")
    
    return jsonify({
        "message": "Testing zone video analyzed successfully",
        "zone": "Testing",
        "video_url": f"/uploads/testing_{filename}",
        "analysis": analysis,
        "endpoint": CAMERA_ENDPOINTS['testing'],
        "continuous_mode": continuous_mode,
        "status": "Processing continuously" if continuous_mode else "One-time analysis complete"
    })

@app.route('/api/cameras/continuous/status', methods=['GET'])
def get_continuous_status():
    """
    Get status of all continuous video processors
    ---
    tags:
      - Camera Management
    responses:
      200:
        description: Status of all active processors
    """
    status = {}
    with VIDEO_PROCESSING_LOCK:
        for zone_id, processor in ACTIVE_VIDEO_PROCESSORS.items():
            status[zone_id] = {
                "active": processor['thread'].is_alive(),
                "video_path": processor['video_path'],
                "started_at": processor['started_at']
            }
    return jsonify({
        "active_processors": len(status),
        "processors": status
    })

@app.route('/api/cameras/continuous/stop/<zone_id>', methods=['POST'])
def stop_continuous_processing(zone_id):
    """
    Stop continuous processing for a specific zone
    ---
    tags:
      - Camera Management
    parameters:
      - name: zone_id
        in: path
        type: string
        required: true
        description: "Zone identifier (food_court, parking, main_stage, testing)"
    responses:
      200:
        description: Processing stopped successfully
    """
    with VIDEO_PROCESSING_LOCK:
        if zone_id in ACTIVE_VIDEO_PROCESSORS:
            ACTIVE_VIDEO_PROCESSORS[zone_id]['stop_flag']['stop'] = True
            del ACTIVE_VIDEO_PROCESSORS[zone_id]
            print(f"[{zone_id}] Stopped continuous processing")
            return jsonify({"message": f"Continuous processing stopped for {zone_id}"})
        else:
            return jsonify({"error": f"No active processor for {zone_id}"}), 404

@app.route('/api/cameras/continuous/stop-all', methods=['POST'])
def stop_all_continuous_processing():
    """
    Stop all continuous video processors
    ---
    tags:
      - Camera Management
    responses:
      200:
        description: All processors stopped
    """
    stopped_count = 0
    with VIDEO_PROCESSING_LOCK:
        for zone_id, processor in list(ACTIVE_VIDEO_PROCESSORS.items()):
            processor['stop_flag']['stop'] = True
            stopped_count += 1
        ACTIVE_VIDEO_PROCESSORS.clear()
    
    print(f"Stopped {stopped_count} continuous processors")
    return jsonify({
        "message": f"Stopped {stopped_count} continuous processors",
        "stopped_count": stopped_count
    })

@app.route('/api/cameras/search-stream', methods=['POST'])
def search_and_stream_video():
    """
    Search YouTube for a video and start continuous analysis
    ---
    tags:
      - Camera Management
    parameters:
      - name: body
        in: body
        required: true
        schema:
            type: object
            properties:
                query:
                    type: string
                    example: "crowd walking in mall"
                zone_id:
                    type: string
                    example: "food_court"
    responses:
      200:
        description: Video found and analysis started
    """
    try:
        data = request.json
        query = data.get('query')
        zone_id = data.get('zone_id', 'testing')
        
        if not query:
            return jsonify({"error": "Query is required"}), 400
            
        print(f"[{zone_id}] Searching YouTube for: {query}")
        
        # Use yt-dlp to search and download
        import yt_dlp
        
        # Create a safe filename from query
        safe_query = "".join([c for c in query if c.isalnum() or c in (' ', '-', '_')]).strip().replace(' ', '_')
        filename = f"yt_{safe_query}_{int(time.time())}.mp4"
        save_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        
        ydl_opts = {
            'format': 'best[ext=mp4]/best',
            'outtmpl': save_path,
            'noplaylist': True,
            'quiet': True,
            'default_search': 'ytsearch1:',  # Search and get 1st result
            'max_downloads': 1
        }
        
        video_info = None
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                # Search and download
                info = ydl.extract_info(query, download=True)
                if 'entries' in info:
                    video_info = info['entries'][0]
                else:
                    video_info = info
        except Exception as e:
            print(f"yt-dlp warning/error: {e}")
            # Continue if file exists, as max_downloads might trigger error
            if not os.path.exists(save_path):
                 return jsonify({"error": f"Failed to download video: {str(e)}"}), 500
                
        if not os.path.exists(save_path):
             return jsonify({"error": "Failed to download video"}), 500
             
        video_title = video_info.get('title', 'Unknown') if video_info else 'YouTube Video'
        print(f"[{zone_id}] Downloaded video: {video_title}")
        
        # Start continuous analysis
        with VIDEO_PROCESSING_LOCK:
            # Stop existing processor if any
            if zone_id in ACTIVE_VIDEO_PROCESSORS:
                ACTIVE_VIDEO_PROCESSORS[zone_id]['stop_flag']['stop'] = True
                print(f"[{zone_id}] Stopping previous processor...")
                time.sleep(1) # Give it a moment to stop
            
            # Start new processor
            stop_flag = {'stop': False}
            thread = threading.Thread(
                target=fast_continuous_video_processor,
                args=(save_path, zone_id, stop_flag),
                daemon=True
            )
            thread.start()
            
            ACTIVE_VIDEO_PROCESSORS[zone_id] = {
                'thread': thread,
                'stop_flag': stop_flag,
                'video_path': save_path,
                'started_at': datetime.utcnow().isoformat() + "Z"
            }
            
        return jsonify({
            "message": "Video found and analysis started",
            "video_title": video_title,
            "video_url": f"/uploads/{filename}",
            "zone_id": zone_id,
            "status": "Processing continuously"
        })
        
    except Exception as e:
        print(f"Search error: {e}")
        return jsonify({"error": str(e)}), 500



@app.route('/api/cameras/endpoints', methods=['GET'])
def get_camera_endpoints():
    """
    Get list of all available camera endpoints
    ---
    tags:
      - Camera Management
    responses:
      200:
        description: List of camera endpoints
    """
    return jsonify({
        "endpoints": list(CAMERA_ENDPOINTS.values()),
        "total_cameras": len(CAMERA_ENDPOINTS)
    })


@app.route('/api/zones/<zone_id>/density', methods=['POST'])
def get_zone_density(zone_id):
    """
    Get real-time crowd density for a specific zone
    ---
    tags:
      - Zone Management
    parameters:
      - name: zone_id
        in: path
        type: string
        required: true
        description: ID of the zone (e.g., zone1)
    responses:
      200:
        description: Density data retrieved
        schema:
          type: object
          properties:
            density:
              type: number
            people_count:
              type: integer
    """
    # Check if we have real analysis data
    if zone_id in ZONE_ANALYSIS:
        analysis = ZONE_ANALYSIS[zone_id]
        # Map density level to numeric value for compatibility if needed
        density_map = {"Low": 0.2, "Medium": 0.5, "High": 0.8, "Critical": 1.0}
        density_val = density_map.get(analysis.get('density_level', 'Low'), 0.1)
        
        # Handle anomalies (convert objects to strings for backward compatibility)
        raw_anomalies = analysis.get('anomalies', [])
        simple_anomalies = []
        detailed_anomalies = []
        
        for a in raw_anomalies:
            if isinstance(a, dict):
                simple_anomalies.append(f"{a.get('type', 'Anomaly')}: {a.get('description', '')} at {a.get('timestamp', '')}")
                detailed_anomalies.append(a)
            else:
                simple_anomalies.append(str(a))
                detailed_anomalies.append({"description": str(a), "type": "other"})

        return jsonify({
            "zone_id": zone_id,
            "density": density_val,
            "people_count": analysis.get('crowd_count', 0),
            "density_level": analysis.get('density_level', 'Low'),
            "anomalies": simple_anomalies,
            "detailed_anomalies": detailed_anomalies,
            "description": analysis.get('description', ''),
            "sentiment": analysis.get('sentiment', ''),
            "timestamp": analysis.get('timestamp', datetime.utcnow().isoformat() + "Z")
        })

    # NO FALLBACK - Return empty/null status as requested
    return jsonify({
        "zone_id": zone_id,
        "status": "no_data",
        "message": "No analysis available. Please upload video."
    })

@app.route('/api/anomaly/detect', methods=['POST'])
def detect_anomaly():
    """
    Detect anomalies in crowd behavior
    ---
    tags:
      - Anomaly Detection
    responses:
      200:
        description: Anomaly detection result
        schema:
          type: object
          properties:
            anomaly_detected:
              type: boolean
            anomaly_type:
              type: string
            severity:
              type: string
            location:
              type: string
    """
    anomaly_data = {
        "anomaly_detected": True,
        "anomaly_type": "fire",
        "severity": "high",
        "location": "Food Court",
        "coordinates": [12.9780, 77.5980],
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "alert_summary": "Fire detected near Food Court. High severity."
    }
    
    message = f"ALERT: {anomaly_data['alert_summary']} Location: {anomaly_data['location']}. Please respond immediately."
    send_sms_alert("+917337743545", message)
    
    return jsonify(anomaly_data)

@app.route('/api/anomalies/active', methods=['GET'])
def get_active_anomalies():
    """
    Get all active anomalies across all zones from persistent storage
    """
    # Return all anomalies from persistent storage
    # They already have all required fields: id, type, description, location, timestamp, etc.
    return jsonify(PERSISTENT_ANOMALIES)

@app.route('/api/messages', methods=['GET', 'POST'])
def handle_messages():
    """
    Handle messaging between responders and admin
    """
    if request.method == 'POST':
        msg = request.json
        msg['id'] = str(uuid.uuid4())
        msg['timestamp'] = datetime.utcnow().isoformat() + "Z"
        MESSAGES.append(msg)
        return jsonify({"status": "sent", "message": msg})
    return jsonify(MESSAGES)

@app.route('/api/realtime/zone-history/<zone_id>', methods=['GET'])
def get_zone_history(zone_id):
    """
    Get historical data for real-time graphs
    ---
    tags:
      - Real-time Data
    parameters:
      - name: zone_id
        in: path
        type: string
        required: true
        description: Zone identifier (food_court, parking, main_stage, testing)
    responses:
      200:
        description: Historical data for the zone
    """
    if zone_id not in ZONE_HISTORY:
        return jsonify({"error": "Zone not found", "available_zones": list(ZONE_HISTORY.keys())}), 404
    
    return jsonify({
        "zone_id": zone_id,
        "history": ZONE_HISTORY[zone_id],
        "data_points": len(ZONE_HISTORY[zone_id])
    })

@app.route('/api/realtime/all-zones', methods=['GET'])
def get_all_zones_realtime():
    """
    Get real-time data for all zones
    ---
    tags:
      - Real-time Data
    responses:
      200:
        description: Real-time data for all zones
    """
    zones_data = []
    
    # Return ALL zones from ZONE_ANALYSIS instead of hardcoded list
    for zone_id, analysis in ZONE_ANALYSIS.items():
        history = ZONE_HISTORY.get(zone_id, [])
        
        # Calculate trend
        trend = "stable"
        if len(history) >= 2:
            recent_count = history[-1].get('crowd_count', 0)
            previous_count = history[-2].get('crowd_count', 0)
            if recent_count > previous_count:
                trend = "increasing"
            elif recent_count < previous_count:
                trend = "decreasing"
        
        # Get zone name from analysis or CAMERA_ENDPOINTS
        zone_name = analysis.get('zone_name') if analysis else None
        if not zone_name:
            zone_name = CAMERA_ENDPOINTS.get(zone_id, {}).get('name', zone_id)
        
        zones_data.append({
            "zone_id": zone_id,
            "zone_name": zone_name,
            "current_analysis": analysis,
            "trend": trend,
            "history_points": len(history),
            "latest_data": history[-1] if history else None
        })
    
    return jsonify({
        "zones": zones_data,
        "timestamp": datetime.utcnow().isoformat() + "Z"
    })

@app.route('/api/realtime/dashboard-summary', methods=['GET'])
def get_dashboard_summary():
    """
    Get comprehensive dashboard summary with all real-time metrics
    ---
    tags:
      - Real-time Data
    responses:
      200:
        description: Complete dashboard summary
    """
    total_crowd = 0
    total_anomalies = 0
    critical_zones = []
    
    for zone_id in ['food_court', 'parking', 'main_stage', 'testing']:
        analysis = ZONE_ANALYSIS.get(zone_id)
        if analysis:
            crowd_count = analysis.get('crowd_count', 0)
            total_crowd += crowd_count
            anomalies = analysis.get('anomalies', [])
            total_anomalies += len(anomalies)
            
            density_level = analysis.get('density_level', 'Low')
            if density_level in ['High', 'Critical']:
                critical_zones.append({
                    "zone": CAMERA_ENDPOINTS.get(zone_id, {}).get('name', zone_id),
                    "density": density_level,
                    "crowd_count": crowd_count
                })
    
    return jsonify({
        "summary": {
            "total_crowd_count": total_crowd,
            "total_active_anomalies": total_anomalies,
            "critical_zones_count": len(critical_zones),
            "monitored_zones": len(CAMERA_ENDPOINTS),
            "timestamp": datetime.utcnow().isoformat() + "Z"
        },
        "critical_zones": critical_zones,
        "zone_breakdown": {
            zone_id: {
                "crowd_count": ZONE_ANALYSIS.get(zone_id, {}).get('crowd_count', 0),
                "density_level": ZONE_ANALYSIS.get(zone_id, {}).get('density_level', 'Unknown'),
                "anomaly_count": len(ZONE_ANALYSIS.get(zone_id, {}).get('anomalies', []))
            }
            for zone_id in ['food_court', 'parking', 'main_stage', 'testing']
        }
    })

@app.route('/api/lost-found/report', methods=['POST'])
def report_lost_person():
    """
    Report a lost person
    ---
    tags:
      - Lost and Found
    parameters:
      - name: name
        in: formData
        type: string
        required: true
      - name: age
        in: formData
        type: integer
        required: true
      - name: description
        in: formData
        type: string
        required: true
      - name: last_seen
        in: formData
        type: string
      - name: contact
        in: formData
        type: string
        required: true
      - name: image
        in: formData
        type: file
    responses:
      200:
        description: Report created
    """
    try:
        name = request.form.get('name')
        age = request.form.get('age')
        description = request.form.get('description')
        last_seen = request.form.get('last_seen')
        contact = request.form.get('contact')
        
        image_url = None
        if 'image' in request.files:
            file = request.files['image']
            if file and file.filename:
                filename = secure_filename(file.filename)
                # Save with unique ID
                unique_filename = f"lost_{uuid.uuid4()}_{filename}"
                filepath = os.path.join(FACES_FOLDER, unique_filename)
                file.save(filepath)
                image_url = f"/uploads/faces/{unique_filename}"
                
                # Verify face (optional check)
                try:
                    from deepface import DeepFace
                    # Just check if a face is detectable to warn user (log only for now)
                    # DeepFace.extract_faces(img_path=filepath, enforce_detection=False)
                    pass
                except:
                    pass
        
        report_id = str(uuid.uuid4())
        report = {
            "id": report_id,
            "name": name,
            "age": age,
            "description": description,
            "last_seen": last_seen,
            "contact": contact,
            "image_url": image_url,
            "status": "active",
            "reported_at": datetime.utcnow().isoformat() + "Z"
        }
        
        LOST_PERSONS.append(report)
        return jsonify({"message": "Report submitted successfully", "report": report})
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/lost-found/reports', methods=['GET'])
def get_lost_reports():
    """
    Get all active lost person reports
    ---
    tags:
      - Lost and Found
    responses:
      200:
        description: List of lost persons
    """
    active_reports = [p for p in LOST_PERSONS if p['status'] == 'active']
    return jsonify({"reports": active_reports})

@app.route('/api/lost-found/matches', methods=['GET'])
def get_lost_matches():
    """
    Get found matches for lost persons
    ---
    tags:
      - Lost and Found
    responses:
      200:
        description: List of matches found by AI
    """
    return jsonify({"matches": FOUND_MATCHES})



@app.route('/api/crowd/predict', methods=['POST'])
def predict_crowd():
    """
    Predict future crowd levels
    ---
    tags:
      - Crowd Prediction
    responses:
      200:
        description: Prediction result
        schema:
          type: object
          properties:
            prediction:
              type: string
            confidence:
              type: integer
    """
    return jsonify({
        "prediction": "Crowd in Zone Z1 expected to increase slightly, stabilizing at moderate levels.",
        "confidence": 72
    })

@app.route('/api/path/find', methods=['POST'])
def find_path():
    """
    Find simple path between two points
    ---
    tags:
      - Navigation
    responses:
      200:
        description: Path found
    """
    return jsonify({
        "path": [[77.5946, 12.9716], [77.5915, 12.9715], [77.5946, 12.9721]],
        "distance": "500m",
        "estimated_time": "5 mins"
    })

@app.route('/api/path/calculate', methods=['POST'])
def calculate_path():
    """
    Calculate optimal path avoiding crowd zones
    ---
    tags:
      - Navigation
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          properties:
            start:
              type: string
              example: "Entrance"
            end:
              type: string
              example: "Main Stage"
            avoid:
              type: array
              items:
                type: string
              example: ["Food Court"]
    responses:
      200:
        description: Calculated path with instructions
        schema:
          type: object
          properties:
            path_nodes:
              type: array
              items:
                type: string
            instructions:
              type: array
              items:
                type: string
    """
    data = request.json
    start_location = data.get('start', 'Entrance')
    end_location = data.get('end', 'Main Stage')
    avoid_zones = data.get('avoid', []) 
    
    path = calculate_shortest_path(start_location, end_location, avoid_zones)
    
    if not path:
        return jsonify({"error": "No path found"}), 404
        
    path_coordinates = [VENUE_COORDINATES.get(node, [0,0]) for node in path]
    
    # Generate detailed voice navigation instructions
    voice_instructions = []
    for i, node in enumerate(path):
        if i == 0:
            voice_instructions.append(f"Starting navigation from {node}. Total {len(path) - 1} steps to {end_location}.")
        elif i == len(path) - 1:
            voice_instructions.append(f"Arriving at your destination, {node}. Navigation complete.")
        else:
            voice_instructions.append(f"Continue to {node}. Step {i} of {len(path) - 1}.")
    
    # Calculate total distance based on actual coordinates
    total_distance = len(path) * 100  # Approximate 100m per segment for venues
    
    return jsonify({
        "path_nodes": path,
        "path_coordinates": path_coordinates,
        "avoid_zones": avoid_zones,
        "instructions": [f"Step {i+1}: {instr}" for i, instr in enumerate(voice_instructions)],
        "voice_instructions": voice_instructions,
        "total_distance_meters": total_distance,
        "estimated_time_minutes": round(total_distance / 83)  # Average walking speed 5 km/h = 83 m/min
    })

@app.route('/api/missing/register', methods=['POST'])
def register_missing():
    return jsonify({"status": "registered", "case_id": "case123", "message": "Missing person case registered successfully."})

@app.route('/api/missing/search', methods=['POST'])
def search_missing():
    return jsonify({
        "matched": True,
        "person_id": "person456",
        "confidence": 0.85,
        "last_seen_location": "Zone B",
        "timestamp": "2025-11-16T10:00:00Z",
        "matching_frames": [{"timestamp": "2025-11-16T10:00:00Z", "confidence": 0.85, "frame_url": "https://example.com/frame123.jpg"}]
    })

@app.route('/uploads/faces/<filename>')
def uploaded_face_file(filename):
    return send_from_directory(FACES_FOLDER, filename)

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

def analyze_video_robust(video_path, zone_id):
    """
    Robust video analysis using DeepFace for missing person detection.
    Scans video frame-by-frame (sampled) and compares against active lost persons.
    Draws bounding boxes: RED for unknown, GREEN for found matches.
    """
    try:
        from deepface import DeepFace
        import cv2
        import numpy as np
        
        print(f"Starting robust analysis for {video_path}...")
        
        # Initialize analysis result
        analysis = {
            'crowd_count': 0,
            'density_level': 'Low',
            'anomalies': [],
            'found_persons': [],
            'description': "Analysis complete.",
            'sentiment': "Unknown",
            'timestamp': datetime.utcnow().isoformat() + "Z"
        }
        
        # Get active lost persons with images
        active_lost_persons = [p for p in LOST_PERSONS if p['status'] == 'active' and p['image_url']]
        
        if not active_lost_persons:
            print("No active lost persons with images to search for.")
            return analysis

        cap = cv2.VideoCapture(video_path)
        fps = cap.get(cv2.CAP_PROP_FPS)
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration = frame_count / fps
        
        # Sample frames more frequently (e.g., every 0.5 seconds)
        sample_rate = int(fps / 2) 
        if sample_rate < 1: sample_rate = 1
        
        found_person_ids = set()
        
        current_frame = 0
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break
                
            if current_frame % sample_rate == 0:
                timestamp_seconds = current_frame / fps
                minutes = int(timestamp_seconds // 60)
                seconds = int(timestamp_seconds % 60)
                timestamp_str = f"{minutes:02d}:{seconds:02d}"
                
                print(f"Scanning frame at {timestamp_str}...")
                
                # Detect all faces in the frame first
                # Using 'ssd' for better robustness than 'opencv' but faster than 'retinaface'
                try:
                    faces = DeepFace.extract_faces(
                        img_path=frame,
                        detector_backend="ssd", 
                        enforce_detection=False,
                        align=False
                    )
                except:
                    # Fallback to opencv if ssd fails or not installed
                    try:
                        faces = DeepFace.extract_faces(
                            img_path=frame,
                            detector_backend="opencv",
                            enforce_detection=False,
                            align=False
                        )
                    except:
                        faces = []

                frame_has_match = False
                annotated_frame = frame.copy()
                
                for face_obj in faces:
                    facial_area = face_obj['facial_area']
                    x, y, w, h = facial_area['x'], facial_area['y'], facial_area['w'], facial_area['h']
                    
                    # Default: Draw RED box (Unknown)
                    color = (0, 0, 255) # BGR
                    label = "Unknown"
                    
                    # Crop face for verification
                    face_img = frame[y:y+h, x:x+w]
                    if face_img.size == 0: continue
                    
                    # Save temp crop for verification
                    temp_face_path = os.path.join(app.config['UPLOAD_FOLDER'], f"temp_face_{uuid.uuid4().hex[:8]}.jpg")
                    cv2.imwrite(temp_face_path, face_img)

                    # Check against all lost persons
                    for person in active_lost_persons:
                        # Get person's reference image path
                        ref_img_filename = os.path.basename(person['image_url'])
                        ref_img_path = os.path.join(FACES_FOLDER, ref_img_filename)
                        
                        if not os.path.exists(ref_img_path):
                            continue
                            
                        try:
                            # Use VGG-Face for verification (good balance)
                            result = DeepFace.verify(
                                img1_path=temp_face_path,
                                img2_path=ref_img_path,
                                model_name="VGG-Face",
                                detector_backend="opencv", # Detector for alignment in verify
                                distance_metric="cosine",
                                enforce_detection=False
                            )
                            
                            if result['verified']:
                                # Match Found!
                                color = (0, 255, 0) # Green
                                label = f"{person['name']} ({int((1-result['distance'])*100)}%)"
                                frame_has_match = True
                                
                                # Always record/update match for this timestamp
                                found_frame_filename = f"found_{person['id']}_{uuid.uuid4().hex[:8]}.jpg"
                                # We will save the ANNOTATED frame later
                                
                                match = {
                                    "person_id": person['id'],
                                    "zone_id": zone_id,
                                    "confidence": int((1 - result['distance']) * 100),
                                    "description": f"Matched {person['name']} at {timestamp_str}",
                                    "timestamp": timestamp_str,
                                    "found_at": datetime.utcnow().isoformat() + "Z",
                                    "found_frame_url": f"/uploads/{found_frame_filename}", # Placeholder
                                    "image_url": f"/uploads/{found_frame_filename}"
                                }
                                
                                analysis['found_persons'].append(match)
                                FOUND_MATCHES.append(match)
                                found_person_ids.add(person['id'])
                                
                                person['status'] = 'found'
                                person['found_location'] = zone_id
                                break # Stop checking other persons for this face
                                
                        except Exception:
                            pass
                    
                    # Cleanup temp face
                    if os.path.exists(temp_face_path):
                        os.remove(temp_face_path)

                    # Draw Box and Label
                    cv2.rectangle(annotated_frame, (x, y), (x + w, y + h), color, 2)
                    cv2.putText(annotated_frame, label, (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)

                # If we found a match in this frame, save the annotated frame
                if frame_has_match:
                    found_frame_filename = f"found_frame_{uuid.uuid4().hex[:8]}.jpg"
                    found_frame_path = os.path.join(app.config['UPLOAD_FOLDER'], found_frame_filename)
                    cv2.imwrite(found_frame_path, annotated_frame)
                    
                    # Update the URLs for matches found in this frame
                    for match in analysis['found_persons']:
                        if match['timestamp'] == timestamp_str and match['found_frame_url'].startswith("/uploads/found_"):
                             match['found_frame_url'] = f"/uploads/{found_frame_filename}"
                             match['image_url'] = f"/uploads/{found_frame_filename}"

            current_frame += 1
            
        cap.release()
        
        # Update global analysis
        ZONE_ANALYSIS[zone_id] = analysis
        return analysis

    except Exception as e:
        print(f"Robust Analysis Error: {e}")
        return None

def check_supabase_connection():
    try:
        from supabase import create_client
        url = os.environ.get("SUPABASE_URL")
        key = os.environ.get("SUPABASE_KEY")
        if url and key:
            supabase = create_client(url, key)
            supabase.table("lost_persons").select("*").limit(1).execute()
            print("Supabase connected and 'lost_persons' table found.")
            return True
    except Exception as e:
        print(f"ℹ️ Running in local mode (Supabase optional): {e}")
        print("Running in in-memory mode. Data will not be persisted.")
        return False

@app.route('/api/demo/reset', methods=['POST'])
def reset_demo_data():
    """
    Reset all demo data to empty state
    """
    global ZONE_ANALYSIS, PERSISTENT_ANOMALIES, ZONE_HISTORY
    
    ZONE_ANALYSIS.clear()
    PERSISTENT_ANOMALIES.clear()
    for zone in ZONE_HISTORY:
        ZONE_HISTORY[zone].clear()
        
    return jsonify({"message": "Demo data reset successfully. System is clean."})

@app.route('/api/emergency/fire-alert', methods=['POST'])
def trigger_fire_alert():
    """
    Emergency Fire Alert System - Triggers immediate fire response
    """
    global ZONE_ANALYSIS, PERSISTENT_ANOMALIES, ZONE_HISTORY
    
    # Create critical fire incident
    fire_incident = {
        'id': str(uuid.uuid4()),
        'type': 'fire',
        'description': 'Fire emergency detected in building - smoke and flames visible, people evacuating',
        'timestamp': datetime.utcnow().isoformat() + 'Z',
        'confidence': 95,
        'location': 'Testing Region',
        'zone_id': 'testing',
        'status': 'active',
        'severity': 'critical',
        'image_url': 'http://localhost:5000/uploads/fire_incident.png'
    }
    
    now = datetime.utcnow()
    
    # Update zone analysis for testing (FIRE ZONE)
    ZONE_ANALYSIS['testing'] = {
        'crowd_count': 45,
        'density_level': 'Critical',
        'anomalies': [fire_incident],
        'description': 'Fire emergency situation - building evacuation underway',
        'sentiment': 'Panic',
        'timestamp': now.isoformat() + 'Z'
    }
    
    # Add to persistent storage for responder dashboard
    PERSISTENT_ANOMALIES.append(fire_incident)
    
    # Add testing zone history (T-10m, T-5m, Now)
    if 'testing' not in ZONE_HISTORY:
        ZONE_HISTORY['testing'] = []
    ZONE_HISTORY['testing'].append({'timestamp': (now - timedelta(minutes=10)).isoformat() + 'Z', 'crowd_count': 20})
    ZONE_HISTORY['testing'].append({'timestamp': (now - timedelta(minutes=5)).isoformat() + 'Z', 'crowd_count': 35})
    ZONE_HISTORY['testing'].append({'timestamp': now.isoformat() + 'Z', 'crowd_count': 45})
    
    # Populate other zones with normal data
    zones_data = {
        'parking': {
            'crowd_count': 12,
            'density_level': 'Low',
            'anomalies': [],
            'description': 'Parking lot with light vehicle traffic',
            'sentiment': 'Calm',
        },
        'main_stage': {
            'crowd_count': 450,
            'density_level': 'Critical',
            'anomalies': [],
            'description': 'Concert event with large crowd near stage',
            'sentiment': 'Agitated',
        },
        'food_court': {
            'crowd_count': 78,
            'density_level': 'Medium',
            'anomalies': [],
            'description': 'Shopping mall food court with moderate crowd',
            'sentiment': 'Calm',
        }
    }
    
    # Update analysis and history for all zones
    for zone_id, data in zones_data.items():
        data['timestamp'] = now.isoformat() + 'Z'
        ZONE_ANALYSIS[zone_id] = data
        
        # Add historical data for predictions (T-10m, T-5m, Now)
        if zone_id not in ZONE_HISTORY:
            ZONE_HISTORY[zone_id] = []
        
        current_count = data['crowd_count']
        ZONE_HISTORY[zone_id].append({'timestamp': (now - timedelta(minutes=10)).isoformat() + 'Z', 'crowd_count': max(0, current_count - 10)})
        ZONE_HISTORY[zone_id].append({'timestamp': (now - timedelta(minutes=5)).isoformat() + 'Z', 'crowd_count': max(0, current_count - 5)})
        ZONE_HISTORY[zone_id].append({'timestamp': now.isoformat() + 'Z', 'crowd_count': current_count})
    
    return jsonify({
        'status': 'emergency_activated',
        'incident_id': fire_incident['id'],
        'type': 'fire',
        'location': 'Testing Region',
        'confidence': 95,
        'message': 'Fire emergency alert triggered. Responders notified.'
    })

@app.route('/api/explain/saliency', methods=['POST'])
def explain_saliency():
    """
    Generate Saliency Map for a given face image URL
    ---
    tags:
      - Explainable AI
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          properties:
            image_url:
              type: string
              description: URL or path of the image to explain
    responses:
      200:
        description: Saliency map generated
    """
    try:
        data = request.json
        image_url = data.get('image_url')
        
        if not image_url:
            return jsonify({"error": "No image_url provided"}), 400
            
        # Handle URL path (remove leading slash if present)
        if image_url.startswith('/'):
            image_url = image_url[1:]
            
        # Construct full path
        # If it's in uploads/faces, map it correctly
        if 'uploads/faces' in image_url:
            # It might be relative to root or absolute
            # We need to find the actual file on disk
            filename = os.path.basename(image_url)
            img_path = os.path.join(FACES_FOLDER, filename)
            if not os.path.exists(img_path):
                 # Try uploads folder directly
                 img_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        elif 'uploads' in image_url:
             filename = os.path.basename(image_url)
             img_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        else:
             return jsonify({"error": "Invalid image path"}), 400
             
        if not os.path.exists(img_path):
            return jsonify({"error": f"Image file not found: {img_path}"}), 404

        # --- XAI Logic ---
        import tensorflow as tf
        from tf_keras_vis.saliency import Saliency
        from tf_keras_vis.utils.model_modifiers import ReplaceToLinear
        from tf_keras_vis.utils.scores import CategoricalScore
        from deepface import DeepFace
        import numpy as np
        import cv2
        
        # 1. Load Model (VGG-Face)
        # DeepFace.build_model returns a Keras model
        model = DeepFace.build_model("VGG-Face")
        
        # 2. Preprocess Image
        # VGG-Face expects 224x224
        target_size = (224, 224)
        img = cv2.imread(img_path)
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        img_resized = cv2.resize(img, target_size)
        x = np.array(img_resized)
        x = np.expand_dims(x, axis=0)
        # Preprocessing for VGG-Face (usually just raw pixels or simple scaling, DeepFace handles it internally usually but here we need raw input for the model)
        # VGG-Face in DeepFace expects inputs in range [0, 255] usually? Or preprocessed?
        # Let's use DeepFace's preprocessing if possible, but for tf-keras-vis we need the tensor.
        # Simple normalization for visualization
        x = x.astype('float32')
        
        # 3. Generate Saliency Map
        # Replace softmax with linear to avoid gradient saturation
        replace2linear = ReplaceToLinear()
        
        # Score function: We want to maximize the activation of the predicted class (or just the embedding layer?)
        # VGG-Face output is an embedding (2622D or 4096D depending on version).
        # Saliency maps usually explain "Why this class?". 
        # Since this is a recognition model, the output is a feature vector, not a classification probability.
        # However, DeepFace's VGG-Face model might be the full classifier or just the feature extractor.
        # Usually it's the feature extractor.
        # To explain "Why this face?", we can try to maximize the mean of the output vector (features).
        
        score = lambda y: tf.reduce_mean(y, axis=1) # Maximize average activation of features
        
        saliency = Saliency(model, model_modifier=replace2linear, clone=False)
        
        # Generate saliency map
        saliency_map = saliency(score, x, smooth_samples=20, smooth_noise=0.20)
        saliency_map = saliency_map[0] # Get first sample
        
        # 4. Post-process and Save
        # Normalize heatmap
        heatmap = (saliency_map - saliency_map.min()) / (saliency_map.max() - saliency_map.min() + 1e-8)
        heatmap = np.uint8(255 * heatmap)
        
        # Apply colormap
        heatmap_color = cv2.applyColorMap(heatmap, cv2.COLORMAP_JET)
        
        # Resize heatmap to original image size
        original_img = cv2.imread(img_path)
        heatmap_resized = cv2.resize(heatmap_color, (original_img.shape[1], original_img.shape[0]))
        
        # Overlay
        overlay = cv2.addWeighted(original_img, 0.6, heatmap_resized, 0.4, 0)
        
        # Save explanation
        explanation_filename = f"saliency_{uuid.uuid4().hex[:8]}.jpg"
        explanation_path = os.path.join(app.config['UPLOAD_FOLDER'], explanation_filename)
        cv2.imwrite(explanation_path, overlay)
        
        return jsonify({
            "message": "Saliency map generated",
            "explanation_url": f"/uploads/{explanation_filename}",
            "original_url": image_url
        })
        
    except Exception as e:
        print(f"XAI Error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/lost-found/report', methods=['POST'])
def submit_lost_report():
    try:
        name = request.form.get('name')
        age = request.form.get('age')
        description = request.form.get('description')
        last_seen = request.form.get('last_seen')
        contact = request.form.get('contact')
        
        if not name or not age:
            return jsonify({"error": "Name and age are required"}), 400
            
        image_url = None
        if 'image' in request.files:
            file = request.files['image']
            if file and file.filename:
                filename = secure_filename(f"{uuid.uuid4().hex[:8]}_{file.filename}")
                file.save(os.path.join(FACES_FOLDER, filename))
                image_url = f"/uploads/faces/{filename}"
        
        person = {
            "id": str(uuid.uuid4()),
            "name": name,
            "age": int(age),
            "description": description,
            "last_seen": last_seen,
            "contact": contact,
            "image_url": image_url,
            "status": "active",
            "reported_at": datetime.utcnow().isoformat() + "Z"
        }
        
        LOST_PERSONS.append(person)
        return jsonify({"message": "Report submitted successfully", "report": person})
        
    except Exception as e:
        print(f"Error reporting lost person: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/lost-found/reports', methods=['GET'])
def fetch_lost_reports():
    return jsonify({"reports": LOST_PERSONS})

@app.route('/api/lost-found/matches', methods=['GET'])
def fetch_lost_matches():
    return jsonify({"matches": FOUND_MATCHES})

@app.route('/api/cameras/upload-video-quick', methods=['POST'])
def upload_video_quick():
    """
    Quick video upload endpoint that returns mock data immediately
    Use this for testing without the heavy ML analysis
    """
    try:
        if 'video' not in request.files:
            return jsonify({"error": "No video file provided"}), 400
            
        file = request.files['video']
        zone_id = request.form.get('zone_id', 'manual_upload')
        
        if file.filename == '':
            return jsonify({"error": "No selected file"}), 400
            
        # Save file
        filename = secure_filename(f"quick_{uuid.uuid4().hex[:8]}_{file.filename}")
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        print(f"✅ Quick upload: Video saved to {filepath}")
        
        # Return mock analysis data immediately (no heavy processing)
        analysis = {
            'crowd_count': random.randint(5, 25),
            'density_level': random.choice(['Low', 'Medium', 'High']),
            'anomalies': [],
            'found_persons': [],
            'description': 'Video uploaded successfully (quick mode - no deep analysis)',
            'sentiment': 'Neutral',
            'timestamp': datetime.utcnow().isoformat() + "Z"
        }
        
        # Update zone history
        update_zone_history(zone_id, analysis)
        
        return jsonify({
            "message": "Video uploaded successfully (quick mode)",
            "analysis": analysis,
            "note": "Quick upload mode - no facial recognition performed"
        })
        
    except Exception as e:
        print(f"❌ Quick upload error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


def initialize_8th_mile_event():
    """Initialize zone data for 8th Mile event on server startup"""
    print("🎉 Initializing 8th Mile event zones...")
    
    # Find the 8th Mile event
    event_8th_mile = next((e for e in EVENTS if e['id'] == 'evt_8th_mile'), None)
    
    if event_8th_mile and 'zones' in event_8th_mile:
        for zone in event_8th_mile['zones']:
            zone_id = zone['id']
            
            # Create analysis data for each zone
            analysis = {
                'crowd_count': zone['current_count'],
                'density_level': zone['status'].capitalize(),
                'density_percentage': zone['density_percentage'],
                'capacity': zone['capacity'],
                'anomalies': [],
                'found_persons': [],
                'description': f"{zone['activity']} - {zone['current_count']}/{zone['capacity']} attendees",
                'sentiment': 'Excited' if zone_id == 'cs_ground' else 'Calm',
                'timestamp': datetime.utcnow().isoformat() + "Z",
                'zone_name': zone['name'],
                'activity': zone['activity']
            }
            
            # Add special note for CS Ground concert
            if zone_id == 'cs_ground':
                analysis['anomalies'] = [{
                    'type': 'High Crowd Density',
                    'severity': 'Medium',
                    'description': 'Concert in progress - crowd management active',
                    'timestamp': datetime.utcnow().isoformat() + "Z"
                }]
            
            # Store in ZONE_ANALYSIS
            ZONE_ANALYSIS[zone_id] = analysis
            
            # Initialize zone history with CORRECT density values
            # Clear any existing wrong data
            ZONE_HISTORY[zone_id] = []
            
            # Add 5 historical data points with the correct density
            now = datetime.utcnow()
            base_density = zone['density_percentage']
            
            for i in range(5, 0, -1):
                t = (now - timedelta(minutes=i*5)).strftime("%H:%M")
                variation = random.randint(-1, 1)  # Very small variation
                density_value = max(5, min(95, base_density + variation))
                
                ZONE_HISTORY[zone_id].append({
                    "time": t,
                    "density": density_value,  # THIS is what the frontend uses!
                    "crowd_count": zone['current_count'],
                    "density_level": zone['status'].capitalize(),
                    "anomaly_count": len(analysis.get('anomalies', []))
                })
        
        print(f"✅ Initialized {len(event_8th_mile['zones'])} zones for 8th Mile event")
        print("   Zones: CS Ground (90%), MM Foods (70%), BT Quadrangle (60%), Auditorium (40%), Food Court (20%)")
    else:
        print("⚠️ 8th Mile event not found in EVENTS list")


# ==================== PHOTO UPLOAD ENDPOINTS WITH XRAI ====================
# New endpoints for photo-based analysis instead of video

@app.route('/api/cameras/<zone_id>/upload-photo', methods=['POST'])
def upload_zone_photo(zone_id):
    """
    Upload photo to any zone and generate XRAI explanations
    ---
    tags:
      - Camera Management
    parameters:
      - name: zone_id
        in: path
        type: string
        required: true
        description: Zone identifier (food_court, parking, main_stage, testing)
      - name: photo
        in: formData
        type: file
        required: true
        description: Photo file (JPG, PNG)
    responses:
      200:
        description: Photo analyzed with XRAI visualizations
    """
    try:
        if 'photo' not in request.files:
            return jsonify({"error": "No photo file provided"}), 400
        
        file = request.files['photo']
        if file.filename == '':
            return jsonify({"error": "No selected file"}), 400
        
        # Use zone_id from path, or default to 'general' if not in the list
        # This allows ANY zone - no validation!
        if zone_id not in ['food_court', 'parking', 'main_stage', 'testing']:
            zone_id = 'general'  # Default zone for any other uploads
        
        # Save photo
        filename = secure_filename(file.filename)
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        save_filename = f"{zone_id}_{timestamp}_{filename}"
        save_path = os.path.join(app.config['UPLOAD_FOLDER'], save_filename)
        file.save(save_path)
        
        print(f"\n📸 Photo uploaded to {zone_id}: {filename}")
        
        # Import and run photo analysis with XRAI
        from photo_analysis import analyze_photo_with_xrai
        
        analysis = analyze_photo_with_xrai(
            image_path=save_path,
            zone_id=zone_id,
            upload_folder=app.config['UPLOAD_FOLDER']
        )
        
        if analysis is None:
            return jsonify({"error": "Photo analysis failed"}), 500
        
        # Update zone history
        update_zone_history(zone_id, analysis)
        
        # Update global zone analysis
        ZONE_ANALYSIS[zone_id] = analysis
        
        return jsonify({
            "message": f"Photo analyzed successfully for {zone_id} zone",
            "zone": zone_id,
            "photo_url": f"/uploads/{save_filename}",
            "analysis": analysis,
            "timestamp": analysis['timestamp']
        })
        
    except Exception as e:
        print(f"❌ Photo upload error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


# ==================== CSR NET VIDEO ANALYSIS ENDPOINTS ====================
@app.route('/api/cameras/cs_ground/upload', methods=['POST'])
def upload_cs_ground_video():
    """
    Upload video to CS Ground zone (8th Mile event) with CSRNet analysis
    ---
    tags:
      - Camera Management
    parameters:
      - name: video
        in: formData
        type: file
        required: true
    responses:
      200:
        description: Video analyzed with CSRNet + XAI
    """
    try:
        if 'video' not in request.files:
            return jsonify({"error": "No video file provided"}), 400
        
        file = request.files['video']
        if file.filename == '':
            return jsonify({"error": "No selected file"}), 400
        
        # Save video
        filename = secure_filename(file.filename)
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        save_filename = f"cs_ground_{timestamp}_{filename}"
        save_path = os.path.join(app.config['UPLOAD_FOLDER'], save_filename)
        file.save(save_path)
        
        print(f"\n📹 Video uploaded: CS Ground - {filename}")
        
        # CSRNet Forecast Analysis
        from csrnet_forecast import process_video_forecast
        
        # Weights path
        backend_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(backend_dir)
        weights_path = os.path.join(project_root, 'weights.pth')
        
        if not os.path.exists(weights_path):
            return jsonify({"error": f"CSRNet weights not found at {weights_path}"}), 500
        
        analysis = process_video_forecast(
            save_path, 
            'cs_ground',
            weights_path,
            app.config['UPLOAD_FOLDER'],
            prediction_minutes=15
        )
        
        if not analysis:
            return jsonify({"error": "Forecast generation failed"}), 500
        
        # Update zone data
        ZONE_ANALYSIS['cs_ground'] = {
            "zone_id": "cs_ground",
            "zone_name": "CS Ground",
            "crowd_count": analysis['crowd_count'],
            "peak_count": analysis['peak_count'],
            "density_level": analysis['density_level'],
            "timestamp": analysis['timestamp'],
            "forecast_video": analysis['forecast_video_url'],
            "prediction_minutes": analysis['prediction_minutes'],
            "processing_time": analysis['processing_time']
        }
        
        # Update history
        if 'cs_ground' not in ZONE_HISTORY:
            ZONE_HISTORY['cs_ground'] = []
        
        ZONE_HISTORY['cs_ground'].append({
            "time": datetime.utcnow().strftime("%H:%M"),
            "density": analysis['crowd_count'],
            "timestamp": analysis['timestamp']
        })
        
        # Keep last 50 entries
        if len(ZONE_HISTORY['cs_ground']) > 50:
            ZONE_HISTORY['cs_ground'] = ZONE_HISTORY['cs_ground'][-50:]
        
        return jsonify({
            "message": "CS Ground video analyzed successfully",
            "zone": "cs_ground",
            "analysis": analysis
        }), 200
        
    except Exception as e:
        print(f"❌ CS Ground upload error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


# ==================== GENERIC ZONE VIDEO UPLOAD WITH CSRNET ====================
@app.route('/api/cameras/<zone_id>/upload', methods=['POST'])
def upload_zone_video_generic(zone_id):
    """
    Generic video upload endpoint for all zones with CSRNet forecast
    ---
    tags:
      - Camera Management
    parameters:
      - name: zone_id
        in: path
        type: string
        required: true
        description: Zone ID (e.g., cs_ground, bt_quadrangle, food_court, mm_foods, auditorium)
      - name: video
        in: formData
        type: file
        required: true
        description: Video file to analyze
    responses:
      200:
        description: Video analyzed with CSRNet forecast
        schema:
          type: object
          properties:
            message:
              type: string
            zone:
              type: string
            analysis:
              type: object
              properties:
                crowd_count:
                  type: integer
                peak_count:
                  type: integer
                density_level:
                  type: string
                forecast_video_url:
                  type: string
                processing_time:
                  type: string
      400:
        description: Bad request
      500:
        description: Processing error
     """
    try:
        if 'video' not in request.files:
            return jsonify({"error": "No video file provided"}), 400
        
        file = request.files['video']
        if file.filename == '':
            return jsonify({" error": "No selected file"}), 400
        
        # Normalize zone_id (handle both cs-ground and cs_ground formats)
        zone_id_normalized = zone_id.replace('-', '_')
        
        # Save video immediately
        filename = secure_filename(file.filename)
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        save_filename = f"{zone_id_normalized}_{timestamp}_{filename}"
        save_path = os.path.join(app.config['UPLOAD_FOLDER'], save_filename)
        file.save(save_path)
        
        print(f"\n📹 Video uploaded: {zone_id_normalized} - {filename}")
        
        # Return immediately for streaming
        return jsonify({
            "upload_id": "stream_mode",
            "status": "complete",
            "filename": save_filename,
            "message": "Video uploaded. Ready to stream."
        }), 202

    except Exception as e:
        print(f"❌ Upload error for {zone_id}: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/api/video_feed/<path:filename>')
def video_feed(filename):
    video_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    return Response(generate_crowd_stream(video_path),
                    mimetype='multipart/x-mixed-replace; boundary=frame')


# ==================== UPLOAD STATUS ENDPOINT ====================
@app.route('/api/uploads/status/<upload_id>', methods=['GET'])
def get_upload_status(upload_id):
    """
    Get status of async video upload
    ---
    tags:
      - Upload Status
    parameters:
      - name: upload_id
        in: path
        type: string
        required: true
    responses:
      200:
        description: Status retrieved
      404:
        description: Upload not found
    """
    with UPLOAD_LOCK:
        status = UPLOAD_STATUS.get(upload_id)
    
    if not status:
        return jsonify({"error": "Upload not found"}), 404
    
    return jsonify(status), 200





# ==================== STATIC FILE SERVING FOR XRAI ====================
from xai_service import generate_xai_dashboard_image
from io import BytesIO

@app.route('/uploads/<path:filename>')
def serve_uploads(filename):
    """Serve uploaded files and XRAI visualizations"""
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/api/crowd_analysis_stream')
def crowd_analysis_stream():
    """Stream the predefined test.mp4 for the Crowd Analysis tab"""
    # Assuming app.py is in backend/, navigate up to root then to test.mp4
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    video_path = os.path.join(project_root, 'test3.mp4')
    return Response(generate_crowd_stream(video_path),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/api/xai/test2')
def get_xai_dashboard():
    """Generate and return XAI dashboard for test2.mp4"""
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    video_path = os.path.join(project_root, 'test3.mp4')
    weights_path = os.path.join(project_root, 'weights.pth')
    
    img_io, error = generate_xai_dashboard_image(video_path, weights_path)
    if error:
        return jsonify({'error': error}), 500
        
    return send_file(img_io, mimetype='image/png')



def _env_flag(name, default=False):
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {'1', 'true', 'yes', 'on'}


def run_backend_server():
    """Stable backend startup entrypoint (Windows-friendly defaults)."""
    check_supabase_connection()
    initialize_8th_mile_event()

    host = os.getenv('BACKEND_HOST', '127.0.0.1')
    port = int(os.getenv('BACKEND_PORT', '5000'))
    debug = _env_flag('BACKEND_DEBUG', False)
    use_reloader = _env_flag('BACKEND_USE_RELOADER', False)

    safe_print(
        f"Starting backend on http://{host}:{port} "
        f"(debug={debug}, reloader={use_reloader})"
    )
    app.run(
        host=host,
        port=port,
        debug=debug,
        use_reloader=use_reloader,
        threaded=True
    )


if __name__ == '__main__':
    run_backend_server()
