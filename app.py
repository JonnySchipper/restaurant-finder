import os
import googlemaps
from flask import Flask, request, render_template
from geopy.geocoders import Nominatim

app = Flask(__name__)

# Initialize Google Maps client
API_KEY = os.getenv('GOOGLE_API_KEY')
gmaps = googlemaps.Client(key=API_KEY)

# Initialize geocoder
geolocator = Nominatim(user_agent="restaurant_finder")

def calculate_score(rating: float, review_count: int) -> float:
    """Calculate a score that reduces the value of the first 200 reviews and rewards higher counts."""
    if review_count <= 200:
        score = rating * (review_count / 200)
    else:
        excess_reviews = review_count - 200
        bonus = excess_reviews * 0.001
        score = rating + min(bonus, 1.0)
    return round(score, 2)

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        zipcode = request.form['zipcode']
        searchquery = request.form.get('searchquery', 'restaurant')  # Default to 'restaurant' if not provided
        radius = request.form.get('radius', 4.35)  # Default to 4.35 miles (~7000 meters) if not provided
        try:
            # Convert radius to meters (1 mile = 1609.34 meters)
            radius = int(float(radius) * 1609.34)

            # Convert zip code to coordinates
            location = geolocator.geocode(f"{zipcode}, USA")
            if not location:
                return render_template('index.html', error="Invalid zip code")
            
            lat, lng = location.latitude, location.longitude

            # Search for places based on query
            places_result = gmaps.places_nearby(
                location=(lat, lng),
                radius=radius,  # Use the user-provided radius
                keyword=searchquery  # Use the search query
            )

            restaurants = []
            for place in places_result.get('results', []):
                # Get detailed place info
                place_id = place['place_id']
                details = gmaps.place(place_id=place_id, fields=['name', 'rating', 'user_ratings_total', 'formatted_address'])
                result = details['result']
                
                name = result.get('name', 'Unknown')
                rating = result.get('rating', 0)
                num_reviews = result.get('user_ratings_total', 0)
                address = result.get('formatted_address', 'No address available')

                # Calculate score using new function
                score = calculate_score(rating, num_reviews) if rating and num_reviews else 0

                restaurants.append({
                    'name': name,
                    'rating': rating,
                    'num_reviews': num_reviews,
                    'weighted_score': score,
                    'address': address
                })

            # Sort by score (descending)
            restaurants.sort(key=lambda x: x['weighted_score'], reverse=True)

            return render_template('results.html', restaurants=restaurants, zipcode=zipcode, searchquery=searchquery, radius=radius)
        
        except Exception as e:
            return render_template('index.html', error=str(e))
    
    return render_template('index.html')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
