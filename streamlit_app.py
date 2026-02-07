import streamlit as st
from streamlit_gsheets import GSheetsConnection
import plotly.express as px
import pandas as pd

# -----------------------------------------------------------------------------
# 1. PAGE CONFIGURATION
# This section sets up the "look" of the website in the browser tab.
# Edit 'page_title' to change the name on the tab.
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Grad 2026 Seating", 
    layout="wide", # Forces the app to use the full width of the screen
    page_icon="🎓"
)

# -----------------------------------------------------------------------------
# 2. DATABASE CONNECTION (GOOGLE SHEETS)
# This connects the app to your spreadsheet using the 'secrets' you provided.
# 'ttl=0' is CRITICAL: It tells the app to fetch a fresh copy of the data
# every single time the page refreshes. Without this, users see old data.
# -----------------------------------------------------------------------------
conn = st.connection("gsheets", type=GSheetsConnection)

# Read the two tabs from your Google Sheet.
# Ensure your tabs are named EXACTLY "Tables" and "Students".
df = conn.read(worksheet="Tables", ttl=0)
student_df = conn.read(worksheet="Students", ttl=0)

st.title("🎓 Grade 12 Graduation Seating")
st.markdown("Use the map to find friends. Use the sidebar to log in and reserve your seats.")

# -----------------------------------------------------------------------------
# 3. PUBLIC SEARCH (FIND A FRIEND)
# This section allows any user (even without a code) to search the map.
# -----------------------------------------------------------------------------
st.markdown("### 🔍 Find a Guest")
search_query = st.text_input("Type a name to find their table:", placeholder="e.g. Smith")

if search_query:
    # This line looks through the 'Guest_List' column for the text typed above.
    # 'case=False' makes it so 'SMITH' and 'smith' both work.
    results = df[df['Guest_List'].str.contains(search_query, case=False, na=False)]
    
    if not results.empty:
        for _, row in results.iterrows():
            st.success(f"✅ Found results at **Table {row['Table_ID']}**")
            with st.expander(f"See everyone at Table {row['Table_ID']}"):
                st.write(row['Guest_List'])
    else:
        st.warning("No one found by that name yet.")

st.divider()

# -----------------------------------------------------------------------------
# 4. SIDEBAR: THE SECURE BOOKING SYSTEM
# This handles the "Sign-In" logic and the writing of data to your spreadsheet.
# -----------------------------------------------------------------------------
with st.sidebar:
    st.header("🎫 Reserve Your Table")
    
    # --- STEP 1: Name Selection ---
    # last_names pulls unique names from your 'Students' tab.
    last_names = sorted(student_df['Last Name'].unique().tolist())
    sel_last = st.selectbox("1. Your Last Name:", [""] + last_names)
    
    if sel_last:
        # Once a last name is picked, this filters the list for matching first names.
        filtered_firsts = student_df[student_df['Last Name'] == sel_last]['First Name'].tolist()
        sel_first = st.selectbox("2. Your First Name:", [""] + filtered_firsts)
        
        if sel_first:
            # Look up the student's specific record (Ticket count & Access Code)
            student_info = student_df[
                (student_df['Last Name'] == sel_last) & 
                (student_df['First Name'] == sel_first)
            ].iloc[0]
            
            # --- STEP 2: SECURITY GATE (ACCESS CODE) ---
            # 'strip()' removes accidental spaces.
            # 'autocomplete="new-password"' helps stop browser autofill popups.
            user_input_code = st.text_input(
                "3. Enter Access Code:", 
                type="password", 
                autocomplete="new-password"
            ).strip() 
            
            # MATH FIX: Sheets often reads '1234' as '1234.0'.
            # 'split('.')[0]' removes the decimal so it matches the user's input.
            correct_code = str(student_info['Access_Code']).strip().split('.')[0]
            
            # --- STEP 3: VERIFICATION & BOOKING ---
            if user_input_code == correct_code and user_input_code != "":
                st.success("Identity Verified!")
                full_name = f"{sel_first} {sel_last}"
                ticket_count = int(student_info['Tickets'])
                st.info(f"Welcome {sel_first}. You have **{ticket_count}** tickets.")
                
                # Check if this student is already seated in the 'Guest_List' column.
                already_seated = df[df['Guest_List'].str.contains(full_name, na=False)]
                
                if not already_seated.empty:
                    assigned_table = already_seated.iloc[0]['Table_ID']
                    st.warning(f"⚠️ Already assigned to **Table {assigned_table}**")
                    st.caption("Need a change? Contact the Grad Committee Admin.")
                else:
                    # CALCULATE SPACE: Fresh math using Capacity minus Taken.
                    df['Remaining'] = df['Capacity'] - df['Taken']
                    # Only show tables that have enough room for the student's group size.
                    valid_tables = df[df['Remaining'] >= ticket_count]
                    
                    if not valid_tables.empty:
                        selection = st.selectbox("4. Choose an Available Table:", valid_tables['Table_ID'])
                        
                        if st.button("Confirm Seating", use_container_width=True, type="primary"):
                            # Find the row index for the chosen table
                            idx = df[df['Table_ID'] == selection].index[0]
                            
                            # Update the 'Taken' count
                            df.at[idx, 'Taken'] += ticket_count
                            
                            # Append the name to the Guest List string
                            # We handle 'nan' to ensure the text stays clean in the sheet.
                            current_list = str(df.at[idx, 'Guest_List']) if pd.notna(df.at[idx, 'Guest_List']) and df.at[idx, 'Guest_List'] != "nan" else ""
                            df.at[idx, 'Guest_List'] = current_list + f"{full_name} ({ticket_count}), "
                            
                            # SAVE DATA TO GOOGLE SHEETS
                            conn.update(worksheet="Tables", data=df)
                            
                            st.success(f"Confirmed! Enjoy Table {selection}.")
                            st.balloons()
                            st.rerun() # Refresh page to show updated map
                    else:
                        st.error("No tables have enough space left for your party.")
            elif user_input_code != "":
                st.error("❌ Incorrect Code. Please try again.")

    # --- SIDEBAR ADMIN TOOLS ---
    st.sidebar.markdown("---")
    st.sidebar.caption("📊 **Admin Actions**")
    # This button generates a CSV from the live data for easy printing/Excel use.
    csv_data = df[['Table_ID', 'Capacity', 'Taken', 'Guest_List']].to_csv(index=False).encode('utf-8')
    st.sidebar.download_button(label="Download Seating List (CSV)", data=csv_data, file_name='grad_seating.csv', mime='text/csv')
    
    st.sidebar.markdown("---")
    st.sidebar.caption("📩 **Support**")
    st.sidebar.write("For seating changes or lost codes, contact the Grad Committee.")

