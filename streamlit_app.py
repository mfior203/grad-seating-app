import streamlit as st
from streamlit_gsheets import GSheetsConnection
import plotly.express as px
import pandas as pd

# -----------------------------------------------------------------------------
# 1. PAGE SETUP
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Grad 2026 Seating", 
    layout="wide", 
    page_icon="🎓"
)

# -----------------------------------------------------------------------------
# 2. DATABASE CONNECTION
# This links to your Google Sheet using the secrets in your Streamlit dashboard.
# -----------------------------------------------------------------------------
conn = st.connection("gsheets", type=GSheetsConnection)

# Fetch data from both tabs. 'ttl=0' ensures we don't show old, cached bookings.
df = conn.read(worksheet="Tables", ttl=0)
student_df = conn.read(worksheet="Students", ttl=0)

st.title("🎓 Grade 12 Graduation Seating")
st.markdown("Find your friends on the map and log in via the sidebar to pick your table.")

# -----------------------------------------------------------------------------
# 3. PUBLIC SEARCH (TOP OF THE PAGE)
# Allows anyone to see where a friend is sitting without needing a password.
# -----------------------------------------------------------------------------
st.markdown("### 🔍 Find a Guest")
search_query = st.text_input("Search for a friend's name:", placeholder="Start typing a name...")

if search_query:
    # Look for the typed name within the 'Guest_List' column of our spreadsheet
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
# This section handles student verification and the actual seat reservation.
# -----------------------------------------------------------------------------
with st.sidebar:
    st.header("🎫 Reserve Your Table")
    
    # STEP 1: Select Name
    # We sort last names alphabetically to make them easier to find.
    last_names = sorted(student_df['Last Name'].unique().tolist())
    sel_last = st.selectbox("1. Select Last Name:", [""] + last_names)
    
    if sel_last:
        # Filter first names based on the chosen last name
        filtered_firsts = student_df[student_df['Last Name'] == sel_last]['First Name'].tolist()
        sel_first = st.selectbox("2. Select First Name:", [""] + filtered_firsts)
        
        if sel_first:
            # Look up this student's specific row in the Student sheet
            student_info = student_df[
                (student_df['Last Name'] == sel_last) & 
                (student_df['First Name'] == sel_first)
            ].iloc[0]
            
            # STEP 2: SECURITY GATE
            # Asks for the Access_Code from your Google Sheet. type="password" hides input.
            # We use a unique 'key' and a custom label to discourage browser autofill
            user_code = st.text_input(
            "3. Verification Code:", 
            type="password", 
            key="user_access_code_gate", # Unique key stops some browsers from remembering
            help="Enter the code provided on your ticket receipt.",
            autocomplete="new-password" # Signals to the browser NOT to suggest old passwords
            )

            
            # Check if user input matches the code in the spreadsheet
            if str(user_code) == str(student_info['Access_Code']):
                st.success("Identity Verified!")
                full_name = f"{sel_first} {sel_last}"
                ticket_count = int(student_info['Tickets'])
                st.info(f"You have **{ticket_count}** tickets.")
                
                # STEP 3: PREVENT DOUBLE BOOKING
                # Checks if the name is already written in any table's guest list.
                already_seated_row = df[df['Guest_List'].str.contains(full_name, na=False)]
                
                if not already_seated_row.empty:
                    assigned_table = already_seated_row.iloc[0]['Table_ID']
                    st.warning(f"⚠️ You are already at **Table {assigned_table}**")
                    st.write("---")
                    st.caption("Contact the Grad Committee to move your group.")
                else:
                    # STEP 4: FILTER TABLES BY CAPACITY
                    # We calculate remaining seats here to ensure math is always 100% correct.
                    df['Remaining'] = df['Capacity'] - df['Taken']
                    valid_tables = df[df['Remaining'] >= ticket_count]
                    
                    if not valid_tables.empty:
                        selection = st.selectbox("4. Choose a table with space:", valid_tables['Table_ID'])
                        
                        if st.button("Confirm Seating", use_container_width=True, type="primary"):
                            # Find the table index and update 'Taken' and 'Guest_List'
                            idx = df[df['Table_ID'] == selection].index[0]
                            df.at[idx, 'Taken'] += ticket_count
                            
                            # Clean up Guest_List string to avoid 'nan' values
                            current_list = str(df.at[idx, 'Guest_List']) if pd.notna(df.at[idx, 'Guest_List']) and df.at[idx, 'Guest_List'] != "nan" else ""
                            df.at[idx, 'Guest_List'] = current_list + f"{full_name} ({ticket_count}), "
                            
                            # SYNC TO GOOGLE SHEETS
                            conn.update(worksheet="Tables", data=df)
                            st.success(f"Reserved! See you at Table {selection}.")
                            st.balloons()
                            st.rerun() # Refresh to update the map
                    else:
                        st.error("No tables have enough space left.")
            elif user_code != "":
                st.error("❌ Incorrect Access Code.")

    # --- SIDEBAR FOOTER ---
    st.sidebar.markdown("---")
    # ADMIN DOWNLOAD: Allows the committee to grab the final list for the banquet hall.
    st.sidebar.caption("📊 **Admin Tools**")
    csv_data = df[['Table_ID', 'Capacity', 'Taken', 'Guest_List']].to_csv(index=False).encode('utf-8')
    st.sidebar.download_button(label="Download Seating List", data=csv_data, file_name='grad_seating.csv', mime='text/csv')
    
    st.sidebar.markdown("---")
    st.sidebar.caption("📩 **Support**")
    st.sidebar.write("For seating changes, contact:")
    st.sidebar.write("Grad Committee Admin")

