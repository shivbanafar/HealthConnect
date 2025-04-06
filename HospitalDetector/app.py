import streamlit as st
import pandas as pd
import numpy as np
import requests
import json
import folium
from folium.plugins import MarkerCluster
from streamlit_folium import folium_static
from geopy.distance import geodesic
import urllib.parse
import os
import time
import re
import polyline

# Set page configuration
st.set_page_config(
    page_title="Hospital Route Finder - India",
    page_icon="🏥",
    layout="wide"
)

# Application title and description
st.title("🏥 Hospital Route Finder - India")
st.markdown("""
This application helps find the nearest hospital within one hour of travel time, considering real-time traffic conditions and speed limits.
Simply select a location on the map or enter an address, and the app will search for hospitals and calculate routes.
""")

# Define constants
RADIUS_KM = 25  # Search radius in kilometers (increased to find hospitals within 1-hour travel time)
RADIUS_METERS = RADIUS_KM * 1000  # Convert to kilometers for Google API
MAX_RESULTS = 20  # Maximum number of results to return per API call
MAX_TRAVEL_TIME_SECONDS = 3600  # 1 hour in seconds

# API Key - Using Streamlit secrets
API_KEY = st.secrets["api_key"]

# Utility functions
def format_address(address_components):
    """Format address components into a readable string"""
    if not address_components:
        return "Address not available"
    
    formatted = []
    for component in address_components:
        if 'long_name' in component:
            formatted.append(component['long_name'])
    
    return ", ".join(formatted)

def get_hospital_details(place_id, api_key):
    """Get hospital details using place_id"""
    url = f"https://maps.googleapis.com/maps/api/place/details/json?place_id={place_id}&fields=name,formatted_address,formatted_phone_number,website,rating,user_ratings_total,types&key={api_key}"
    try:
        response = requests.get(url)
        data = response.json()
        
        if data["status"] == "OK":
            return data["result"]
    except Exception as e:
        st.error(f"Error fetching hospital details: {e}")
    
    return None

def geocode_address(address, api_key):
    """Convert address to geographic coordinates using Google Geocoding API"""
    url = f"https://maps.googleapis.com/maps/api/geocode/json?address={urllib.parse.quote(address)}&key={api_key}&region=in"
    
    try:
        response = requests.get(url)
        data = response.json()
        
        if data["status"] == "OK":
            location = data["results"][0]["geometry"]["location"]
            formatted_address = data["results"][0]["formatted_address"]
            return location["lat"], location["lng"], formatted_address
        else:
            st.error(f"Geocoding error: {data['status']}")
            return None, None, None
    except Exception as e:
        st.error(f"Error geocoding address: {e}")
        return None, None, None

def search_hospitals_google(lat, lng, api_key):
    """Search for hospitals using Google Places API"""
    hospitals = []
    page_token = None
    
    # Make initial and follow-up requests with pagetoken if available
    for _ in range(3):  # Limit to 3 pages of results (60 places maximum)
        if page_token:
            url = f"https://maps.googleapis.com/maps/api/place/nearbysearch/json?pagetoken={page_token}&key={api_key}"
        else:
            url = (
                f"https://maps.googleapis.com/maps/api/place/nearbysearch/json?"
                f"location={lat},{lng}&radius={RADIUS_METERS}&type=hospital&key={api_key}"
            )
        
        try:
            response = requests.get(url)
            data = response.json()
            
            if data["status"] == "OK":
                hospitals.extend(data["results"])
                
                if "next_page_token" in data:
                    page_token = data["next_page_token"]
                    # Need to wait a bit before using the page token
                    time.sleep(2)
                else:
                    break
            else:
                st.warning(f"Google Places API error: {data.get('status')}")
                break
        except Exception as e:
            st.error(f"Error searching hospitals: {e}")
            break
    
    return hospitals

def is_multispeciality_hospital(hospital):
    """Check if a hospital is likely a multispeciality hospital based on its name and ratings"""
    # Check for keywords in the name
    name = hospital.get('name', '').lower()
    multispeciality_keywords = ['multi', 'general', 'district', 'medical center', 'medical college', 
                              'aiims', 'government', 'state', 'university', 'memorial']
    
    for keyword in multispeciality_keywords:
        if keyword in name:
            return True
    
    # Consider hospitals with high ratings and many reviews as likely multispeciality
    rating = hospital.get('rating', 0)
    user_ratings_total = hospital.get('user_ratings_total', 0)
    
    if rating >= 4.0 and user_ratings_total >= 50:
        return True
    
    return False

