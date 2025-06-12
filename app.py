
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

    # --- Filter Tanggal dan Event Status ---
    selected_date = st.date_input("Pilih Tanggal Cek Stok", value=pd.to_datetime("today"))
    status_options = ["All", "Temporary", "Permanent"]
    selected_event_status = st.selectbox("Filter Event Status", status_options)

    # --- Normalisasi & Persiapan Data ---
    df_event["Status"] = df_event["Status"].fillna("").str.lower().str.strip()
    df_event["Event Status"] = df_event["Event Status"].fillna("").str.lower().str.strip()
    df_stock["Status Device"] = df_stock["Status Device"].fillna("").str.lower().str.strip()

    # --- Filter Event Berdasarkan Tanggal & Status ---
    df_event["Event Start Date"] = pd.to_datetime(df_event["Event Start Date"])
    df_event["Event End Date"] = pd.to_datetime(df_event["Event End Date"])

    df_event_filtered = df_event[
        (df_event["Event Start Date"] <= pd.to_datetime(selected_date)) &
        (df_event["Event End Date"] >= pd.to_datetime(selected_date))
    ]

    if selected_event_status != "All":
        df_event_filtered = df_event_filtered[
            df_event_filtered["Event Status"] == selected_event_status.lower()
        ]

    # Kumpulan Status
    status_in_use = ["in use", "lost asset", "on progress of handover"]
    status_pending = ["on prepare", "reject", "", "waiting"]
    status_returned = ["returned"]

    # Hitung real per status dari sheet Event
    df_in_use = df_event_filtered[df_event_filtered["Status"].isin(status_in_use)]
    df_pending = df_event_filtered[df_event_filtered["Status"].isin(status_pending)]
    df_returned = df_event_filtered[df_event_filtered["Status"].isin(status_returned)]

    # Rekap tiap jenis
    used_summary = df_in_use[["Numbers of Tablet", "Numbers of Printer", "Numbers of Mobile POS (MPOS)"]].fillna(0).sum()
    pending_summary = df_pending[["Numbers of Tablet", "Numbers of Printer", "Numbers of Mobile POS (MPOS)"]].fillna(0).sum()
    returned_summary = df_returned[["Numbers of Tablet", "Numbers of Printer", "Numbers of Mobile POS (MPOS)"]].fillna(0).sum()

    # Semua stok dari All Device
    total_summary = df_stock.groupby("Type").size().to_dict()
    available_summary = df_stock[df_stock["Status Device"] == "available"].groupby("Type").size().to_dict()

    # Hitung Stok Ready dari Available + Returned - In Use
    stock_ready = {
        "Tablet": available_summary.get("Tablet", 0),
        "Printer": available_summary.get("Printer Bluetooth", 0),
        "Mobile POS": available_summary.get("Mobile POS", 0)
    }

    in_use = {
        "Tablet": used_summary.get("Numbers of Tablet", 0),
        "Printer": used_summary.get("Numbers of Printer", 0),
        "Mobile POS": used_summary.get("Numbers of Mobile POS (MPOS)", 0)
    }

    to_confirm = {
        "Tablet": pending_summary.get("Numbers of Tablet", 0),
        "Printer": pending_summary.get("Numbers of Printer", 0),
        "Mobile POS": pending_summary.get("Numbers of Mobile POS (MPOS)", 0)
    }

    stock_real = {
        "Tablet": stock_ready["Tablet"] - in_use["Tablet"],
        "Printer": stock_ready["Printer"] - in_use["Printer"],
        "Mobile POS": stock_ready["Mobile POS"] - in_use["Mobile POS"]
    }

    # --- Tampilkan Metrik ---
    col1, col2, col3 = st.columns(3)
    col1.metric("Tablet Ready", stock_real["Tablet"], delta=f"-{in_use['Tablet']} in use")
    col2.metric("Printer Ready", stock_real["Printer"], delta=f"-{in_use['Printer']} in use")
    col3.metric("MPOS Ready", stock_real["Mobile POS"], delta=f"-{in_use['Mobile POS']} in use")

    summary_data = pd.DataFrame({
    "Type": ["Mobile POS", "Printer Bluetooth", "Tablet"],
    "Total Device": [total_summary.get("Mobile POS", 0), total_summary.get("Printer Bluetooth", 0), total_summary.get("Tablet", 0)],
    "Available": [stock_ready["Mobile POS"], stock_ready["Printer"], stock_ready["Tablet"]],
    "In Use": [in_use["Mobile POS"], in_use["Printer"], in_use["Tablet"]],
    "To Be Confirm": [to_confirm["Mobile POS"], to_confirm["Printer"], to_confirm["Tablet"]]
    })

    st.subheader("📊 Ringkasan Jumlah Device")
    st.dataframe(summary_data, use_container_width=True)

    # --- Filter Tipe Device ---
    tipe_list = ["All"] + sorted(df_stock["Type"].dropna().unique())
    selected_type = st.selectbox("Filter berdasarkan Tipe Device", tipe_list)

    df_device_filtered = df_stock.copy()
    if selected_type != "All":
        df_device_filtered = df_device_filtered[df_device_filtered["Type"] == selected_type]

    # --- Tampilkan Daftar Device ---
    st.subheader("📋 Daftar Device")
    st.dataframe(df_device_filtered.reset_index(drop=True), use_container_width=True)
