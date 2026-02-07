import streamlit as st
from streamlit_gsheets import GSheetsConnection
import plotly.express as px
import pandas as pd

# -----------------------------------------------------------------------------
# 1. PAGE CONFIGURATION
# This sets the browser tab title and forces the app to use the full screen width.
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Grad 2026 Seating", 
    layout="wide", 
    page_icon="🎓"
)

# -----------------------------------------------------------------------------
# 2. DATABASE CONNECTION
# This connects to the Google Sheet using the secrets you pasted into Streamlit.
# 'ttl=0' means "Time To Live is 0", forcing the app to fetch fresh data
# every time the page is refreshed so you don't see old/cached bookings.
# -----------------------------------------------------------------------------
conn = st.connection("gsheets", type=GSheetsConnection)

# Fetch the "Tables" tab (the map) and the "Students" tab (the guest list)
df = conn.read(worksheet="Tables", ttl=0)
student_df = conn.read(worksheet="Students", ttl=0)

st.title("🎓 Grade 12 Graduation Seating")
st.markdown("Find your friends on the map and reserve your table below.")

# -----------------------------------------------------------------------------
# 3. SEARCH SECTION (TOP OF PAGE)
# This allows guests to type in a name and find which table that person is at.
# -----------------------------------------------------------------------------
st.markdown("### 🔍 Find a Guest")
search_query = st.text_input(
    "Type a name to see where they are sitting:", 
    placeholder="Start typing a name..."
)

if search_query:
    # This line looks through the 'Guest_List' column for the text typed above
    results = df[df['Guest_List'].str.contains(search_query, case=False, na=False)]
    
    if not results.empty:
        for _, row in results.iterrows():
            st.success(f"✅ Found results at **Table {row['Table_ID']}**")
            with st.expander(f"See everyone at Table {row['Table_ID']}"):
                st.write(row['Guest_List'])
    else:
        st.warning("No one by that name has selected a table yet.")

st.divider()

# -----------------------------------------------------------------------------
# 4. SIDEBAR: THE BOOKING SYSTEM
# This is where the magic happens. It handles student verification and booking.
# -----------------------------------------------------------------------------
with st.sidebar:
    st.header("🎫 Reserve Your Table")
    
    # STEP 1: Select Last Name (helps filter a list of 200+ people)
    last_names = sorted(student_df['Last Name'].unique().tolist())
    sel_last = st.selectbox("1. Your Last Name:", [""] + last_names)
    
    if sel_last:
        # STEP 2: Show only First Names that match that Last Name
        filtered_firsts = student_df[student_df['Last Name'] == sel_last]['First Name'].tolist()
        sel_first = st.selectbox("2. Your First Name:", [""] + filtered_firsts)
        
        if sel_first:
            full_name = f"{sel_first} {sel_last}"
            
            # STEP 3: Identify how many tickets this student is allowed to book
            student_info = student_df[
                (student_df['Last Name'] == sel_last) & 
                (student_df['First Name'] == sel_first)
            ].iloc[0]
            ticket_count = int(student_info['Tickets'])
            
            st.info(f"Welcome {sel_first}! You are booking for **{ticket_count}** seats.")
            
            # STEP 4: Check if they are already in the guest list somewhere
            already_seated_row = df[df['Guest_List'].str.contains(full_name, na=False)]
            
            if not already_seated_row.empty:
                # If they are already seated, tell them where and stop the booking
                assigned_table = already_seated_row.iloc[0]['Table_ID']
                st.warning(f"⚠️ You are already assigned to **Table {assigned_table}**")
                st.write("---")
                st.caption("**Need to change tables?**")
                st.write("Please contact the Admin to manually move your group.")
            else:
                # STEP 5: Filter the table list to only show tables with enough room
                df['Remaining'] = df['Capacity'] - df['Taken']
                valid_tables = df[df['Remaining'] >= ticket_count]
                
                if not valid_tables.empty:
                    selection = st.selectbox("3. Choose an available table:", valid_tables['Table_ID'])
                    
                    if st.button("Confirm Seating", use_container_width=True, type="primary"):
                        # Find the correct row in the spreadsheet to update
                        idx = df[df['Table_ID'] == selection].index[0]
                        
                        # Add the ticket count to 'Taken'
                        df.at[idx, 'Taken'] += ticket_count
                        
                        # Append the student's name to the 'Guest_List' string
                        # We handle 'nan' values to avoid weird text in the sheet
                        current_list = str(df.at[idx, 'Guest_List']) if pd.notna(df.at[idx, 'Guest_List']) and df.at[idx, 'Guest_List'] != "nan" else ""
                        df.at[idx, 'Guest_List'] = current_list + f"{full_name} ({ticket_count}), "
                        
                        # SEND UPDATED DATA TO GOOGLE SHEETS
                        conn.update(worksheet="Tables", data=df)
                        
                        st.success(f"Success! Table {selection} reserved.")
                        st.balloons()
                        st.rerun() # Refresh page to show updated map
                else:
                    st.error("No tables have enough space left for your party size.")

    # --- SIDEBAR FOOTER: ADMIN & CONTACT ---
    st.sidebar.markdown("---")
    
    # DOWNLOAD BUTTON: Export the current seating data as a CSV file
    st.sidebar.caption("📊 **Admin Tools**")
    csv_data = df[['Table_ID', 'Capacity', 'Taken', 'Guest_List']].to_csv(index=False).encode('utf-8')
    st.sidebar.download_button(
        label="Download Seating List",
        data=csv_data,
        file_name='grad_seating_final.csv',
        mime='text/csv',
    )
    
    st.sidebar.markdown("---")
    st.sidebar.caption("📩 **Support**")
    st.sidebar.write("Contact the Grad Committee for issues:")
    st.sidebar.write("[your.email@example.com]")