def has_ample_emergency_services(hospital):
    """Check if a hospital likely has ample emergency services based on name and other attributes"""
    # Check for keywords in the name
    name = hospital.get('name', '').lower()
    emergency_keywords = ['emergency', 'trauma', 'accident', 'emergency care', '24 hour', '24/7',
                         'critical care', 'casualty', 'emergency department']
    
    for keyword in emergency_keywords:
        if keyword in name:
            return True
    
    # Look for emergency-related types in the hospital data
    types = hospital.get('types', [])
    emergency_types = ['emergency_room', 'emergency_service', 'trauma_center']
    
    for type_name in emergency_types:
        if type_name in types:
            return True
    
    # Larger, higher-rated hospitals are more likely to have ample emergency services
    rating = hospital.get('rating', 0)
    user_ratings_total = hospital.get('user_ratings_total', 0)
    
    # Very high-rated hospitals with many reviews likely have emergency services
    if rating >= 4.5 and user_ratings_total >= 100:
        return True
    
    return False

def get_travel_time_with_traffic(origin_lat, origin_lng, dest_lat, dest_lng, api_key):
    """Get travel time considering traffic using Google Maps Routes API"""
    url = "https://routes.googleapis.com/directions/v2:computeRoutes"
    headers = {
        'Content-Type': 'application/json',
        'X-Goog-Api-Key': api_key,
        'X-Goog-FieldMask': 'routes.duration,routes.distanceMeters,routes.polyline.encodedPolyline'
    }
    
    data = {
        "origin": {
            "location": {
                "latLng": {
                    "latitude": origin_lat,
                    "longitude": origin_lng
                }
            }
        },
        "destination": {
            "location": {
                "latLng": {
                    "latitude": dest_lat,
                    "longitude": dest_lng
                }
            }
        },
        "travelMode": "DRIVE",
        "routingPreference": "TRAFFIC_AWARE",
        "computeAlternativeRoutes": False,
        "routeModifiers": {
            "avoidTolls": False,
            "avoidHighways": False,
            "avoidFerries": False
        }
    }
    
    try:
        response = requests.post(url, headers=headers, data=json.dumps(data))
        result = response.json()
        
        if "routes" in result and len(result["routes"]) > 0:
            route = result["routes"][0]
            duration_seconds = int(route.get("duration", "").replace("s", ""))
            distance_meters = route.get("distanceMeters", 0)
            polyline_str = route.get("polyline", {}).get("encodedPolyline", "")
            
            return {
                "duration_seconds": duration_seconds,
                "distance_meters": distance_meters,
                "polyline": polyline_str
            }
    except Exception as e:
        st.error(f"Error getting travel time: {e}")
    
    return None

def get_speed_limits(path_points, api_key):
    """Get speed limits using Google Roads API"""
    # Convert path points to string format
    path_string = "|".join([f"{lat},{lng}" for lat, lng in path_points])
    
    url = f"https://roads.googleapis.com/v1/speedLimits?path={path_string}&key={api_key}"
    
    try:
        response = requests.get(url)
        data = response.json()
        
        if "speedLimits" in data:
            return data["speedLimits"]
    except Exception as e:
        st.error(f"Error getting speed limits: {e}")
    
    return []

def decode_polyline(encoded_polyline):
    """Decode Google's encoded polyline format"""
    points = polyline.decode(encoded_polyline)
    return [(point[0], point[1]) for point in points]

