import streamlit as st
from streamlit_gsheets import GSheetsConnection
import plotly.express as px

st.set_page_config(page_title="Grad 2026 Seating", layout="wide")

# Connect to Google Sheets
conn = st.connection("gsheets", type=GSheetsConnection)

# Load data - tab name MUST be "Tables"
df = conn.read(worksheet="Tables", ttl=0)

st.title("🎓 Grade 12 Graduation Seating")

# Sidebar for Booking
with st.sidebar:
    st.header("Reserve Your Table")
    name = st.text_input("Full Name")
    tickets = st.number_input("Tickets", min_value=1, max_value=10, value=1)
    
    # Logic: Only show tables with room
    df['Remaining'] = df['Capacity'] - df['Taken']
    available = df[df['Remaining'] >= tickets]
    
    if not available.empty:
        selection = st.selectbox("Pick a Table", available['Table_ID'])
        if st.button("Confirm Seating"):
            if name:
                idx = df[df['Table_ID'] == selection].index[0]
                df.at[idx, 'Taken'] += tickets
                df.at[idx, 'Guest_List'] = str(df.at[idx, 'Guest_List']) + f"{name}({tickets}), "
                
                # UPDATE THE SHEET
                conn.update(worksheet="Tables", data=df)
                st.success("Table Booked!")
                st.rerun()
            else:
                st.error("Enter your name.")

# Visual Map
df['Status'] = df.apply(lambda x: "FULL" if x['Remaining'] <= 0 else "AVAILABLE", axis=1)
fig = px.scatter(df, x='X', y='Y', text='Table_ID', size=[20]*len(df),
                 color='Status', color_discrete_map={"AVAILABLE": "#2ecc71", "FULL": "#e74c3c"})
fig.update_layout(xaxis_visible=False, yaxis_visible=False)
st.plotly_chart(fig, use_container_width=True)
