import streamlit as st
from streamlit_gsheets import GSheetsConnection
import plotly.express as px
import pandas as pd

# Set page to wide mode and add a title
st.set_page_config(page_title="Grad 2026 Seating", layout="wide", page_icon="🎓")

# 1. --- DATABASE CONNECTION ---
conn = st.connection("gsheets", type=GSheetsConnection)

# Load data with ttl=0 to ensure real-time updates
df = conn.read(worksheet="Tables", ttl=0)
student_df = conn.read(worksheet="Students", ttl=0)

st.title("🎓 Grade 12 Graduation Seating")
st.markdown("Use this map to find your friends and reserve your table for the banquet.")

# 2. --- TOP SECTION: FIND A FRIEND ---
st.markdown("### 🔍 Find a Guest")
search_query = st.text_input("Type a name to see where they are sitting:", placeholder="e.g. Smith")

if search_query:
    results = df[df['Guest_List'].str.contains(search_query, case=False, na=False)]
    if not results.empty:
        for _, row in results.iterrows():
            st.success(f"✅ Results found at **Table {row['Table_ID']}**")
            with st.expander(f"See Guest List for Table {row['Table_ID']}"):
                st.write(row['Guest_List'])
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
            
            # Get ticket count for student
            student_info = student_df[(student_df['Last Name'] == sel_last) & (student_df['First Name'] == sel_first)].iloc[0]
            ticket_count = int(student_info['Tickets'])
            
            st.info(f"Welcome {sel_first}! You have **{ticket_count}** tickets.")
            
            # CHECK IF ALREADY SEATED
            already_seated_row = df[df['Guest_List'].str.contains(full_name, na=False)]
            
            if not already_seated_row.empty:
                assigned_table = already_seated_row.iloc[0]['Table_ID']
                st.warning(f"⚠️ You are already assigned to **Table {assigned_table}**")
                st.write("---")
                st.caption("**Need to change tables?**")
                st.write("Please contact the Grad Committee to reset your seat.")
            else:
                # Show tables that have enough seats left
                df['Remaining'] = df['Capacity'] - df['Taken']
                valid_tables = df[df['Remaining'] >= ticket_count]
                
                if not valid_tables.empty:
                    selection = st.selectbox("Choose a table:", valid_tables['Table_ID'])
                    if st.button("Confirm Seating", use_container_width=True, type="primary"):
                        idx = df[df['Table_ID'] == selection].index[0]
                        df.at[idx, 'Taken'] += ticket_count
                        
                        current_list = str(df.at[idx, 'Guest_List']) if pd.notna(df.at[idx, 'Guest_List']) and df.at[idx, 'Guest_List'] != "nan" else ""
                        df.at[idx, 'Guest_List'] = current_list + f"{full_name} ({ticket_count}), "
                        
                        conn.update(worksheet="Tables", data=df)
                        st.success(f"Success! Table {selection} reserved.")
                        st.balloons()
                        st.rerun()
                else:
                    st.error("No tables have enough space left.")

    # --- SIDEBAR FOOTER & EXPORT ---
    st.sidebar.markdown("---")
    
    # Simple Export Tool for Admins
    st.sidebar.caption("📊 **Admin Export**")
    csv = df[['Table_ID', 'Capacity', 'Taken', 'Guest_List']].to_csv(index=False).encode('utf-8')
    st.sidebar.download_button(
        label="Download Seating List (CSV)",
        data=csv,
        file_name='grad_seating_final.csv',
        mime='text/csv',
    )
    
    st.sidebar.markdown("---")
    st.sidebar.caption("📩 **Support / Contact**")
    st.sidebar.write("For changes, contact:")
    st.sidebar.write("Grad Committee Admin")
    st.sidebar.write("[your.email@example.com]")

# 4. --- VISUAL MAP SECTION ---
st.markdown("### 🗺️ Room Layout")

def get_status(row):
    rem = row['Capacity'] - row['Taken']
    if rem <= 0: return "🔴 Sold Out"
    if rem < 3: return "🟡 Nearly Full"
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

# Adjust table size
fig.update_traces(
    marker=dict(
        size=60, 
        sizemode='area', 
        sizeref=0.1, 
        line=dict(width=2, color='white')
    ),
    textposition='middle center',
    textfont=dict(size=14, color="white")
)

# Set the "room" boundaries
fig.update_layout(
    xaxis=dict(range=[df['X'].min() - 1, df['X'].max() + 1], visible=False),
    yaxis=dict(range=[df['Y'].min() - 1, df['Y'].max() + 1], visible=False),
    height=800,
    margin=dict(l=10, r=10, t=10, b=10),
    legend_title_text='Table Status'
)

st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

# 5. --- LIST VIEW ---
with st.expander("Show Detailed Seating List"):
    display_df = df[['Table_ID', 'Remaining', 'Guest_List']].copy()
    st.dataframe(display_df, hide_index=True, use_container_width=True)
