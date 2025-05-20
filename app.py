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

def weighted_rating(rating, num_reviews, discount_factor=0.8, threshold=400):
    """Calculate weighted rating to favor higher review counts."""
    if num_reviews <= threshold:
        return rating * discount_factor
    else:
        weighted_factor = (threshold * discount_factor + (num_reviews - threshold)) / num_reviews
        return rating * weighted_factor

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        zipcode = request.form['zipcode']
        try:
            # Convert zip code to coordinates
            location = geolocator.geocode(f"{zipcode}, USA")
            if not location:
                return render_template('index.html', error="Invalid zip code")
            
            lat, lng = location.latitude, location.longitude

            # Search for restaurants
            places_result = gmaps.places_nearby(
                location=(lat, lng),
                radius=5000,  # 5km radius
                type='restaurant'
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

                # Calculate weighted rating
                weighted_score = weighted_rating(rating, num_reviews) if rating and num_reviews else 0

                restaurants.append({
                    'name': name,
                    'rating': rating,
                    'num_reviews': num_reviews,
                    'weighted_score': weighted_score,
                    'address': address
                })

            # Sort by weighted score (descending)
            restaurants.sort(key=lambda x: x['weighted_score'], reverse=True)

            return render_template('results.html', restaurants=restaurants, zipcode=zipcode)
        
        except Exception as e:
            return render_template('index.html', error=str(e))
    
    return render_template('index.html')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)