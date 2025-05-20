import os
import time
import googlemaps
from flask import Flask, request, render_template

app = Flask(__name__)

# Initialize Google Maps client
API_KEY = os.getenv('GOOGLE_API_KEY')
gmaps = googlemaps.Client(key=API_KEY)

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
        query = request.form['query']
        try:
            # Search for restaurants using text search
            places_result = gmaps.places(query=query, type='restaurant')
            
            restaurants = []
            # Process initial page
            for place in places_result.get('results', []):
                place_id = place['place_id']
                # Fetch detailed place info
                details = gmaps.place(place_id=place_id, fields=[
                    'name', 'rating', 'user_ratings_total', 'formatted_address',
                    'website', 'formatted_phone_number'
                ])
                result = details['result']
                
                name = result.get('name', 'Unknown')
                rating = result.get('rating', 0)
                num_reviews = result.get('user_ratings_total', 0)
                address = result.get('formatted_address', 'No address available')
                website = result.get('website', 'N/A')
                phone = result.get('formatted_phone_number', 'N/A')

                # Calculate score
                score = calculate_score(rating, num_reviews) if rating and num_reviews else 0

                restaurants.append({
                    'name': name,
                    'rating': rating,
                    'num_reviews': num_reviews,
                    'weighted_score': score,
                    'address': address,
                    'website': website,
                    'phone': phone
                })

            # Handle pagination (up to 60 results)
            while 'next_page_token' in places_result and len(restaurants) < 60:
                next_page_token = places_result['next_page_token']
                time.sleep(2)  # Wait for next page to be available
                places_result = gmaps.places(
                    query=query,
                    type='restaurant',
                    page_token=next_page_token
                )
                
                for place in places_result.get('results', []):
                    place_id = place['place_id']
                    details = gmaps.place(place_id=place_id, fields=[
                        'name', 'rating', 'user_ratings_total', 'formatted_address',
                        'website', 'formatted_phone_number'
                    ])
                    result = details['result']
                    
                    name = result.get('name', 'Unknown')
                    rating = result.get('rating', 0)
                    num_reviews = result.get('user_ratings_total', 0)
                    address = result.get('formatted_address', 'No address available')
                    website = result.get('website', 'N/A')
                    phone = result.get('formatted_phone_number', 'N/A')

                    score = calculate_score(rating, num_reviews) if rating and num_reviews else 0

                    restaurants.append({
                        'name': name,
                        'rating': rating,
                        'num_reviews': num_reviews,
                        'weighted_score': score,
                        'address': address,
                        'website': website,
                        'phone': phone
                    })

            # Sort by score (descending)
            restaurants.sort(key=lambda x: x['weighted_score'], reverse=True)

            # Limit to top 20 restaurants
            restaurants = restaurants[:20]

            return render_template('results.html', restaurants=restaurants, query=query)
        
        except Exception as e:
            return render_template('index.html', error=str(e))
    
    return render_template('index.html')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
