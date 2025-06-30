# app.py
from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import os

app = Flask(__name__)
# Configure CORS to allow requests from your frontend (replace '*' with your frontend URL in production)
CORS(app, resources={r"/book-ride": {"origins": "https://vin-diesel-hre.netlify.app/"}})

# --- Configuration ---
# IMPORTANT: Replace 'YOUR_FIXED_ORIGIN_ADDRESS' with your actual starting location (e.g., your home address or garage)
FIXED_ORIGIN = os.environ.get('FIXED_ORIGIN', 'Harare, Zimbabwe') # Fallback if not set as env var
GOOGLE_MAPS_API_KEY = os.environ.get('GOOGLE_MAPS_API_KEY') # Get API key from environment variable

# Cost calculation parameters (adjust as needed)
# Example: Base fare + cost per km + cost per minute
BASE_FARE_USD = 2.00
COST_PER_KM_USD = 0.50
COST_PER_MINUTE_USD = 0.20

# --- Helper Function for Google Maps Distance Matrix API ---
def get_distance_and_duration(origin, destination):
    if not GOOGLE_MAPS_API_KEY:
        print("Error: GOOGLE_MAPS_API_KEY environment variable not set.")
        return None, None, "API key not configured on backend."

    # Google Maps Distance Matrix API endpoint
    api_url = "https://maps.googleapis.com/maps/api/distancematrix/json"
    
    params = {
        "origins": origin,
        "destinations": destination,
        "key": GOOGLE_MAPS_API_KEY,
        "units": "metric" # Request results in metric (kilometers)
    }

    try:
        response = requests.get(api_url, params=params)
        response.raise_for_status() # Raise an exception for HTTP errors (4xx or 5xx)
        data = response.json()

        if data["status"] == "OK" and data["rows"] and data["rows"][0]["elements"]:
            element = data["rows"][0]["elements"][0]
            if element["status"] == "OK":
                distance_meters = element["distance"]["value"]
                duration_seconds = element["duration"]["value"]
                
                # Convert to kilometers and minutes
                distance_km = distance_meters / 1000
                duration_minutes = duration_seconds / 60
                
                return distance_km, duration_minutes, None
            else:
                return None, None, f"Distance Matrix API element status: {element['status']}"
        else:
            return None, None, f"Distance Matrix API status: {data['status']}"

    except requests.exceptions.RequestException as e:
        return None, None, f"Network or API request error: {e}"
    except ValueError:
        return None, None, "Failed to parse API response as JSON."
    except Exception as e:
        return None, None, f"An unexpected error occurred: {e}"

# --- Cost Calculation Function ---
def calculate_cost(total_distance_km, total_duration_minutes):
    cost = BASE_FARE_USD + \
           (total_distance_km * COST_PER_KM_USD) + \
           (total_duration_minutes * COST_PER_MINUTE_USD)
    return round(cost, 2) # Round to two decimal places for currency

# --- API Endpoint for Ride Booking ---
@app.route('/book-ride', methods=['POST'])
def book_ride():
    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid JSON data"}), 400

    # Extract data from the request
    name = data.get('name')
    email = data.get('email')
    phone = data.get('phone')
    pickup_location = data.get('pickupLocation')
    primary_destination = data.get('primaryDestination')
    additional_destinations = data.get('additionalDestinations', [])
    passenger_requests = data.get('passengerRequests')

    if not all([name, email, phone, pickup_location, primary_destination]):
        return jsonify({"error": "Missing required fields (name, email, phone, pickupLocation, primaryDestination)"}), 400

    total_distance_km = 0
    total_duration_minutes = 0
    calculated_legs = []

    # Leg 1: Fixed Origin to Pickup Location
    dist, dur, err = get_distance_and_duration(FIXED_ORIGIN, pickup_location)
    if err:
        return jsonify({"error": f"Error calculating distance to pickup: {err}"}), 500
    
    total_distance_km += dist
    total_duration_minutes += dur
    calculated_legs.append({
        "from": FIXED_ORIGIN,
        "to": pickup_location,
        "distance_km": round(dist, 2),
        "duration_minutes": round(dur, 2)
    })
    
    current_origin_for_next_leg = pickup_location

    # Leg 2: Pickup Location to Primary Destination
    dist, dur, err = get_distance_and_duration(current_origin_for_next_leg, primary_destination)
    if err:
        return jsonify({"error": f"Error calculating distance to primary destination: {err}"}), 500
    
    total_distance_km += dist
    total_duration_minutes += dur
    calculated_legs.append({
        "from": current_origin_for_next_leg,
        "to": primary_destination,
        "distance_km": round(dist, 2),
        "duration_minutes": round(dur, 2)
    })
    current_origin_for_next_leg = primary_destination

    # Subsequent Legs: Between Additional Destinations
    for dest in additional_destinations:
        dist, dur, err = get_distance_and_duration(current_origin_for_next_leg, dest)
        if err:
            return jsonify({"error": f"Error calculating distance for additional destination '{dest}': {err}"}), 500
        
        total_distance_km += dist
        total_duration_minutes += dur
        calculated_legs.append({
            "from": current_origin_for_next_leg,
            "to": dest,
            "distance_km": round(dist, 2),
            "duration_minutes": round(dur, 2)
        })
        current_origin_for_next_leg = dest # Update origin for the next leg

    # Calculate total cost
    total_cost = calculate_cost(total_distance_km, total_duration_minutes)

    response_data = {
        "message": "Ride booking request received and processed!",
        "booking_details": {
            "name": name,
            "email": email,
            "phone": phone,
            "pickupLocation": pickup_location,
            "primaryDestination": primary_destination,
            "additionalDestinations": additional_destinations,
            "passengerRequests": passenger_requests,
            "total_distance_km": round(total_distance_km, 2),
            "total_duration_minutes": round(total_duration_minutes, 2),
            "estimated_cost_usd": total_cost,
            "calculated_legs": calculated_legs
        }
    }

    return jsonify(response_data), 200

if __name__ == '__main__':
    # For local development: run on http://127.0.0.1:5000/
    # In production, use a WSGI server like Gunicorn
    app.run(debug=True, port=5000)
