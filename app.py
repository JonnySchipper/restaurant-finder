import os
import googlemaps
from flask import Flask, request, render_template
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from geopy.geocoders import Nominatim
from datetime import datetime
from time import mktime
import logging

app = Flask(__name__)

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Initialize Flask-Limiter
limiter = Limiter(
    app,
    key_func=get_remote_address,
    default_limits=["10 per day"],
    storage_uri="memory://"  # Explicitly use in-memory storage
)

# Initialize Google Maps client
API_KEY = os.getenv('GOOGLE_API_KEY')
if not API_KEY:
    logger.error("GOOGLE_API_KEY environment variable not set")
    raise ValueError("GOOGLE_API_KEY environment variable not set")
gmaps = googlemaps.Client(key=API_KEY)

# Initialize geocoder
geolocator = Nominatim(user_agent="restaurant_finder")

def calculate_score(rating: float, review_count: int) -> float:
    """Calculate a score that reduces the value of the first 200 reviews and rewards higher counts."""
    try:
        if review_count <= 200:
            score = rating * (review_count / 200)
        else:
            excess_reviews = review_count - 200
            bonus = excess_reviews * 0.001
            score = rating + min(bonus, 1.0)
        return round(score, 2)
    except Exception as e:
        logger.error(f"Error calculating score: {e}")
        return 0.0

def get_remaining_queries():
    """Get the number of remaining queries for the current user's IP for today."""
    try:
        ip = get_remote_address()
        limit_key = f"{ip}:/:10 per day"
        storage = limiter.limiter.storage
        window = int(mktime(datetime.now().replace(hour=0, minute=0, second=0, microsecond=0).timetuple()))
        count = storage.get(f"{limit_key}:{window}")
        count = int(count) if count is not None else 0
        remaining = max(0, 10 - count)
        logger.info(f"IP {ip}: {count} queries used, {remaining} remaining")
        return remaining
    except Exception as e:
        logger.error(f"Error getting remaining queries: {e}")
        return 10  # Fallback to 10

@app.route('/', methods=['GET', 'POST'])
@limiter.limit("10 per day")
def index():
    remaining_queries = get_remaining_queries()
    
    if request.method == 'POST':
        zipcode = request.form.get('zipcode')
        searchquery = request.form.get('searchQuery', '').strip().lower()
        distance = request.form.get('distance', '10')
        
        if not zipcode or not searchquery:
            logger.warning("Missing zipcode or searchQuery")
            return render_template('index.html', error="Please provide both a zip code and search query", remaining_queries=remaining_queries)
        
        try:
            radius = int(float(distance) * 1609.34)
            logger.info(f"Processing search: zipcode={zipcode}, query={searchquery}, radius={radius}")
            
            location = geolocator.geocode(f"{zipcode}, USA")
            if not location:
                logger.warning(f"Geocoding failed for {zipcode}")
                return render_template('index.html', error="Invalid zip code or location", remaining_queries=remaining_queries)

            lat, lng = location.latitude, location.longitude
            query = f"{searchquery} restaurants"
            
            places_result = gmaps.places(
                query=query,
                location=(lat, lng),
                radius=radius,
                type='restaurant'
            )
            
            restaurants = []
            for place in places_result.get('results', []):
                try:
                    place_id = place['place_id']
                    details = gmaps.place(place_id=place_id, fields=['name', 'rating', 'user_ratings_total', 'formatted_address'])
                    result = details['result']
                    
                    name = result.get('name', 'Unknown')
                    rating = result.get('rating', 0)
                    num_reviews = result.get('user_ratings_total', 0)
                    address = result.get('formatted_address', 'No address available')
                    score = calculate_score(rating, num_reviews)
                    
                    restaurants.append({
                        'name': name,
                        'rating': rating,
                        'num_reviews': num_reviews,
                        'weighted_score': score,
                        'address': address
                    })
                except Exception as e:
                    logger.error(f"Error processing place {place.get('name', 'unknown')}: {e}")
                    continue
            
            restaurants.sort(key=lambda x: x['weighted_score'], reverse=True)
            logger.info(f"Found {len(restaurants)} restaurants")
            
            return render_template('results.html', restaurants=restaurants, zipcode=zipcode, searchquery=searchquery, radius=distance)
        
        except Exception as e:
            logger.error(f"Search error: {e}")
            return render_template('index.html', error=f"Search failed: {str(e)}", remaining_queries=remaining_queries)
    
    return render_template('index.html', remaining_queries=remaining_queries)

@app.errorhandler(429)
def ratelimit_handler(e):
    remaining_queries = get_remaining_queries()
    logger.warning("Rate limit exceeded for IP %s", get_remote_address())
    return render_template('index.html', error="You've reached the daily search limit (10 searches). Please try again tomorrow.", remaining_queries=remaining_queries), 429

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)