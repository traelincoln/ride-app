import os
from flask import Flask, request, jsonify
from flask_cors import CORS
import requests

app = Flask(__name__)

# Configure CORS. In production, replace "*" with your Netlify frontend domain.
# For example: CORS(app, resources={r"/*": {"origins": "https://vin-diesel-hre.netlify.app"}})
# For development/testing, allowing all origins is simpler:
CORS(app)

# Ensure this is set on Heroku: heroku config:set GOOGLE_MAPS_API_KEY="YOUR_BACKEND_DISTANCE_MATRIX_API_KEY"
GOOGLE_MAPS_API_KEY = os.environ.get('GOOGLE_MAPS_API_KEY')
if not GOOGLE_MAPS_API_KEY:
    print("Warning: GOOGLE_MAPS_API_KEY environment variable not set.")
    # You might want to raise an error or use a placeholder in development
    # For a real production app, this should be a critical error.

# Ensure this is set on Heroku: heroku config:set FIXED_ORIGIN="Your Starting Address, City, Country"
FIXED_ORIGIN = os.environ.get('FIXED_ORIGIN')
if not FIXED_ORIGIN:
    print("Warning: FIXED_ORIGIN environment variable not set. Using a default.")
    FIXED_ORIGIN = "Harare, Zimbabwe" # Fallback, but Heroku env var is preferred

@app.route('/book-ride', methods=['POST'])
def book_ride():
    data = request.json
    if not data:
        return jsonify({"error": "Invalid request: No JSON data provided"}), 400

    pickup_location = data.get('pickupLocation')
    primary_destination = data.get('primaryDestination')
    additional_destinations = data.get('additionalDestinations', [])
    
    # Basic validation
    if not all([pickup_location, primary_destination]):
        return jsonify({"error": "Pickup location and primary destination are required."}), 400

    # Construct the list of waypoints for the Distance Matrix API
    # Origin: pickup_location
    # Destinations: primary_destination + additional_destinations
    
    # Google Distance Matrix API URL
    distance_matrix_url = "https://maps.googleapis.com/maps/api/distancematrix/json"

    # All destinations including the primary one
    all_destinations = [primary_destination] + additional_destinations

    params = {
        "origins": pickup_location,
        "destinations": "|".join(all_destinations), # '|' separates multiple destinations
        "key": GOOGLE_MAPS_API_KEY,
        "units": "metric" # For kilometers
    }

    try:
        response = requests.get(distance_matrix_url, params=params)
        response.raise_for_status() # Raise an exception for HTTP errors (4xx or 5xx)
        distance_data = response.json()

        if distance_data.get('status') == 'OK' and distance_data['rows']:
            total_distance_km = 0
            total_duration_minutes = 0

            # Iterate through rows (origins) - should be just one from pickup_location
            for row in distance_data['rows']:
                for element in row['elements']:
                    if element['status'] == 'OK':
                        distance_meters = element['distance']['value'] # in meters
                        duration_seconds = element['duration']['value'] # in seconds

                        total_distance_km += (distance_meters / 1000)
                        total_duration_minutes += (duration_seconds / 60)
                    else:
                        print(f"Element status not OK: {element['status']}")
                        # Handle specific element errors, e.g., NO_RESULTS, ZERO_RESULTS
                        # For simplicity, we'll just skip this element for now
                        pass

            # Simple cost estimation: e.g., $1.50 per km + $0.50 per minute base + fixed fee
            # This is a placeholder; refine your cost logic as needed.
            FIXED_BASE_FARE = 2.00 # Example fixed base fare
            COST_PER_KM = 1.50
            COST_PER_MINUTE = 0.50

            estimated_cost_usd = (total_distance_km * COST_PER_KM) + \
                                 (total_duration_minutes * COST_PER_MINUTE) + \
                                 FIXED_BASE_FARE

            booking_details = {
                "name": data.get('name'),
                "email": data.get('email'),
                "phone": data.get('phone'),
                "pickupLocation": pickup_location,
                "primaryDestination": primary_destination,
                "additionalDestinations": additional_destinations,
                "passengerRequests": data.get('passengerRequests'),
                "total_distance_km": total_distance_km,
                "total_duration_minutes": total_duration_minutes,
                "estimated_cost_usd": estimated_cost_usd,
                "status": "Quote Generated" # Or "Confirmed" if it's a confirmed booking
            }
            return jsonify({"message": "Quote generated successfully!", "booking_details": booking_details}), 200
        else:
            return jsonify({"error": "Could not calculate distance/duration. API status: " + distance_data.get('status', 'Unknown')}), 500

    except requests.exceptions.RequestException as e:
        print(f"Request to Google Maps API failed: {e}")
        return jsonify({"error": "Failed to connect to mapping service for quote. Please try again later."}), 500
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return jsonify({"error": "An internal server error occurred."}), 500

# This block is for local development only. Gunicorn handles running the app on Heroku.
# If you leave app.run() outside this, it can conflict with Gunicorn.
if __name__ == '__main__':
    # When running locally, ensure these are set in your environment
    # or replace os.environ.get with your actual keys for local testing.
    # e.g., os.environ['GOOGLE_MAPS_API_KEY'] = "YOUR_LOCAL_BACKEND_API_KEY"
    # e.g., os.environ['FIXED_ORIGIN'] = "Your Home Address, City, Country"
    # test 2
    app.run(debug=True, port=os.environ.get('PORT', 5000))