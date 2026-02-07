import streamlit as st
from streamlit_gsheets import GSheetsConnection
import plotly.express as px
import pandas as pd

# -----------------------------------------------------------------------------
# 1. PAGE CONFIGURATION
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Grad 2026 Seating", 
    layout="wide", 
    page_icon="🎓"
)

# -----------------------------------------------------------------------------
# 2. DATABASE CONNECTION
# This connects to the Google Sheet using the 'secrets' you linked in Streamlit.
# -----------------------------------------------------------------------------
conn = st.connection("gsheets", type=GSheetsConnection)

# Fetch fresh data. 'ttl=0' means the app doesn't cache old data—it's always live.
df = conn.read(worksheet="Tables", ttl=0)
student_df = conn.read(worksheet="Students", ttl=0)

st.title("🎓 Grade 12 Graduation Seating")
st.markdown("Use the map to find friends. Use the sidebar to log in and reserve your seats.")

# -----------------------------------------------------------------------------
# 3. PUBLIC SEARCH (TOP OF PAGE)
# -----------------------------------------------------------------------------
st.markdown("### 🔍 Find a Guest")
search_query = st.text_input("Type a name to find their table:", placeholder="e.g. Smith")

if search_query:
    # Look through the 'Guest_List' column for the search term
    results = df[df['Guest_List'].str.contains(search_query, case=False, na=False)]
    if not results.empty:
        for _, row in results.iterrows():
            st.success(f"✅ Found at **Table {row['Table_ID']}**")
            with st.expander(f"See who's at Table {row['Table_ID']}"):
                st.write(row['Guest_List'])
    else:
        st.warning("No one found by that name yet.")

st.divider()

# -----------------------------------------------------------------------------
# 4. SIDEBAR: SECURE BOOKING SYSTEM
# -----------------------------------------------------------------------------
with st.sidebar:
    st.header("🎫 Reserve Your Table")
    
    # STEP 1: Name Selection
    last_names = sorted(student_df['Last Name'].unique().tolist())
    sel_last = st.selectbox("1. Your Last Name:", [""] + last_names)
    
    if sel_last:
        filtered_firsts = student_df[student_df['Last Name'] == sel_last]['First Name'].tolist()
        sel_first = st.selectbox("2. Your First Name:", [""] + filtered_firsts)
        
        if sel_first:
            # Look up the specific student row
            student_info = student_df[
                (student_df['Last Name'] == sel_last) & 
                (student_df['First Name'] == sel_first)
            ].iloc[0]
            
            # STEP 2: SECURE ACCESS CODE GATE
            # We use 'autocomplete="new-password"' to discourage annoying browser autofill popups.
            user_input_code = st.text_input(
                "3. Enter Access Code:", 
                type="password", 
                autocomplete="new-password"
            ).strip() # .strip() removes accidental spaces at the start/end
            
            # DATA CLEANING:
            # We convert the Google Sheet code to a string and use .split('.')[0]
            # This prevents '1234' from being read as '1234.0' (a common Google Sheets/Python error).
            correct_code = str(student_info['Access_Code']).strip().split('.')[0]
            
            if user_input_code == correct_code and user_input_code != "":
                st.success("Identity Verified!")
                full_name = f"{sel_first} {sel_last}"
                ticket_count = int(student_info['Tickets'])
                st.info(f"Welcome {sel_first}. You have **{ticket_count}** tickets.")
                
                # Check if this name is already seated somewhere
                already_seated = df[df['Guest_List'].str.contains(full_name, na=False)]
                
                if not already_seated.empty:
                    assigned_table = already_seated.iloc[0]['Table_ID']
                    st.warning(f"⚠️ Already assigned to **Table {assigned_table}**")
                    st.caption("Contact the committee for changes.")
                else:
                    # STEP 3: TABLE SELECTION (BASED ON LIVE MATH)
                    # We recalculate 'Remaining' here to ensure the logic is fresh.
                    df['Remaining'] = df['Capacity'] - df['Taken']
                    valid_tables = df[df['Remaining'] >= ticket_count]
                    
                    if not valid_tables.empty:
                        selection = st.selectbox("4. Choose a Table:", valid_tables['Table_ID'])
                        
                        if st.button("Confirm Seating", use_container_width=True, type="primary"):
                            # Update the dataframe locally
                            idx = df[df['Table_ID'] == selection].index[0]
                            df.at[idx, 'Taken'] += ticket_count
                            
                            # Clean up the guest list text
                            current_list = str(df.at[idx, 'Guest_List']) if pd.notna(df.at[idx, 'Guest_List']) and df.at[idx, 'Guest_List'] != "nan" else ""
                            df.at[idx, 'Guest_List'] = current_list + f"{full_name} ({ticket_count}), "
                            
                            # SYNC TO GOOGLE SHEETS
                            conn.update(worksheet="Tables", data=df)
                            st.success(f"Confirmed! See you at Table {selection}.")
                            st.balloons()
                            st.rerun()
                    else:
                        st.error("No tables have enough space left.")
            elif user_input_code != "":
                st.error("❌ Incorrect Code.")

    # --- SIDEBAR FOOTER ---
    st.sidebar.markdown("---")
    st.sidebar.caption("📊 **Admin Actions**")
    # This creates a CSV file of the current seating for the Committee.
    csv_data = df[['Table_ID', 'Capacity', 'Taken', 'Guest_List']].to_csv(index=False).encode('utf-8')
    st.sidebar.download_button(label="Download Seating CSV", data=csv_data, file_name='grad_seating.csv', mime='text/csv')
    
    st.sidebar.markdown("---")
    st.sidebar.caption("📩 **Support**")
    st.sidebar.write("Issues? Contact the Grad Committee Admin.")

# -----------------------------------------------------------------------------
# 5. VISUAL MAP GENERATION (PLOTLY)
# -----------------------------------------------------------------------------
st.markdown("### 🗺️ Room Layout")

# Force calculate the status for colors
df['Remaining'] = df['Capacity'] - df['Taken']

def get_status(row):
    if row['Remaining'] <= 0: return "🔴 Sold Out"
    if row['Remaining'] < 3: return "🟡 Nearly Full"
    return "🟢 Available"

df['Status'] = df.apply(get_status, axis=1)

# Build the scatter plot map
fig = px.scatter(
    df, x='X', y='Y', text='Table_ID',
    color='Status',
    color_discrete_map={"🟢 Available": "#2ecc71", "🟡 Nearly Full": "#f1c40f", "🔴 Sold Out": "#e74c3c"},
    hover_name="Table_ID",
    hover_data={"Remaining": True, "Guest_List": True, "X": False, "Y": False}
)

# STYLING:
# 'size' and 'sizeref' control the diameter of the circles. 
# Decrease 'sizeref' to make circles larger.
fig.update_traces(
    marker=dict(size=60, sizemode='area', sizeref=0.1, line=dict(width=2, color='white')),
    textposition='middle center',
    textfont=dict(size=14, color="white")
)

# CLEANUP: Remove axes and set height
fig.update_layout(
    xaxis=dict(range=[df['X'].min() - 1, df['X'].max() + 1], visible=False),
    yaxis=dict(range=[df['Y'].min() - 1, df['Y'].max() + 1], visible=False),
    height=800,
    margin=dict(l=10, r=10, t=10, b=10),
    legend_title_text='Status'
)

st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

# -----------------------------------------------------------------------------
# 6. TEXT LIST VIEW
# -----------------------------------------------------------------------------
with st.expander("Show Raw Seating Data"):
    st.dataframe(df[['Table_ID', 'Remaining', 'Guest_List']], hide_index=True, use_container_width=True)