def find_hospitals_within_travel_time(origin_lat, origin_lng, hospitals, api_key, max_travel_time=MAX_TRAVEL_TIME_SECONDS):
    """Find hospitals that are reachable within the specified travel time"""
    reachable_hospitals = []
    
    with st.spinner("Calculating travel times to hospitals..."):
        # Calculate travel time for each hospital
        for hospital in hospitals:
            try:
                lat = hospital.get('geometry', {}).get('location', {}).get('lat')
                lng = hospital.get('geometry', {}).get('location', {}).get('lng')
                
                if lat and lng:
                    travel_info = get_travel_time_with_traffic(origin_lat, origin_lng, lat, lng, api_key)
                    
                    if travel_info and travel_info["duration_seconds"] <= max_travel_time:
                        # Add travel information to the hospital data
                        hospital["travel_info"] = travel_info
                        hospital["is_multispeciality"] = is_multispeciality_hospital(hospital)
                        hospital["has_emergency"] = has_ample_emergency_services(hospital)
                        reachable_hospitals.append(hospital)
            except Exception as e:
                st.error(f"Error processing hospital {hospital.get('name', 'Unknown')}: {e}")
    
    # Sort by travel time
    reachable_hospitals.sort(key=lambda x: x.get("travel_info", {}).get("duration_seconds", float('inf')))
    
    return reachable_hospitals

def format_travel_time(seconds):
    """Format seconds into a readable travel time string"""
    if seconds < 60:
        return f"{seconds} seconds"
    elif seconds < 3600:
        minutes = seconds // 60
        return f"{minutes} minute{'s' if minutes != 1 else ''}"
    else:
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        if minutes == 0:
            return f"{hours} hour{'s' if hours != 1 else ''}"
        return f"{hours} hour{'s' if hours != 1 else ''} and {minutes} minute{'s' if minutes != 1 else ''}"

def create_route_map(center_lat, center_lng, selected_hospital, radius_km=RADIUS_KM):
    """Create a folium map with the route to the selected hospital"""
    # Create base map centered on selected location
    m = folium.Map(location=[center_lat, center_lng], zoom_start=12)
    
    # Add a marker for the selected location
    folium.Marker(
        location=[center_lat, center_lng],
        popup="Your Location",
        tooltip="Your Location",
        icon=folium.Icon(color='red', icon='home', prefix='fa')
    ).add_to(m)
    
    # Add hospital marker
    lat = selected_hospital.get('geometry', {}).get('location', {}).get('lat')
    lng = selected_hospital.get('geometry', {}).get('location', {}).get('lng')
    name = selected_hospital.get('name', 'Unknown Hospital')
    
    travel_info = selected_hospital.get('travel_info', {})
    duration_seconds = travel_info.get('duration_seconds', 0)
    distance_meters = travel_info.get('distance_meters', 0)
    
    # Format travel information for popup
    travel_time_str = format_travel_time(duration_seconds)
    distance_km = distance_meters / 1000
    
    popup_html = f"""
    <div style="width: 200px">
        <b>{name}</b><br>
        Travel Time: {travel_time_str}<br>
        Distance: {distance_km:.2f} km
    </div>
    """
    
    # Determine icon based on hospital type
    color = 'green'
    icon_name = 'plus-square'
    
    # Highlight multispeciality hospitals in dark blue
    if selected_hospital.get('is_multispeciality', False):
        color = 'darkblue'
    
    # Highlight hospitals with emergency services in red
    if selected_hospital.get('has_emergency', False):
        color = 'red'
        icon_name = 'ambulance'
    
    folium.Marker(
        location=[lat, lng],
        popup=folium.Popup(popup_html, max_width=300),
        tooltip=name,
        icon=folium.Icon(color=color, icon=icon_name, prefix='fa')
    ).add_to(m)
    
    # Add the route polyline if available
    if "polyline" in travel_info:
        encoded_polyline = travel_info["polyline"]
        points = decode_polyline(encoded_polyline)
        
        folium.PolyLine(
            points,
            color="blue",
            weight=5,
            opacity=0.7,
            tooltip=f"Travel Time: {travel_time_str}"
        ).add_to(m)
    
    return m

