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
st.subheader("Interactive Seating Chart")

# 3. Sidebar Booking Panel
with st.sidebar:
    st.header("🎫 Reserve Your Table")
    name = st.text_input("Full Name (Party Lead)")
    tickets = st.number_input("Number of Seats", min_value=1, max_value=10, value=1)
    
    df['Remaining'] = df['Capacity'] - df['Taken']
    # Only show tables that can fit the party size
    valid_options = df[df['Remaining'] >= tickets]
    
    if not valid_options.empty:
        selection = st.selectbox("Select an available table:", valid_options['Table_ID'])
        if st.button("Confirm Selection", use_container_width=True, type="primary"):
            if name:
                idx = df[df['Table_ID'] == selection].index[0]
                # Update logic
                df.at[idx, 'Taken'] += tickets
                # Maintain the guest list string
                current_list = str(df.at[idx, 'Guest_List']) if pd.notna(df.at[idx, 'Guest_List']) else ""
                df.at[idx, 'Guest_List'] = current_list + f"{name} ({tickets}), "
                
                conn.update(worksheet="Tables", data=df)
                st.success(f"Got it! {name} is at Table {selection}.")
                st.balloons()
                st.rerun()
            else:
                st.error("Please enter a name!")
    else:
        st.error("No tables have enough space for your party size.")

# 4. The Visual Map Logic
def get_status(row):
    rem = row['Capacity'] - row['Taken']
    if rem <= 0: return "🔴 Sold Out"
    if rem < 3: return "🟡 Nearly Full"
    return "🟢 Available"

df['Status'] = df.apply(get_status, axis=1)

# Create the fancy scatter plot
fig = px.scatter(
    df, x='X', y='Y', text='Table_ID', 
    size=[20]*len(df),
    color='Status',
    color_discrete_map={
        "🟢 Available": "#2ecc71", 
        "🟡 Nearly Full": "#f1c40f", 
        "🔴 Sold Out": "#e74c3c"
    },
    hover_name="Table_ID",
    hover_data={"X": False, "Y": False, "Remaining": True, "Taken": True, "Guest_List": True}
)

# Style tweaks to make it look like a floor plan
fig.update_traces(
    textposition='middle center', 
    marker=dict(line=dict(width=2, color='DarkSlateGrey')),
    textfont=dict(color='white', size=14)
)

fig.update_layout(
    xaxis_visible=False, 
    yaxis_visible=False, 
    showlegend=True,
    legend_title_text='Table Status',
    margin=dict(l=20, r=20, t=20, b=20),
    height=600
)

st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

# 5. Backup Table View (at the bottom)
with st.expander("Show Text List of Tables"):
    st.dataframe(df[['Table_ID', 'Remaining', 'Taken', 'Guest_List']], hide_index=True)
