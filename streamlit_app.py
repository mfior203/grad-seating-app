import streamlit as st
from streamlit_gsheets import GSheetsConnection
import plotly.express as px
import pandas as pd

# -----------------------------------------------------------------------------
# 1. PAGE CONFIGURATION
# This section sets the browser tab title and the overall layout.
# Change 'page_title' to update what appears on the browser tab.
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Grad 2026 Seating", 
    layout="wide", # Uses the full width of the screen
    page_icon="🎓"
)

# -----------------------------------------------------------------------------
# 2. DATABASE CONNECTION
# This connects the app to your Google Sheet.
# 'ttl=0' ensures that the app fetches fresh data every time someone visits.
# -----------------------------------------------------------------------------
conn = st.connection("gsheets", type=GSheetsConnection)

# Read the two tabs from your Google Sheet.
# Make sure your tabs are named EXACTLY "Tables" and "Students".
df = conn.read(worksheet="Tables", ttl=0)
student_df = conn.read(worksheet="Students", ttl=0)

st.title("🎓 Grade 12 Graduation Seating")
st.markdown("Use the map to find friends. Use the sidebar to log in and reserve your seats.")

# -----------------------------------------------------------------------------
# 3. PUBLIC SEARCH (FIND A FRIEND)
# This allows anyone to search the guest lists without logging in.
# -----------------------------------------------------------------------------
st.markdown("### 🔍 Find a Guest")
search_query = st.text_input("Type a name to find their table:", placeholder="e.g. Smith")

if search_query:
    # This looks through the 'Guest_List' column for the text typed above.
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
# This handles student verification and updating the Google Sheet.
# -----------------------------------------------------------------------------
with st.sidebar:
    st.header("🎫 Reserve Your Table")
    
    # --- STEP 1: Name Selection ---
    # Pulls unique last names from your 'Students' tab.
    last_names = sorted(student_df['Last Name'].unique().tolist())
    sel_last = st.selectbox("1. Your Last Name:", [""] + last_names)
    
    if sel_last:
        # Filters first names based on the chosen last name.
        filtered_firsts = student_df[student_df['Last Name'] == sel_last]['First Name'].tolist()
        sel_first = st.selectbox("2. Your First Name:", [""] + filtered_firsts)
        
        if sel_first:
            # Look up the student's record (Ticket count & Access Code)
            student_info = student_df[
                (student_df['Last Name'] == sel_last) & 
                (student_df['First Name'] == sel_first)
            ].iloc[0]
            
            # --- STEP 2: SECURITY GATE (ACCESS CODE) ---
            # '.strip()' removes accidental spaces. 
            # 'autocomplete="new-password"' helps block annoying browser popups.
            user_input_code = st.text_input(
                "3. Enter Access Code:", 
                type="password", 
                autocomplete="new-password"
            ).strip() 
            
            # GOOGLE SHEETS FIX:
            # Sheets often turns '1234' into '1234.0'. '.split('.')[0]' removes the decimal.
            correct_code = str(student_info['Access_Code']).strip().split('.')[0]
            
            # --- STEP 3: VERIFICATION & BOOKING ---
            if user_input_code == correct_code and user_input_code != "":
                st.success("Identity Verified!")
                full_name = f"{sel_first} {sel_last}"
                ticket_count = int(student_info['Tickets'])
                st.info(f"Welcome {sel_first}. You have **{ticket_count}** tickets.")
                
                # Check if this student's name is already in a guest list.
                already_seated = df[df['Guest_List'].str.contains(full_name, na=False)]
                
                if already_seated.empty:
                    # CALCULATE SPACE: Fresh math (Capacity minus Taken).
                    df['Remaining'] = df['Capacity'] - df['Taken']
                    
                    # Only show tables that have enough room for the group.
                    valid_tables = df[df['Remaining'] >= ticket_count]
                    
                    if not valid_tables.empty:
                        selection = st.selectbox("4. Choose an Available Table:", valid_tables['Table_ID'])
                        
                        if st.button("Confirm Seating", use_container_width=True, type="primary"):
                            # Find the row index for the chosen table.
                            idx = df[df['Table_ID'] == selection].index[0]
                            
                            # Add the student's ticket count to 'Taken'.
                            df.at[idx, 'Taken'] += ticket_count
                            
                            # Format the Guest List text string.
                            current_list = str(df.at[idx, 'Guest_List']) if pd.notna(df.at[idx, 'Guest_List']) and df.at[idx, 'Guest_List'] != "nan" else ""
                            df.at[idx, 'Guest_List'] = current_list + f"{full_name} ({ticket_count}), "
                            
                            # SAVE TO GOOGLE SHEETS
                            conn.update(worksheet="Tables", data=df)
                            
                            st.success(f"Confirmed! Enjoy Table {selection}.")
                            st.balloons()
                            st.rerun() # Refresh to show the new seating on the map.
                    else:
                        st.error("No tables have enough space left.")
                else:
                    assigned_table = already_seated.iloc[0]['Table_ID']
                    st.warning(f"⚠️ You are already at **Table {assigned_table}**")
            elif user_input_code != "":
                st.error("❌ Incorrect Code.")

    # --- SIDEBAR ADMIN TOOLS ---
    st.sidebar.markdown("---")
    st.sidebar.caption("📊 **Admin Actions**")
    # Generates a CSV file for the committee to print or open in Excel.
    csv_data = df[['Table_ID', 'Capacity', 'Taken', 'Guest_List']].to_csv(index=False).encode('utf-8')
    st.sidebar.download_button(label="Download Seating CSV", data=csv_data, file_name='grad_seating.csv', mime='text/csv')
    
    # --- SUPPORT CONTACT ---
    st.sidebar.markdown("---")
    st.sidebar.caption("📩 **Support & Contact**")
    st.sidebar.write("If your code doesn't work or you need to change your seat, please email:")
    # UPDATE THIS EMAIL TO YOURS
    st.sidebar.info("gradcommittee@school.com")

