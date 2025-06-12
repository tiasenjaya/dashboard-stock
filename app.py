
import streamlit as st
import pandas as pd
from urllib.parse import quote

# --- CONFIG ---
st.set_page_config(page_title="Monitoring Stock Device Event", layout="wide")

if st.button("🔄 Refresh Data"):
    st.cache_data.clear()
    st.rerun()

# --- LOAD DATA ---
@st.cache_data
def load_data():
    sheet_id = "1nAPJdN6BJ1G2EHlcR0SnzIjcWCYycoLO6Dmki5IBp3Y"
    sheet_event = quote("List Event")
    sheet_stock = quote("All Device")

    url_event = f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&sheet={sheet_event}"
    url_stock = f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&sheet={sheet_stock}"

    df_event = pd.read_csv(url_event)
    df_stock = pd.read_csv(url_stock)
    return df_event, df_stock

df_event, df_stock = load_data()

# --- CLEAN & TRANSFORM ---
df_event.columns = df_event.columns.str.strip()
df_event = df_event.loc[:, ~df_event.columns.str.contains("^Unnamed")]

# Ganti Status kosong jadi Waiting
df_event["Status"] = df_event["Status"].fillna("Waiting")

# Total Device
df_event["Total Device"] = df_event[
    ["Numbers of Tablet", "Numbers of Printer", "Numbers of Mobile POS (MPOS)"]
].fillna(0).sum(axis=1)

# --- TAB LAYOUT ---
tab1, tab2 = st.tabs(["📋 Monitoring Event", "📦 Status Stok Device"])

with tab1:
    st.header("📋 Monitoring Pengajuan Event")

    # Pilih PIC
    pic_list = sorted(df_event["Email Address"].dropna().unique())
    selected_pic = st.selectbox("Pilih Nama PIC (Sales)", pic_list)
    user_data = df_event[df_event["Email Address"] == selected_pic]

    if user_data.empty:
        st.info("Belum ada pengajuan untuk PIC ini.")
    else:
        # Buat indeks unik sebagai ID dropdown
        user_data = user_data.reset_index(drop=True)
        event_options = list(enumerate(user_data["Event Name"].tolist()))
        selected_pair = st.selectbox("Pilih Pengajuan Event", options=event_options, format_func=lambda x: x[1])
        selected_index = selected_pair[0]  # Ambil indeksnya

        # Ambil baris tepat berdasarkan index
        selected_row = user_data.iloc[selected_index]

        # Layout Ringkasan
        st.subheader("📌 Ringkasan Pengajuan")
        col1, col2, col3 = st.columns(3)
        col1.markdown(f"<div style='font-size:30px; font-weight:bold'>Event<br><span style='font-weight:normal'>{selected_row['Event Name']}</span></div>", unsafe_allow_html=True)
        col2.markdown(f"<div style='font-size:30px; font-weight:bold'>Lokasi<br><span style='font-weight:normal'>{selected_row['Event Location']}</span></div>", unsafe_allow_html=True)
        col3.markdown(f"<div style='font-size:30px; font-weight:bold'>Status<br><span style='font-weight:normal'>{selected_row['Status']}</span></div>", unsafe_allow_html=True)
        st.markdown("")
        col4, col5, col6 = st.columns(3)
        col4.markdown(f"<div style='font-size:30px; font-weight:bold'>Start Event<br><span style='font-weight:normal'>{str(selected_row['Event Start Date'])}</span></div>", unsafe_allow_html=True)
        col5.markdown(f"<div style='font-size:30px; font-weight:bold'>End Event<br><span style='font-weight:normal'>{str(selected_row['Event End Date'])}</span></div>", unsafe_allow_html=True)
        col6.markdown(f"<div style='font-size:30px; font-weight:bold'>Total Device<br><span style='font-weight:normal'>{int(selected_row['Total Device'])}</span></div>", unsafe_allow_html=True)

        # Buat email tampil tanpa hyperlink
        username, domain = selected_pic.split("@")
        domain_obfuscated = domain.replace(".", " [dot] ")
        email_display = selected_pic.replace("@", "&#8203;@").replace(".", "&#8203;.")

        st.markdown("---")
        st.markdown(
            f"<b>📄 Riwayat Semua Pengajuan oleh</b> <span style='color:black'>{email_display}</span>",
            unsafe_allow_html=True
        )

        st.dataframe(user_data.reset_index(drop=True), use_container_width=True)

# --- TAB 2: STOK DEVICE ---
with tab2:
    st.header("📦 Status Stok Device")

    # Pilih tanggal pengecekan stok
    selected_date = st.date_input("Pilih Tanggal Cek Stok")

    # Hitung total device READY dari All Device
    df_ready = df_stock[df_stock["Status Device"] == "Ready"]
    total_per_type = df_ready["Type"].value_counts()

    df_event["Event Start Date"] = pd.to_datetime(df_event["Event Start Date"])
    df_event["Event End Date"] = pd.to_datetime(df_event["Event End Date"])

    # Hitung device yang sedang digunakan berdasarkan List Event
    df_event_filtered = df_event[
        (df_event["Event Start Date"] <= pd.to_datetime(selected_date)) &
        (df_event["Event End Date"] >= pd.to_datetime(selected_date))
    ]

    in_use = {
        "Tablet": df_event_filtered["Numbers of Tablet"].fillna(0).sum(),
        "Printer": df_event_filtered["Numbers of Printer"].fillna(0).sum(),
        "Mobile POS (MPOS)": df_event_filtered["Numbers of Mobile POS (MPOS)"].fillna(0).sum()
    }

    stock_ready = {
        tipe: total_per_type.get(tipe, 0) - in_use.get(tipe, 0)
        for tipe in ["Tablet", "Printer", "Mobile POS (MPOS)"]
    }

    # Tampilkan ringkasan stok berdasarkan hasil hitung
    col1, col2, col3 = st.columns(3)
    col1.metric("Tablet Ready", stock_ready["Tablet"], delta=f"-{in_use['Tablet']} in use")
    col2.metric("Printer Ready", stock_ready["Printer"], delta=f"-{in_use['Printer']} in use")
    col3.metric("MPOS Ready", stock_ready["Mobile POS (MPOS)"], delta=f"-{in_use['Mobile POS (MPOS)']} in use")

    st.markdown("---")

    # Tabel rekap jumlah total device dari df_stock
    st.subheader("📊 Ringkasan Jumlah Device")
    summary = df_stock.groupby(["Type", "Status Device"]).size().unstack(fill_value=0)
    st.dataframe(summary, use_container_width=True)

    # Filter berdasarkan tipe device
    tipe_list = ["All"] + sorted(df_stock["Type"].dropna().unique())
    selected_type = st.selectbox("Filter berdasarkan Tipe Device", tipe_list)

    df_device_filtered = df_stock.copy()
    if selected_type != "All":
        df_device_filtered = df_device_filtered[df_device_filtered["Type"] == selected_type]

    # Pewarnaan status device
    def highlight_device_status(row):
        status = str(row["Status Device"]).lower()
        if "ready" in status:
            return ['background-color: #d4edda'] * len(row)
        elif "in use" in status:
            return ['background-color: #fff3cd'] * len(row)
        elif "broken" in status or "maintenance" in status:
            return ['background-color: #f8d7da'] * len(row)
        return [''] * len(row)

    st.subheader("📋 Daftar Device")
    st.dataframe(df_device_filtered.style.apply(highlight_device_status, axis=1), use_container_width=True)