def create_hospitals_map(center_lat, center_lng, hospitals, radius_km=RADIUS_KM):
    """Create a folium map with hospital markers and radius circle"""
    # Create base map centered on selected location
    m = folium.Map(location=[center_lat, center_lng], zoom_start=12)
    
    # Add a circle representing the search radius
    folium.Circle(
        location=[center_lat, center_lng],
        radius=radius_km * 1000,  # Convert km to meters
        color='blue',
        fill=True,
        fill_opacity=0.1
    ).add_to(m)
    
    # Add a marker for the selected location
    folium.Marker(
        location=[center_lat, center_lng],
        popup="Your Location",
        tooltip="Your Location",
        icon=folium.Icon(color='red', icon='home', prefix='fa')
    ).add_to(m)
    
    # Create a marker cluster for hospitals
    marker_cluster = MarkerCluster().add_to(m)
    
    # Add hospital markers
    for hospital in hospitals:
        try:
            lat = hospital.get('geometry', {}).get('location', {}).get('lat')
            lng = hospital.get('geometry', {}).get('location', {}).get('lng')
            name = hospital.get('name', 'Unknown Hospital')
            rating = hospital.get('rating', 'No rating')
            vicinity = hospital.get('vicinity', 'Address not available')
            
            if lat and lng:
                # Get travel information
                travel_info = hospital.get('travel_info', {})
                duration_seconds = travel_info.get('duration_seconds', 0)
                distance_meters = travel_info.get('distance_meters', 0)
                
                # Format travel information for popup
                travel_time_str = format_travel_time(duration_seconds)
                distance_km = distance_meters / 1000
                
                # Determine marker color based on hospital type
                color = 'green'
                icon_name = 'plus-square'
                
                # Highlight multispeciality hospitals in dark blue
                if hospital.get('is_multispeciality', False):
                    color = 'darkblue'
                
                # Highlight hospitals with emergency services in red
                if hospital.get('has_emergency', False):
                    color = 'red'
                    icon_name = 'ambulance'  # Use ambulance icon for emergency hospitals
                
                # Customize popup content
                popup_html = f"""
                <div style="width: 220px">
                    <b>{name}</b><br>
                    Rating: {rating}/5<br>
                    Address: {vicinity}<br>
                    Distance: {distance_km:.2f} km<br>
                    Travel Time: {travel_time_str}
                    {"<br><b>Multispeciality Hospital</b>" if hospital.get('is_multispeciality', False) else ""}
                    {"<br><b style='color: red;'>✚ Ample Emergency Services</b>" if hospital.get('has_emergency', False) else ""}
                </div>
                """
                
                folium.Marker(
                    location=[lat, lng],
                    popup=folium.Popup(popup_html, max_width=300),
                    tooltip=name,
                    icon=folium.Icon(color=color, icon=icon_name, prefix='fa')
                ).add_to(marker_cluster)
        except Exception as e:
            st.error(f"Error adding marker: {e}")
    
    return m

# Sidebar for configuration
with st.sidebar:
    st.header("Configuration")
    
    # API key information
    st.info(
        "This application requires Google API keys with access to:"
        "\n- Google Places API"
        "\n- Google Maps Routes API"
        "\n- Google Roads API"
        "\n- Google Geocoding API"
    )
    
    # Sample locations
    st.subheader("Sample Locations")
    sample_location = st.selectbox(
        "Select a sample location",
        [
            "Custom Input",
            "Gurgaon, Haryana",
            "Ahmedabad, Gujarat",
            "Vijayawada, Andhra Pradesh",
            "Siliguri, West Bengal",
            "Kochi, Kerala"
        ]
    )
    
    if sample_location != "Custom Input":
        use_sample = st.checkbox("Use this sample location", value=False)
    
    # Search radius setting
    st.subheader("Search Settings")
    search_radius = st.slider(
        "Initial search radius (km)",
        min_value=5,
        max_value=50,
        value=RADIUS_KM,
        step=5,
        help="Initial radius to search for hospitals. Note: Travel time will still be limited to 1 hour."
    )
    
    # Travel time setting
    max_travel_minutes = st.slider(
        "Maximum travel time (minutes)",
        min_value=15,
        max_value=60,
        value=60,
        step=5,
        help="Maximum travel time to consider a hospital reachable"
    )
    max_travel_seconds = max_travel_minutes * 60

# Main area for location input and map display
col1, col2 = st.columns([3, 7])

