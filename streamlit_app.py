import streamlit as st
from streamlit_gsheets import GSheetsConnection
import plotly.express as px
import pandas as pd

# -----------------------------------------------------------------------------
# 1. PAGE CONFIGURATION
# This section sets up the "look" of the website in the browser tab.
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Grad 2026 Seating", 
    layout="wide", # Forces the app to use the full width of the screen
    page_icon="🎓"
)

# -----------------------------------------------------------------------------
# 2. DATABASE CONNECTION (GOOGLE SHEETS)
# This connects the app to your spreadsheet using the 'secrets' you provided.
# 'ttl=0' ensures the app fetches fresh data every time someone visits.
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
# This section allows any user to search the map.
# -----------------------------------------------------------------------------
st.markdown("### 🔍 Find a Guest")
search_query = st.text_input("Type a name to find their table:", placeholder="e.g. Smith")

if search_query:
    # --- SAFETY FIX ---
    # We force the Guest_List to be a string. This prevents the "AttributeError" 
    # if the column is empty in your Google Sheet.
    df['Guest_List'] = df['Guest_List'].astype(str)
    
    # Search for the name within the guest list string.
    results = df[df['Guest_List'].str.contains(search_query, case=False, na=False)]
    
    if not results.empty:
        for _, row in results.iterrows():
            st.success(f"✅ Found results at **Table {row['Table_ID']}**")
            with st.expander(f"See everyone at Table {row['Table_ID']}"):
                # We replace 'nan' with an empty string for a cleaner look if empty
                clean_list = row['Guest_List'].replace('nan', 'No guests yet')
                st.write(clean_list)
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
    last_names = sorted(student_df['Last Name'].unique().tolist())
    sel_last = st.selectbox("1. Your Last Name:", [""] + last_names)
    
    if sel_last:
        filtered_firsts = student_df[student_df['Last Name'] == sel_last]['First Name'].tolist()
        sel_first = st.selectbox("2. Your First Name:", [""] + filtered_firsts)
        
        if sel_first:
            # Look up the student's specific record
            student_info = student_df[
                (student_df['Last Name'] == sel_last) & 
                (student_df['First Name'] == sel_first)
            ].iloc[0]
            
            # --- STEP 2: SECURITY GATE (ACCESS CODE) ---
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
                
                # --- SAFETY FIX ---
                # Force Guest_List to string again here to prevent crash during the seated check.
                df['Guest_List'] = df['Guest_List'].astype(str)
                
                # Check if this student is already seated.
                already_seated = df[df['Guest_List'].str.contains(full_name, na=False)]
                
                if not already_seated.empty:
                    assigned_table = already_seated.iloc[0]['Table_ID']
                    st.warning(f"⚠️ Already assigned to **Table {assigned_table}**")
                    st.caption("Need a change? Contact the Grad Committee Admin.")
                else:
                    # CALCULATE SPACE: Fresh math using Capacity minus Taken.
                    df['Remaining'] = df['Capacity'] - df['Taken']
                    valid_tables = df[df['Remaining'] >= ticket_count]
                    
                    if not valid_tables.empty:
                        selection = st.selectbox("4. Choose an Available Table:", valid_tables['Table_ID'])
                        
                        if st.button("Confirm Seating", use_container_width=True, type="primary"):
                            idx = df[df['Table_ID'] == selection].index[0]
                            
                            # Update the 'Taken' count
                            df.at[idx, 'Taken'] += ticket_count
                            
                            # Append the name to the Guest List string
                            # We treat the current value as a string and handle 'nan' placeholders.
                            current_list = str(df.at[idx, 'Guest_List'])
                            if current_list == "nan" or current_list == "":
                                updated_list = f"{full_name} ({ticket_count})"
                            else:
                                updated_list = current_list + f", {full_name} ({ticket_count})"
                            
                            df.at[idx, 'Guest_List'] = updated_list
                            
                            # SAVE DATA TO GOOGLE SHEETS
                            conn.update(worksheet="Tables", data=df)
                            
                            st.success(f"Confirmed! Enjoy Table {selection}.")
                            st.balloons()
                            st.rerun() 
                    else:
                        st.error("No tables have enough space left.")
            elif user_input_code != "":
                st.error("❌ Incorrect Code.")

    # --- SIDEBAR ADMIN & SUPPORT ---
    st.sidebar.markdown("---")
    st.sidebar.caption("📊 **Admin Actions**")
    csv_data = df[['Table_ID', 'Capacity', 'Taken', 'Guest_List']].to_csv(index=False).encode('utf-8')
    st.sidebar.download_button(label="Download Seating List (CSV)", data=csv_data, file_name='grad_seating.csv', mime='text/csv')
    
    st.sidebar.markdown("---")
    st.sidebar.caption("📩 **Support & Contact**")
    st.sidebar.write("If your code doesn't work or you need a change, please email:")
    st.sidebar.info("gradcommittee@school.com") # <--- UPDATE THIS EMAIL

# -----------------------------------------------------------------------------
# 5. VISUAL MAP GENERATION (PLOTLY SCATTER)
# -----------------------------------------------------------------------------
st.markdown("### 🗺️ Room Layout")

# Recalculate 'Remaining' for map colors
df['Remaining'] = df['Capacity'] - df['Taken']

def get_status(row):
    if row['Remaining'] <= 0: return "🔴 Sold Out"
    if row['Remaining'] < 3: return "🟡 Nearly Full"
    return "🟢 Available"

df['Status'] = df.apply(get_status, axis=1)

# Generate the Map
fig = px.scatter(
    df, x='X', y='Y', text='Table_ID', color='Status',
    color_discrete_map={"🟢 Available": "#2ecc71", "🟡 Nearly Full": "#f1c40f", "🔴 Sold Out": "#e74c3c"},
    hover_name="Table_ID",
    hover_data={"Remaining": True, "Guest_List": True, "X": False, "Y": False}
)

fig.update_traces(
    marker=dict(size=60, sizemode='area', sizeref=0.1, line=dict(width=2, color='white')),
    textposition='middle center',
    textfont=dict(size=14, color="white")
)

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
# -----------------------------------------------------------------------------
with st.expander("Show Raw Seating Data (Table View)"):
    # Ensure guest list is clean for display
    display_df = df[['Table_ID', 'Remaining', 'Guest_List']].copy()
    display_df['Guest_List'] = display_df['Guest_List'].astype(str).replace('nan', '')
    st.dataframe(display_df, hide_index=True, use_container_width=True)
