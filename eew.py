from ECHO_modules.get_data import get_echo_data # Import the get_echo_data function, which is the function that does the work of retrieving data from the SBU database
from ECHO_modules.get_data import get_spatial_data # Import this function, which will help us get county boundaries
from ECHO_modules.geographies import spatial_tables, fips # Import for mapping purposes
from ECHO_modules.geographies import states as state_abbreviations # Import US state abbreviations for help
from ECHO_modules.utilities import get_active_facilities # Get the active facilities in the region
from ECHO_modules.utilities import bivariate_map, map_style # Style for our map
from ECHO_modules.utilities import marker_text # Utilities to help us make the map
import geopandas
import folium # Folium is for mapping
from folium.plugins import FastMarkerCluster
from streamlit_folium import st_folium
import pandas as pd
import streamlit as st

# Wide page!
st.set_page_config(layout="wide")

# Create some session state variables to track user interaction
if "first_time" not in st.session_state: # If this is the first time loading the script, track that
	st.session_state["first_time"] = True 
if "county_names" not in st.session_state: # If we haven't loaded county names before, get ready to
	st.session_state["county_names"] = None

# Initial data load (county/state names)
@st.cache
def load_county_names():
	counties = pd.read_csv("state_counties_corrected.csv") # Can also be found here: https://github.com/edgi-govdata-archiving/ECHO_modules/blob/main/data/
	# Data pre-processing - make sure the only states in the list are real states, but comparing with the fips data
	counties = counties.loc[counties["FAC_STATE"].isin(state_abbreviations)]
	return counties

## Only load counties if this is the first run through of the script
if st.session_state["first_time"]:
	st.session_state["county_names"] = load_county_names()
	st.session_state["first_time"] = False # We've loaded the county names once, we can track that by setting first_time to False


# Arrange the page
container = st.container()
with container:
	col1, col2, col3 = st.columns([.2, .4, .4])

# Streamlit pickers
## State picker
with col1:
	state = st.selectbox(
		"Which state?",
		list(st.session_state["county_names"]["FAC_STATE"].unique()) # List of state abbreviations
	)
	## County picker
	county = st.selectbox(
		"Which county in this state?",
		list(st.session_state["county_names"].loc[st.session_state["county_names"]["FAC_STATE"] == state]["County"].unique()) # List of counties in the selected state
	)

# Try to get county data. EPA's list of counties / states is notoriously bad and includes Canadian provinces, so we need to handle these exceptions
try:
	with col2:
		# Get facilities and county boundaries
		with st.spinner('Loading data...'): # Tell the user we are loading the data
			# Get facilities
			active_fac = get_active_facilities(state, 'County', [county])
			## Display
			st.markdown("## Facility data") 
			st.dataframe(active_fac[["FAC_NAME", "FAC_COUNTY", "FAC_STATE"]])

			# Get county boundaries
			county_boundaries, state_boundaries = get_spatial_data("County", [state], spatial_tables, fips, county.title())

			# Get EJ Screen data
			baseline = int(str(county_boundaries["geoid"][0]) + "0000000") # Find the county's geoid and turn it into a 12 digit block group code
			next_county = baseline + 10000000 # Find the next county's geoid - we don't want any of this so it's the limit of our query
			sql = 'SELECT * from "EJSCREEN_2021_USPR" where "ID" between '+str(baseline)+' and '+str(next_county)+'' # The query should give us all the block groups in the county, nothing more nothing less
			ej_data = get_echo_data(sql)
			## Display
			st.markdown("## EJScreen data")
			st.dataframe(ej_data)

		# Map
	with col3:	
		with st.spinner('Loading map...'): # Tell the user we are making the map
		  # Construct the map
		  m = folium.Map()

		  # Add the county boundaries
		  cb = folium.GeoJson(
		    county_boundaries,
		    style_function = lambda x: map_style['other'] # Style the county
		  ).add_to(m)

		  # Show the active facilities
		  ## Create the Marker Cluster array
		  #kwargs={"disableClusteringAtZoom": 10, "showCoverageOnHover": False}
		  mc = FastMarkerCluster("")
		  ## Add a clickable marker for each facility
		  for index, row in active_fac.iterrows():
		    mc.add_child(folium.CircleMarker(
		      location = [row["FAC_LAT"], row["FAC_LONG"]],
		      popup = marker_text( row, False ),
		      radius = 8,
		      color = "black",
		      weight = 1,
		      fill_color = "orange",
		      fill_opacity= .4
		    ))
		  ## Add it to the map
		  m.add_child(mc)

		  # Compute boundaries so that the map automatically zooms in
		  bounds = m.get_bounds()
		  m.fit_bounds(bounds, padding=0)

		  # Display the map
		  out = st_folium(
		    m,
		    width = 750,
		    returned_objects=[] # No objects need to be returned to streamlit to re-load the page! We don't want that!!
		  )
except:
	with col2:
		st.warning("### Not a valid state and/or county")