with col1:
    st.header("Location Input")
    
    # Initialize session state for coordinates if they don't exist
    if 'lat' not in st.session_state:
        st.session_state.lat = None
    if 'lng' not in st.session_state:
        st.session_state.lng = None
    if 'address' not in st.session_state:
        st.session_state.address = ""
    if 'hospitals' not in st.session_state:
        st.session_state.hospitals = []
    if 'reachable_hospitals' not in st.session_state:
        st.session_state.reachable_hospitals = []
    if 'selected_hospital' not in st.session_state:
        st.session_state.selected_hospital = None
    
    # Location input method selection
    input_method = st.radio(
        "Select input method",
        ["Enter address", "Use map coordinates"]
    )
    
    if input_method == "Enter address":
        # Address input
        if sample_location != "Custom Input" and use_sample:
            address = sample_location
        else:
            address = st.text_input(
                "Enter address or city in India",
                value=st.session_state.address if st.session_state.address else "",
                placeholder="E.g. Connaught Place, New Delhi"
            )
        
        if st.button("Search Location"):
            if not address:
                st.error("Please enter an address")
            else:
                with st.spinner("Geocoding address..."):
                    lat, lng, formatted_address = geocode_address(address, API_KEY)
                    
                    if lat and lng:
                        st.session_state.lat = lat
                        st.session_state.lng = lng
                        st.session_state.address = formatted_address
                        st.success(f"Located: {formatted_address}")
                    else:
                        st.error("Could not geocode the address. Please try another address.")
    else:
        # Direct coordinate input
        lat_input = st.number_input(
            "Latitude",
            value=st.session_state.lat if st.session_state.lat else 28.6139,
            format="%.6f"
        )
        lng_input = st.number_input(
            "Longitude",
            value=st.session_state.lng if st.session_state.lng else 77.2090,
            format="%.6f"
        )
        
        if st.button("Set Coordinates"):
            st.session_state.lat = lat_input
            st.session_state.lng = lng_input
            st.session_state.address = f"Custom coordinates ({lat_input}, {lng_input})"
            st.success(f"Coordinates set: ({lat_input}, {lng_input})")
    
    # If coordinates are set, show them
    if st.session_state.lat and st.session_state.lng:
        st.info(f"Selected location: {st.session_state.address}")
        
        # Search for hospitals button
        if st.button("Find Hospitals Within 1 Hour"):
            with st.spinner(f"Searching for hospitals within {search_radius}km radius..."):
                # Get hospitals from Google Places API
                google_hospitals = search_hospitals_google(
                    st.session_state.lat,
                    st.session_state.lng,
                    API_KEY
                )
                
                # Find hospitals reachable within the travel time limit
                reachable_hospitals = find_hospitals_within_travel_time(
                    st.session_state.lat,
                    st.session_state.lng,
                    google_hospitals,
                    API_KEY,
                    max_travel_seconds
                )
                
                # Store hospital data in session state
                st.session_state.hospitals = google_hospitals
                st.session_state.reachable_hospitals = reachable_hospitals
                
                # Clear selected hospital
                st.session_state.selected_hospital = None
                
                # Show success message or warning
                if reachable_hospitals:
                    st.success(f"Found {len(reachable_hospitals)} hospitals reachable within {max_travel_minutes} minutes!")
                else:
                    st.warning(f"No hospitals found within {max_travel_minutes} minutes travel time. You are in a 'blind spot'.")

    # Display hospital list if hospitals are found
    if st.session_state.reachable_hospitals:
        st.header("Hospitals Within Travel Time")
        
        # Group hospitals by type
        emergency_hospitals = [h for h in st.session_state.reachable_hospitals if h.get('has_emergency', False)]
        multispeciality = [h for h in st.session_state.reachable_hospitals if h.get('is_multispeciality', False) and not h.get('has_emergency', False)]
        regular = [h for h in st.session_state.reachable_hospitals if not h.get('is_multispeciality', False) and not h.get('has_emergency', False)]
        
        # Display emergency hospitals first
        if emergency_hospitals:
            st.subheader("Hospitals with Emergency Services 🚑")
            for i, hospital in enumerate(emergency_hospitals):
                name = hospital.get('name', 'Unknown Hospital')
                travel_time = format_travel_time(hospital.get('travel_info', {}).get('duration_seconds', 0))
                
                # Add emergency indicator
                display_name = f"{name} - {travel_time}"
                
                if st.button(display_name, key=f"emerg_{i}"):
                    st.session_state.selected_hospital = hospital
                    st.success(f"Selected: {name}")
        
        # Display multispeciality hospitals next
        if multispeciality:
            st.subheader("Multispeciality Hospitals")
            for i, hospital in enumerate(multispeciality):
                name = hospital.get('name', 'Unknown Hospital')
                travel_time = format_travel_time(hospital.get('travel_info', {}).get('duration_seconds', 0))
                
                if st.button(f"{name} - {travel_time}", key=f"multi_{i}"):
                    st.session_state.selected_hospital = hospital
                    st.success(f"Selected: {name}")
        
        # Display other hospitals
        if regular:
            st.subheader("Other Hospitals")
            for i, hospital in enumerate(regular):
                name = hospital.get('name', 'Unknown Hospital')
                travel_time = format_travel_time(hospital.get('travel_info', {}).get('duration_seconds', 0))
                
                if st.button(f"{name} - {travel_time}", key=f"reg_{i}"):
                    st.session_state.selected_hospital = hospital
                    st.success(f"Selected: {name}")
    
    # Display a "No hospitals found" message if appropriate
    elif st.session_state.hospitals and not st.session_state.reachable_hospitals:
        st.error(f"📍 **Blind Spot Detected**: No hospitals within {max_travel_minutes} minutes travel time.")
        st.warning("Consider increasing the travel time limit or selecting a different location.")

