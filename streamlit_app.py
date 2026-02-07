import streamlit as st
from streamlit_gsheets import GSheetsConnection
import plotly.express as px
import pandas as pd

# Set page to wide mode and add a title to the browser tab
st.set_page_config(page_title="Grad 2026 Seating", layout="wide", page_icon="🎓")

# 1. --- DATABASE CONNECTION ---
conn = st.connection("gsheets", type=GSheetsConnection)

# Load data with ttl=0 to ensure we always see the most recent bookings
df = conn.read(worksheet="Tables", ttl=0)
student_df = conn.read(worksheet="Students", ttl=0)

st.title("🎓 Grade 12 Graduation Seating")

# 2. --- TOP SECTION: FIND A FRIEND ---
st.markdown("### 🔍 Find a Guest")
search_query = st.text_input("Type a name to see where they are sitting:", placeholder="e.g. Smith")

if search_query:
    results = df[df['Guest_List'].str.contains(search_query, case=False, na=False)]
    if not results.empty:
        for _, row in results.iterrows():
            st.success(f"✅ Found '{search_query}' at **Table {row['Table_ID']}**")
    else:
        st.warning("No one by that name has selected a table yet.")

st.divider()

# 3. --- SIDEBAR: SECURE BOOKING ---
with st.sidebar:
    st.header("🎫 Reserve Your Table")
    
    # Select Last Name
    last_names = sorted(student_df['Last Name'].unique().tolist())
    sel_last = st.selectbox("Your Last Name:", [""] + last_names)
    
    if sel_last:
        # Filter First Names based on Last Name
        filtered_firsts = student_df[student_df['Last Name'] == sel_last]['First Name'].tolist()
        sel_first = st.selectbox("Your First Name:", [""] + filtered_firsts)
        
        if sel_first:
            full_name = f"{sel_first} {sel_last}"
            
            # Get ticket count for this specific student
            student_info = student_df[(student_df['Last Name'] == sel_last) & (student_df['First Name'] == sel_first)].iloc[0]
            ticket_count = int(student_info['Tickets'])
            
            st.info(f"Welcome {sel_first}. You have **{ticket_count}** tickets.")
            
            # Check if name is already in ANY table's guest list
            is_already_seated = df['Guest_List'].str.contains(full_name, na=False).any()
            
            if is_already_seated:
                st.warning("⚠️ You are already assigned to a table!")
            else:
                # Show tables that have enough seats left
                df['Remaining'] = df['Capacity'] - df['Taken']
                valid_tables = df[df['Remaining'] >= ticket_count]
                
                if not valid_tables.empty:
                    selection = st.selectbox("Choose an available table:", valid_tables['Table_ID'])
                    if st.button("Confirm Seating", use_container_width=True, type="primary"):
                        # Find the row in the dataframe and update it
                        idx = df[df['Table_ID'] == selection].index[0]
                        df.at[idx, 'Taken'] += ticket_count
                        
                        # Add name to the guest list string
                        current_list = str(df.at[idx, 'Guest_List']) if pd.notna(df.at[idx, 'Guest_List']) else ""
                        df.at[idx, 'Guest_List'] = current_list + f"{full_name} ({ticket_count}), "
                        
                        # Write the whole dataframe back to Google Sheets
                        conn.update(worksheet="Tables", data=df)
                        st.success(f"Success! Table {selection} reserved.")
                        st.balloons()
                        st.rerun()
                else:
                    st.error("No tables have enough space left for your party.")

# 4. --- VISUAL MAP SECTION ---
st.markdown("### 🗺️ Room Layout")

# Define status for colors
def get_status(row):
    rem = row['Capacity'] - row['Taken']
    if rem <= 0: return "🔴 Sold Out"
    if rem <= 4: return "🟡 Nearly Full"
    return "🟢 Available"

df['Status'] = df.apply(get_status, axis=1)

# Create the scatter plot
fig = px.scatter(
    df, x='X', y='Y', text='Table_ID',
    color='Status',
    color_discrete_map={
        "🟢 Available": "#2ecc71", 
        "🟡 Nearly Full": "#f1c40f", 
        "🔴 Sold Out": "#e74c3c"
    },
    hover_name="Table_ID",
    hover_data={"Remaining": True, "Guest_List": True, "X": False, "Y": False}
)

# ADJUST TABLE SIZE HERE
# Decrease 'sizeref' to make circles bigger (e.g., 0.05 is HUGE, 0.2 is smaller)
fig.update_traces(
    marker=dict(
        size=50, 
        sizemode='area', 
        sizeref=0.1, 
        line=dict(width=2, color='white')
    ),
    textposition='middle center',
    textfont=dict(size=14, color="white")
)

# Set the "room" boundaries so circles don't touch the edges
fig.update_layout(
    xaxis=dict(range=[df['X'].min() - 1, df['X'].max() + 1], visible=False),
    yaxis=dict(range=[df['Y'].min() - 1, df['Y'].max() + 1], visible=False),
    height=700,
    margin=dict(l=10, r=10, t=10, b=10),
    legend_title_text='Table Status'
)

st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

# 5. --- LIST VIEW ---
with st.expander("Show Text List of All Tables"):
    # Clean up the display for the table
    display_df = df[['Table_ID', 'Capacity', 'Taken', 'Guest_List']].copy()
    st.dataframe(display_df, hide_index=True, use_container_width=True)