# -----------------------------------------------------------------------------
# 5. VISUAL MAP GENERATION
# -----------------------------------------------------------------------------
st.markdown("### 🗺️ Room Layout")

# Final Math Check for Map Colors
df['Remaining'] = df['Capacity'] - df['Taken']

def get_status(row):
    if row['Remaining'] <= 0: return "🔴 Sold Out"
    if row['Remaining'] < 3: return "🟡 Nearly Full"
    return "🟢 Available"

df['Status'] = df.apply(get_status, axis=1)

# Generate the Scatter Plot
fig = px.scatter(
    df, x='X', y='Y', text='Table_ID',
    color='Status',
    # Colors: Green for good, Yellow for low, Red for none.
    color_discrete_map={"🟢 Available": "#2ecc71", "🟡 Nearly Full": "#f1c40f", "🔴 Sold Out": "#e74c3c"},
    hover_name="Table_ID",
    hover_data={"Remaining": True, "Guest_List": True, "X": False, "Y": False}
)

# ADJUST CIRCLE SIZE HERE:
# 'size' = diameter. 'sizeref' = scale (lower numbers make circles BIGGER).
fig.update_traces(
    marker=dict(size=60, sizemode='area', sizeref=0.1, line=dict(width=2, color='white')),
    textposition='middle center',
    textfont=dict(size=14, color="white")
)

# Layout Setup: Set the height and hide the X/Y axes for a clean "map" look.
fig.update_layout(
    xaxis=dict(range=[df['X'].min() - 1, df['X'].max() + 1], visible=False),
    yaxis=dict(range=[df['Y'].min() - 1, df['Y'].max() + 1], visible=False),
    height=800,
    margin=dict(l=10, r=10, t=10, b=10),
    legend_title_text='Table Status'
)

st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

# -----------------------------------------------------------------------------
# 6. DETAILED LIST (OPTIONAL VIEW)
# -----------------------------------------------------------------------------
with st.expander("Show Detailed Seating List (Table View)"):
    display_df = df[['Table_ID', 'Remaining', 'Guest_List']].copy()
    st.dataframe(display_df, hide_index=True, use_container_width=True)