# -----------------------------------------------------------------------------
# 5. VISUAL MAP GENERATION
# This part draws the room layout using the X and Y coordinates from your sheet.
# -----------------------------------------------------------------------------
st.markdown("### 🗺️ Room Layout")

# FORCE THE MATH: Ensure 'Remaining' is always Capacity minus Taken
df['Remaining'] = df['Capacity'] - df['Taken']

# Logic to determine circle colors based on the FRESH math above
def get_status(row):
    if row['Remaining'] <= 0: 
        return "🔴 Sold Out"
    if row['Remaining'] <= 4: 
        return "🟡 Nearly Full"
    return "🟢 Available"

df['Status'] = df.apply(get_status, axis=1)

# Create the Scatter Plot
fig = px.scatter(
    df, x='X', y='Y', text='Table_ID',
    color='Status',
    color_discrete_map={
        "🟢 Available": "#2ecc71", 
        "🟡 Nearly Full": "#f1c40f", 
        "🔴 Sold Out": "#e74c3c"
    },
    hover_name="Table_ID",
    # We explicitly tell the hover box to use the calculated 'Remaining' column
    hover_data={"Remaining": True, "Guest_List": True, "X": False, "Y": False, "Status": False}
)

# -----------------------------------------------------------------------------
# VISUAL STYLING FOR TABLES
# size: The base size of the circles.
# sizeref: Lower numbers make circles BIGGER. 0.1 is standard.
# -----------------------------------------------------------------------------
fig.update_traces(
    marker=dict(size=60, sizemode='area', sizeref=0.1, line=dict(width=2, color='white')),
    textposition='middle center',
    textfont=dict(size=14, color="white")# White border around circles
)

# Set the "room" boundaries so circles don't touch the very edges of the screen
fig.update_layout(
    xaxis=dict(range=[df['X'].min() - 1, df['X'].max() + 1], visible=False),
    yaxis=dict(range=[df['Y'].min() - 1, df['Y'].max() + 1], visible=False),
    height=800, # Height of the map in pixels
    margin=dict(l=10, r=10, t=10, b=10),
    legend_title_text='Table Status'
)

# Render the chart
st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

# -----------------------------------------------------------------------------
# 6. TEXT LIST VIEW
# A simple table at the bottom for those who prefer reading a list.
# -----------------------------------------------------------------------------
with st.expander("Show Detailed Seating List (Table View)"):
    display_df = df[['Table_ID', 'Remaining', 'Guest_List']].copy()
    st.dataframe(display_df, hide_index=True, use_container_width=True)


# --- SIDEBAR: SECURE BOOKING ---
with st.sidebar:
    st.header("🎫 Reserve Your Table")
    
    # 1. Selection logic (The "Sign-in")
    last_names = sorted(student_df['Last Name'].unique().tolist())
    sel_last = st.selectbox("Your Last Name:", [""] + last_names)
    
    if sel_last:
        filtered_firsts = student_df[student_df['Last Name'] == sel_last]['First Name'].tolist()
        sel_first = st.selectbox("Your First Name:", [""] + filtered_firsts)
        
        if sel_first:
            full_name = f"{sel_first} {sel_last}"
            student_info = student_df[(student_df['Last Name'] == sel_last) & (student_df['First Name'] == sel_first)].iloc[0]
            
            # --- THIS IS THE 'ONLY SEE THEIR TICKETS' PART ---
            ticket_count = int(student_info['Tickets'])
            st.success(f"Verified: **{full_name}**")
            st.info(f"You are authorized for **{ticket_count}** seats.")
            
            # Check for double booking
            already_seated_row = df[df['Guest_List'].str.contains(full_name, na=False)]
            
            if not already_seated_row.empty:
                assigned_table = already_seated_row.iloc[0]['Table_ID']
                st.warning(f"You are already at Table {assigned_table}")
            else:
                # 2. Only show booking options once name is selected
                df['Remaining'] = df['Capacity'] - df['Taken']
                valid_tables = df[df['Remaining'] >= ticket_count]
                
                if not valid_tables.empty:
                    selection = st.selectbox("Select a table with enough space:", valid_tables['Table_ID'])
                    if st.button("Confirm This Table", use_container_width=True, type="primary"):
                        # ... (Update logic remains the same)
                        idx = df[df['Table_ID'] == selection].index[0]
                        df.at[idx, 'Taken'] += ticket_count
                        current_list = str(df.at[idx, 'Guest_List']) if pd.notna(df.at[idx, 'Guest_List']) and df.at[idx, 'Guest_List'] != "nan" else ""
                        df.at[idx, 'Guest_List'] = current_list + f"{full_name} ({ticket_count}), "
                        conn.update(worksheet="Tables", data=df)
                        st.balloons()
                        st.rerun()
                else:
                    st.error("Sorry, no tables have enough room for your group.")
    else:
        # What they see before they "sign in"
        st.write("Please select your name to begin booking.")