with col2:
    st.header("Map View")
    
    # Display the map with hospitals or route based on selection
    if st.session_state.lat and st.session_state.lng:
        if st.session_state.selected_hospital:
            # Show route to selected hospital
            selected_name = st.session_state.selected_hospital.get('name', 'Unknown Hospital')
            st.subheader(f"Route to {selected_name}")
            
            # Display travel information
            travel_info = st.session_state.selected_hospital.get('travel_info', {})
            travel_time = format_travel_time(travel_info.get('duration_seconds', 0))
            distance_km = travel_info.get('distance_meters', 0) / 1000
            
            # Create columns for travel info
            info_col1, info_col2 = st.columns(2)
            with info_col1:
                st.metric("Travel Time", travel_time)
            with info_col2:
                st.metric("Distance", f"{distance_km:.2f} km")
            
            # Create and display route map
            route_map = create_route_map(
                st.session_state.lat,
                st.session_state.lng,
                st.session_state.selected_hospital
            )
            
            folium_static(route_map, width=800, height=500)
            
            # Hospital details
            st.subheader("Hospital Details")
            place_id = st.session_state.selected_hospital.get('place_id')
            if place_id:
                with st.spinner("Fetching hospital details..."):
                    details = get_hospital_details(place_id, API_KEY)
                    
                    if details:
                        st.markdown(f"**Name:** {details.get('name', 'N/A')}")
                        st.markdown(f"**Address:** {details.get('formatted_address', 'N/A')}")
                        
                        if 'formatted_phone_number' in details:
                            st.markdown(f"**Phone:** {details.get('formatted_phone_number')}")
                        
                        if 'website' in details:
                            st.markdown(f"**Website:** [{details.get('website')}]({details.get('website')})")
                        
                        if 'rating' in details:
                            st.markdown(f"**Rating:** {details.get('rating')}/5 ({details.get('user_ratings_total', 0)} reviews)")
                        
                        # Check if it's likely a multispeciality hospital
                        if st.session_state.selected_hospital.get('is_multispeciality', False):
                            st.info("📋 **Multispeciality Hospital**: This appears to be a multispeciality hospital that likely offers a wider range of medical services.")
                            
                        # Check if it has ample emergency services
                        if st.session_state.selected_hospital.get('has_emergency', False):
                            st.success("🚑 **Emergency Services**: This hospital appears to have ample emergency services available.")
                    else:
                        st.warning("Could not fetch detailed information for this hospital.")
            
            # Add a button to go back to the hospital list view
            if st.button("Back to Hospital List"):
                st.session_state.selected_hospital = None
                st.rerun()
            
        elif st.session_state.reachable_hospitals:
            # Show all reachable hospitals on the map
            st.subheader(f"Hospitals Within {max_travel_minutes} Minutes Travel Time")
            
            # Display summary information
            total_hospitals = len(st.session_state.reachable_hospitals)
            multispeciality_count = len([h for h in st.session_state.reachable_hospitals if h.get('is_multispeciality', False)])
            emergency_count = len([h for h in st.session_state.reachable_hospitals if h.get('has_emergency', False)])
            
            # Create columns for summary info
            sum_col1, sum_col2, sum_col3 = st.columns(3)
            with sum_col1:
                st.metric("Total Hospitals", total_hospitals)
            with sum_col2:
                st.metric("Multispeciality", multispeciality_count)
            with sum_col3:
                st.metric("With Emergency Services", emergency_count)
            
            # Create and display the map
            hospitals_map = create_hospitals_map(
                st.session_state.lat,
                st.session_state.lng,
                st.session_state.reachable_hospitals,
                search_radius
            )
            
            folium_static(hospitals_map, width=800, height=500)
            
            # Legend for map markers
            st.markdown("**Map Legend:**")
            st.markdown("🔵 Blue markers: Multispeciality hospitals")
            st.markdown("🟢 Green markers: Regular hospitals")
            st.markdown("🔴 Red markers: Hospitals with ample emergency services")
            st.markdown("🏠 Red home icon: Your location")
            
            st.info("Click on a hospital in the list (left panel) to see the detailed route.")
            
        elif st.session_state.hospitals:
            # No hospitals within travel time - blind spot
            st.warning(f"⚠️ **Blind Spot Detected**: No hospitals are reachable within {max_travel_minutes} minutes travel time from your location.")
            
            # Create a simple map showing the user's location
            m = folium.Map(location=[st.session_state.lat, st.session_state.lng], zoom_start=12)
            
            # Add a marker for the user's location
            folium.Marker(
                location=[st.session_state.lat, st.session_state.lng],
                popup="Your Location",
                tooltip="Your Location",
                icon=folium.Icon(color='red', icon='home', prefix='fa')
            ).add_to(m)
            
            # Add a circle representing the search radius
            folium.Circle(
                location=[st.session_state.lat, st.session_state.lng],
                radius=search_radius * 1000,  # Convert km to meters
                color='red',
                fill=True,
                fill_opacity=0.2
            ).add_to(m)
            
            folium_static(m, width=800, height=500)
            
            st.error("You are in a medical 'blind spot'. No hospitals can be reached within the specified travel time.")
            st.markdown("**Suggestions:**")
            st.markdown("1. Increase the maximum travel time in the sidebar")
            st.markdown("2. Try a different location")
            st.markdown("3. Contact emergency services if this is an emergency")
            
        else:
            # Initial map view centered on user's location
            st.info("Use the controls on the left to search for hospitals near your location.")
            
            # Create a simple initial map
            initial_map = folium.Map(location=[st.session_state.lat, st.session_state.lng], zoom_start=13)
            
            # Add a marker for the user's location
            folium.Marker(
                location=[st.session_state.lat, st.session_state.lng],
                popup="Your Location",
                tooltip="Your Location",
                icon=folium.Icon(color='red', icon='home', prefix='fa')
            ).add_to(initial_map)
            
            folium_static(initial_map, width=800, height=500)
    else:
        # No location selected yet
        st.info("Please select a location using the controls on the left to start.")
        
        # Display a default map of India
        default_map = folium.Map(location=[20.5937, 78.9629], zoom_start=5)  # Centered on India
        folium_static(default_map, width=800, height=500)

# Footer with documentation
st.markdown("---")
with st.expander("Documentation and Help"):
    st.markdown("""
    ### How to use this application
    
    1. **Set your location**: Enter an address or coordinates using the controls on the left
    2. **Find hospitals**: Click the "Find Hospitals Within 1 Hour" button
    3. **Explore options**: View the hospitals on the map and in the list
    4. **Get directions**: Click on a hospital name to see the route and detailed information
    
    ### Features
    
    - **Real-time traffic**: Routes account for current traffic conditions
    - **Speed limits**: Routing considers legal speed limits on roads
    - **Hospital prioritization**: Multispeciality hospitals are highlighted and listed first
    - **Emergency services**: Hospitals with ample emergency services are highlighted with red markers
    - **Blind spot detection**: Areas without hospitals reachable within one hour are marked
    
    ### Notes
    
    - This application requires Google API keys with access to Places, Maps Routes, Roads, and Geocoding APIs
    - Hospital data is retrieved from Google Places API
    - Travel times are estimates and may vary based on actual traffic conditions
    """)

# Display version and credits
st.sidebar.markdown("---")
st.sidebar.caption("v1.0.0 - Hospital Route Finder")
st.sidebar.caption("© 2023 - Built with Streamlit")
