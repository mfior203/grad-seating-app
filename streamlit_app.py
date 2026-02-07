import streamlit as st
from streamlit_gsheets import GSheetsConnection
import plotly.express as px
import pandas as pd

st.set_page_config(page_title="Grad 2026 Seating", layout="wide", page_icon="🎓")

conn = st.connection("gsheets", type=GSheetsConnection)

# --- LOAD DATA ---
df = conn.read(worksheet="Tables", ttl=0)
student_df = conn.read(worksheet="Students", ttl=0)

st.title("🎓 Grade 12 Graduation Seating")

# --- SIDEBAR: AUTHENTICATION & BOOKING ---
with st.sidebar:
    st.header("🎫 Find Your Name")
    
    # 1. Select Last Name first (makes searching 200+ people easier)
    last_names = sorted(student_df['Last Name'].unique().tolist())
    sel_last = st.selectbox("Your Last Name:", [""] + last_names)
    
    if sel_last:
        # 2. Filter first names based on the selected last name
        filtered_firsts = student_df[student_df['Last Name'] == sel_last]['First Name'].tolist()
        sel_first = st.selectbox("Your First Name:", [""] + filtered_firsts)
        
        if sel_first:
            # Full Name for the guest list
            full_name = f"{sel_first} {sel_last}"
            
            # 3. Pull ticket count
            student_info = student_df[(student_df['Last Name'] == sel_last) & (student_df['First Name'] == sel_first)].iloc[0]
            ticket_count = int(student_info['Tickets'])
            
            st.info(f"Welcome {sel_first}. You have **{ticket_count}** tickets.")
            
            # 4. Check if already seated
            is_already_seated = df['Guest_List'].str.contains(full_name, na=False).any()
            
            if is_already_seated:
                st.warning("You have already selected a table!")
            else:
                # 5. Table Selection
                df['Remaining'] = df['Capacity'] - df['Taken']
                valid_tables = df[df['Remaining'] >= ticket_count]
                
                if not valid_tables.empty:
                    selection = st.selectbox("Choose a table:", valid_tables['Table_ID'])
                    if st.button("Confirm Table", use_container_width=True, type="primary"):
                        idx = df[df['Table_ID'] == selection].index[0]
                        df.at[idx, 'Taken'] += ticket_count
                        
                        current_list = str(df.at[idx, 'Guest_List']) if pd.notna(df.at[idx, 'Guest_List']) else ""
                        df.at[idx, 'Guest_List'] = current_list + f"{full_name} ({ticket_count}), "
                        
                        conn.update(worksheet="Tables", data=df)
                        st.success(f"Confirmed! See you at Table {selection}.")
                        st.balloons()
                        st.rerun()
                else:
                    st.error("No tables have enough space!")

# --- VISUAL MAP ---
def get_status(row):
    rem = row['Capacity'] - row['Taken']
    if rem <= 0: return "🔴 Sold Out"
    if rem < 3: return "🟡 Nearly Full"
    return "🟢 Available"

df['Status'] = df.apply(get_status, axis=1)

fig = px.scatter(df, x='X', y='Y', text='Table_ID', size=[20]*len(df),
                 color='Status',
                 color_discrete_map={"🟢 Available": "#2ecc71", "🟡 Nearly Full": "#f1c40f", "🔴 Sold Out": "#e74c3c"},
                 hover_name="Table_ID",
                 hover_data={"Remaining": True, "Guest_List": True})

fig.update_traces(textposition='middle center', marker=dict(line=dict(width=2, color='white')))
fig.update_layout(xaxis_visible=False, yaxis_visible=False, height=600, margin=dict(l=0,r=0,b=0,t=40))
st.plotly_chart(fig, use_container_width=True)