# -----------------------------------------------------------------------------
# 5. VISUAL MAP GENERATION (PLOTLY)
# Draws the room layout based on X and Y coordinates in the spreadsheet.
# -----------------------------------------------------------------------------
st.markdown("### 🗺️ Room Layout")

# Force calculate the status for circle colors.
df['Remaining'] = df['Capacity'] - df['Taken']

def get_status(row):
    # Controls the color based on availability.
    if row['Remaining'] <= 0: return "🔴 Sold Out"
    if row['Remaining'] < 3: return "🟡 Nearly Full"
    return "🟢 Available"

df['Status'] = df.apply(get_status, axis=1)

# Generate the Map Plot
fig = px.scatter(
    df, x='X', y='Y', text='Table_ID', 
    color='Status',
    # Color Map: Green (#2ecc71), Yellow (#f1c40f), Red (#e74c3c).
    color_discrete_map={"🟢 Available": "#2ecc71", "🟡 Nearly Full": "#f1c40f", "🔴 Sold Out": "#e74c3c"},
    hover_name="Table_ID",
    # Controls what appears when a user hovers their mouse over a circle.
    hover_data={"Remaining": True, "Guest_List": True, "X": False, "Y": False}
)

# VISUAL STYLING:
# 'size' = diameter. 'sizeref' = scale (Lower = Larger circles).
fig.update_traces(
    marker=dict(size=60, sizemode='area', sizeref=0.1, line=dict(width=2, color='white')),
    textposition='middle center',
    textfont=dict(size=14, color="white")
)

# Layout Setup: Hide axes and set the map height.
fig.update_layout(
    xaxis=dict(range=[df['X'].min() - 1, df['X'].max() + 1], visible=False),
    yaxis=dict(range=[df['Y'].min() - 1, df['Y'].max() + 1], visible=False),
    height=800,
    margin=dict(l=10, r=10, t=10, b=10),
    legend_title_text='Table Status'
)

st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

# -----------------------------------------------------------------------------
# 6. TEXT LIST VIEW
# A backup table view at the bottom of the page.
# -----------------------------------------------------------------------------
with st.expander("Show Raw Seating Data (Table View)"):
    st.dataframe(df[['Table_ID', 'Remaining', 'Guest_List']], hide_index=True, use_container_width=True)
