import streamlit as st
from streamlit_gsheets import GSheetsConnection
import plotly.express as px
import pandas as pd

st.set_page_config(page_title="Grad 2026 Seating", layout="wide", page_icon="🎓")

# 1. Database Connection
conn = st.connection("gsheets", type=GSheetsConnection)

def load_data():
    return conn.read(worksheet="Tables", ttl=0)

df = load_data()

# 2. Hero Section
st.title("🎓 Grade 12 Graduation Banquet")
st.subheader("Select your table and secure your seats.")

# 3. Sidebar Booking Panel
with st.sidebar:
    st.image("https://img.icons8.com/fluency/96/graduation-cap.png")
    st.header("Reserve Your Table")
    
    name = st.text_input("Full Name (Party Lead)", placeholder="e.g. John Smith")
    tickets = st.number_input("How many tickets in your party?", min_value=1, max_value=10, value=1)
    
    # Logic: Only show tables that have enough ROOM for this specific ticket count
    df['Remaining'] = df['Capacity'] - df['Taken']
    valid_options = df[df['Remaining'] >= tickets]
    
    if not valid_options.empty:
        selection = st.selectbox("Available Tables:", valid_options['Table_ID'])
        if st.button("Confirm My Selection", use_container_width=True, type="primary"):
            if name:
                # Execution logic
                idx = df[df['Table_ID'] == selection].index[0]
                df.at[idx, 'Taken'] += tickets
                df.at[idx, 'Guest_List'] = str(df.at[idx, 'Guest_List']) + f"{name} ({tickets}), "
                
                # Write back to Google
                conn.update(worksheet="Tables", data=df)
                st.success(f"Success! {name}, you're at Table {selection}.")
                st.balloons()
                st.rerun()
            else:
                st.error("Please enter a name first.")
    else:
        st.error("No tables found with enough available seats for your party size.")

# 4. The Visual Map
st.markdown("### 🗺️ Floor Plan")
st.info("🟢 Available | 🟡 Nearly Full | 🔴 Sold Out")

# Create a 'color' column for the map based on availability
def get_color(row):
    rem = row['Capacity'] - row['Taken']
    if rem <= 0: return "Sold Out"
    if rem < 3: return "Nearly Full"
    return "Available"

df['Status'] = df.apply(get_color, axis=1)

fig = px.scatter(df, x='X', y='Y', text='Table_ID', 
                 size=[20]*len(df),
                 color='Status',
                 color_discrete_map={"Available": "#2ecc71", "Nearly Full": "#f1c40f", "Sold Out": "#e74c3c"},
                 hover_name="Table_ID",
                 hover_data={"X":False, "Y":False, "Remaining":True, "Taken":True})

fig.update_traces(textposition='middle center', marker=dict(line=dict(width=2, color='DarkSlateGrey')))
fig.update_layout(xaxis_visible=False, yaxis_visible=False, showlegend=True, margin=dict(l=0, r=0, t=0, b=0))

st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

# 5. Organizer List (Collapsible)
with st.expander("View Detailed Table Occupancy"):
    st.dataframe(df[['Table_ID', 'Capacity', 'Taken', 'Remaining', 'Guest_List']], hide_index=True)
