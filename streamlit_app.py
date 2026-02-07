import streamlit as st
from streamlit_gsheets import GSheetsConnection
import plotly.express as px
import pandas as pd

st.set_page_config(page_title="Grad 2026 Seating", layout="wide", page_icon="🎓")

# Connect to Google Sheets
conn = st.connection("gsheets", type=GSheetsConnection)

# --- LOAD DATA ---
df = conn.read(worksheet="Tables", ttl=0)
student_df = conn.read(worksheet="Students", ttl=0)

st.title("🎓 Grade 12 Graduation Seating")

# --- TOP SECTION: FIND A FRIEND ---
st.markdown("### 🔍 Find a Guest")
search_query = st.text_input("Type a name to see where they are sitting:", placeholder="e.g. Smith")

if search_query:
    # Look through the Guest_List column for the search term
    results = df[df['Guest_List'].str.contains(search_query, case=False, na=False)]
    if not results.empty:
        for _, row in results.iterrows():
            st.success(f"✅ Found '{search_query}' at **Table {row['Table_ID']}**")
    else:
        st.warning("No one by that name has selected a table yet.")

st.divider()

# --- SIDEBAR: SECURE BOOKING ---
with st.sidebar:
    st.header("🎫 Reserve Your Table")
    
    # Select Last Name
    last_names = sorted(student_df['Last Name'].unique().tolist())
    sel_last = st.selectbox("Your Last Name:", [""] + last_names)
    
    if sel_last:
        # Filter First Names
        filtered_firsts = student_df[student_df['Last Name'] == sel_last]['First Name'].tolist()
        sel_first = st.selectbox("Your First Name:", [""] + filtered_firsts)
        
        if sel_first:
            full_name = f"{sel_first} {sel_last}"
            student_info = student_df[(student_df['Last Name'] == sel_last) & (student_df['First Name'] == sel_first)].iloc[0]
            ticket_count = int(student_info['Tickets'])
            
            st.info(f"Welcome {sel_first}. You have **{ticket_count}** tickets.")
            
            # Check for double booking
            is_already_seated = df['Guest_List'].str.contains(full_name, na=False).any()
            
            if is_already_seated:
                st.warning("⚠️ You are already assigned to a table!")
            else:
                df['Remaining'] = df['Capacity'] - df['Taken']
                valid_tables = df[df['Remaining'] >= ticket_count]
                
                if not valid_tables.empty:
                    selection = st.selectbox("Choose a table:", valid_tables['Table_ID'])
                    if st.button("Confirm Seating", use_container_width=True, type="primary"):
                        idx = df[df['Table_ID'] == selection].index[0]
                        df.at[idx, 'Taken'] += ticket_count
                        
                        current_list = str(df.at[idx, 'Guest_List']) if pd.notna(df.at[idx, 'Guest_List']) else ""
                        df.at[idx, 'Guest_List'] = current_list + f"{full_name} ({ticket_count}), "
                        
                        conn.update(worksheet="Tables", data=df)
                        st.success(f"Success! Enjoy the banquet.")
                        st.balloons()
                        st.rerun()
                else:
                    st.error("No tables have enough space left for your party.")

# --- VISUAL MAP ---
st.markdown("### 🗺️ Room Layout")

def get_status(row):
    rem = row['Capacity'] - row['Taken']
    if rem <= 0: return "🔴 Sold Out"
    if rem < 3: return "🟡 Nearly Full"
    return "🟢 Available"

df['Status'] = df.apply(get_status, axis=1)

# Change the number "size=[xx]" to change diameter of table
fig = px.scatter(df, x='X', y='Y', text='Table_ID', size=[105]*len(df),
                 color='Status',
                 color_discrete_map={"🟢 Available": "#2ecc71", "🟡 Nearly Full": "#f1c40f", "🔴 Sold Out": "#e74c3c"},
                 hover_name="Table_ID",
                 hover_data={"Remaining": True, "Guest_List": True, "X": False, "Y": False})

fig.update_traces(textposition='middle center', marker=dict(line=dict(width=2, color='white')), textfont=dict(size=14, color="white"))
fig.update_layout(xaxis_visible=False, yaxis_visible=False, height=600, margin=dict(l=0,r=0,b=0,t=0))

st.plotly_chart(fig, use_container_width=True)

# Expander for full list
with st.expander("Show All Seating Details"):
    st.dataframe(df[['Table_ID', 'Remaining', 'Guest_List']], hide_index=True)