# -----------------------------------------------------------------------------
# 5. VISUAL MAP GENERATION (PLOTLY SCATTER)
# This section draws the circles based on the X and Y coordinates in your sheet.
# -----------------------------------------------------------------------------
st.markdown("### 🗺️ Room Layout")

# Force calculate the status for circle colors.
df['Remaining'] = df['Capacity'] - df['Taken']

def get_status(row):
    # This logic controls the color of the circles.
    if row['Remaining'] <= 0: return "🔴 Sold Out"
    if row['Remaining'] < 3: return "🟡 Nearly Full"
    return "🟢 Available"

df['Status'] = df.apply(get_status, axis=1)

# Generate the Map
fig = px.scatter(
    df, x='X', y='Y', 
    text='Table_ID', # Shows the table number inside the circle
    color='Status',
    # Colors: Green (#2ecc71), Yellow (#f1c40f), Red (#e74c3c).
    color_discrete_map={"🟢 Available": "#2ecc71", "🟡 Nearly Full": "#f1c40f", "🔴 Sold Out": "#e74c3c"},
    hover_name="Table_ID",
    # hover_data controls what people see when they mouse over a table.
    hover_data={"Remaining": True, "Guest_List": True, "X": False, "Y": False}
)

# --- VISUAL STYLING ---
# size: Controls circle diameter.
# sizeref: Scaling factor. Lower = Bigger circles (e.g., 0.08 is very large).
fig.update_traces(
    marker=dict(size=60, sizemode='area', sizeref=0.1, line=dict(width=2, color='white')),
    textposition='middle center',
    textfont=dict(size=14, color="white")
)

# Layout: Hides the grid lines and axes for a cleaner "room layout" look.
fig.update_layout(
    xaxis=dict(range=[df['X'].min() - 1, df['X'].max() + 1], visible=False),
    yaxis=dict(range=[df['Y'].min() - 1, df['Y'].max() + 1], visible=False),
    height=800, # Adjust this to make the map taller or shorter on screen
    margin=dict(l=10, r=10, t=10, b=10),
    legend_title_text='Table Status'
)

st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

# -----------------------------------------------------------------------------
# 6. DETAILED LIST (TABLE VIEW)
# This is a backup view at the bottom of the page for quick reading.
# -----------------------------------------------------------------------------
with st.expander("Show Raw Seating Data (Table View)"):
    st.dataframe(df[['Table_ID', 'Remaining', 'Guest_List']], hide_index=True, use_container_width=True)
