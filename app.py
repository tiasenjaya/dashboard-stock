
import streamlit as st
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="Dashboard Stok Perangkat", layout="wide")

# URL Google Sheet CSV
URL_USED = "https://docs.google.com/spreadsheets/d/1nAPJdN6BJ1G2EHlcR0SnzIjcWCYycoLO6Dmki5IBp3Y/export?format=csv&gid=707408321"
URL_ALL = "https://docs.google.com/spreadsheets/d/1nAPJdN6BJ1G2EHlcR0SnzIjcWCYycoLO6Dmki5IBp3Y/export?format=csv&gid=957160817"


# Tombol Refresh (letakkan di paling awal halaman, sebelum data diload & sebelum tab)
if st.button("🔄 Refresh Data dari Google Sheet"):
    st.cache_data.clear()
    st.rerun()

@st.cache_data
def load_data():
    df_used = pd.read_csv(URL_USED)
    df_all = pd.read_csv(URL_ALL)
    return df_used, df_all

df_used, df_all = load_data()

# Normalisasi kolom
df_used['Status Device'] = df_used['Status Device'].str.strip().str.lower()
df_all['Status Device'] = df_all['Status Device'].str.strip().str.lower()

# Tabs
tab1, tab2 = st.tabs(["📦 Total Stok", "📅 Daftar Event"])

# ---------------------- TAB 1: STOK ----------------------
with tab1:
    st.header("📦 Informasi Stok Perangkat")

    df_ready = df_all[df_all['Status Device'] == 'available']
    df_in_use = df_used[df_used['Status Device'] == 'in use']
    df_confirm = df_used[df_used['Status Device'] == 'to be confirm']
    df_lost = df_used[df_used['Status Device'].str.lower() == "lost asset"]

    # Filter sidebar
    with st.container():
        st.subheader("🔍 Filter Perangkat")
        type_options = ["All"] + sorted(df_all['Type'].dropna().unique())
        selected_type = st.selectbox("Pilih Type", type_options, key="type_filter")

        if selected_type != "All":
            df_ready = df_ready[df_ready['Type'] == selected_type]
            df_in_use = df_in_use[df_in_use['Type'] == selected_type]
            df_confirm = df_confirm[df_confirm['Type'] == selected_type]
            df_lost = df_lost[df_lost['Type'] == selected_type]
            df_all_filtered = df_all[df_all['Type'] == selected_type]
        else:
            df_all_filtered = df_all

        # Metrik
        col1, col2, col3 = st.columns(3)
        col1.metric("Total Perangkat", len(df_all_filtered))
        col2.metric("Stok Ready", len(df_ready))
        col3.metric("Sedang Digunakan", len(df_in_use))

        with st.expander("🗂️ Status Device Lainnya", expanded=False):

            # Di dalam expander:
            st.markdown(f"**• To Be Confirm**: {len(df_confirm)}")
            show_confirm_detail = st.checkbox("Check for Detail", key="toggle_to_be_confirm")
            if show_confirm_detail and not df_confirm.empty:
                st.dataframe(
                    df_confirm[['Serial Number', 'Type', 'Model', 'Specification', 'Status Device']],
                    use_container_width=True
                )

            st.markdown(f"**• Lost Asset**: {len(df_lost)}")
            show_lost_detail = st.checkbox("Check for Detail", key="toggle_lost_asset")
            if show_lost_detail and not df_lost.empty:
                st.dataframe(
                    df_lost[['Serial Number', 'Type', 'Model', 'Specification', 'Status Device']],
                    use_container_width=True
                )

        # Tabel stok ready (tanpa cek tanggal)
        st.subheader("✅ Perangkat Ready Saat Ini")
        st.dataframe(df_ready, use_container_width=True)


# ---------------------- TAB 2: EVENT ----------------------
with tab2:
    st.header("📅 Daftar Event")
    df_event = df_used[df_used['Status Device'] == 'in use'].copy()
    st.markdown("### 📋 Daftar Event yang Sedang Berlangsung")

    # Filter hanya event aktif
    active_event_df = df_event[df_event['Status Event'].str.lower() == "on going"].copy()

    # Hitung jumlah perangkat per event
    event_summary = active_event_df.groupby(['Event', 'PIC'])['Serial Number'].count().reset_index()
    event_summary.rename(columns={'Serial Number': 'Jumlah Perangkat'}, inplace=True)

    # Hitung total perangkat & jumlah event
    total_event = event_summary['Event'].nunique()
    total_device = event_summary['Jumlah Perangkat'].sum()

    # Tampilkan ringkasan
    col1, col2 = st.columns(2)
    col1.metric("Jumlah Event Aktif", total_event)
    col2.metric("Total Perangkat Digunakan", total_device)

    # Opsional: tampilkan tabel detail jika ingin tetap terlihat
    st.markdown("### 📌 Detail Per Event")

    # Pilih event dari daftar event aktif
    selected_event_detail = st.selectbox(
        "Pilih Event untuk Lihat Detail Perangkat",
        event_summary["Event"].unique(),
        key="event_detail_select"
    )

    # Filter data perangkat berdasarkan event terpilih
    event_detail_df = active_event_df[active_event_df["Event"] == selected_event_detail]

    with st.expander("📋 Klik untuk lihat perangkat yang digunakan di event ini"):
        detail_cols = [
            'Type', 'Brand', 'Model', 'Specification', 'Serial Number',
            'Status Device', 'Status Event', 'Event End Date', 'PIC'
        ]
        st.dataframe(event_detail_df[detail_cols], use_container_width=True)


    # Filter event & tanggal
    with st.container():
        st.subheader("🔍 Filter Event")
        selected_pic = st.selectbox("Pilih PIC", ["All"] + sorted(df_used['PIC'].dropna().unique()), key="pic_filter")  

    # Konversi tanggal kolom ke datetime dulu (penting!)
    df_event['Event End Date'] = pd.to_datetime(df_event['Event End Date'], errors='coerce')

    if selected_pic != "All":
        df_event = df_event[df_event['PIC'] == selected_pic]

    event_cols = [
        'Type', 'Brand', 'Model', 'Specification', 'Serial Number',
        'Status Device', 'Status Event', 'Event', 'Event End Date', 'PIC'
    ]
    st.dataframe(df_event[event_cols], use_container_width=True)
