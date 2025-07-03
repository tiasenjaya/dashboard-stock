import streamlit as st
import pandas as pd
from urllib.parse import quote

# === CONFIG ===
st.set_page_config(page_title="Monitoring Stock Device Event", layout="wide")

if st.button("🔄 Refresh Data"):
    st.cache_data.clear()
    st.rerun()


# === 1. LOAD DATA ===
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


# === 2. PREPROCESS DATA ===
def preprocess_data(df_event, df_stock):
    df_event.columns = df_event.columns.str.strip()
    df_event = df_event.loc[:, ~df_event.columns.str.contains("^Unnamed")]
    df_event["Status"] = df_event["Status"].fillna("Waiting")
    df_event["Total Device"] = df_event[
        ["Numbers of Tablet", "Numbers of Printer", "Numbers of Mobile POS (MPOS)"]
    ].fillna(0).sum(axis=1)
    return df_event, df_stock


# === 3. RENDER TAB 1 ===
def render_tab1_monitoring_event(df_event):
    st.header("📋 Monitoring Pengajuan Event")

    pic_list = sorted(df_event["Email Address"].dropna().unique())
    selected_pic = st.selectbox("Pilih Nama PIC (Sales)", pic_list)
    user_data = df_event[df_event["Email Address"] == selected_pic]

    if user_data.empty:
        st.info("Belum ada pengajuan untuk PIC ini.")
    else:
        user_data = user_data.reset_index(drop=True)
        event_names = user_data["Event Name"].dropna().tolist()
        event_options = list(enumerate(event_names))

        if event_options:
            selected_pair = st.selectbox("Pilih Pengajuan Event", options=event_options, format_func=lambda x: x[1])
            selected_index = selected_pair[0]
            selected_row = user_data.iloc[selected_index]

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

            username, domain = selected_pic.split("@")
            email_display = selected_pic.replace("@", "&#8203;@").replace(".", "&#8203;.")
            st.markdown("---")
            st.markdown(f"<b>📄 Riwayat Semua Pengajuan oleh</b> <span style='color:black'>{email_display}</span>", unsafe_allow_html=True)
            st.dataframe(user_data.reset_index(drop=True), use_container_width=True)
        else:
            st.warning("PIC ini belum memiliki nama event yang valid.")


# === 4. RENDER TAB 2 ===
def render_tab2_status_stok(df_event, df_stock):
    st.header("📦 Status Stok Device")

    status_mode = st.radio(
    "Pilih Mode Device",
    ["Device Temporary", "Device Permanent"],
    horizontal=True
    )

    # Bersihkan data stok
    df_stock = df_stock[df_stock["Type"].notna()]
    df_stock["Status Device"] = df_stock["Status Device"].astype(str).str.lower().str.strip()
    df_stock["Type"] = df_stock["Type"].astype(str).str.strip()

    if status_mode == "Device Temporary":
        df_stock = df_stock[~df_stock["Status Device"].str.contains("used permanently")]
    else:
        df_stock = df_stock[df_stock["Status Device"].str.contains("used permanently")]

    # Hitung total perangkat
    total_summary = df_stock.groupby("Type").size().rename("Total Device")

    # Hitung jumlah berdasarkan setiap Status Device
    status_pivot = (
        df_stock
        .groupby(["Type", "Status Device"])
        .size()
        .unstack(fill_value=0)  # otomatis semua status akan jadi kolom
    )

    # Gabungkan total + pivot status
    summary_data = pd.concat([total_summary, status_pivot], axis=1).fillna(0).astype(int).reset_index()

    # Hitung metrik ready dan in use
    if status_mode == "Device Permanent":
        permanent_summary = status_pivot.get("used permanently", {})
        tablet_ready = permanent_summary.get("Tablet", 0)
        printer_ready = permanent_summary.get("Printer Bluetooth", 0)
        mpos_ready = permanent_summary.get("Mobile POS", 0)
        
        # Tetap definisikan variabel *_in_use agar tidak error
        tablet_in_use = 0
        printer_in_use = 0
        mpos_in_use = 0
    else:
        available_summary = status_pivot.get("available", {})
        in_use_summary = status_pivot.get("in use", {})

        tablet_ready = available_summary.get("Tablet", 0)
        printer_ready = available_summary.get("Printer Bluetooth", 0)
        mpos_ready = available_summary.get("Mobile POS", 0)

        tablet_in_use = in_use_summary.get("Tablet", 0)
        printer_in_use = in_use_summary.get("Printer Bluetooth", 0)
        mpos_in_use = in_use_summary.get("Mobile POS", 0)

    total_devices = total_summary.sum()

    # Metrik
    col0, col1, col2, col3 = st.columns(4)
    col0.metric("Total Device", total_devices)
    col1.metric("Tablet Ready", tablet_ready, f"-{tablet_in_use} in use", delta_color="inverse")
    col2.metric("Printer Ready", printer_ready, f"-{printer_in_use} in use", delta_color="inverse")
    col3.metric("MPOS Ready", mpos_ready, f"-{mpos_in_use} in use", delta_color="inverse")

    # Tampilkan tabel ringkasan
    st.subheader("📊 Ringkasan Jumlah Device")
    st.dataframe(summary_data, use_container_width=True)

# === 5. MAIN ===
def main():
    df_event, df_stock = load_data()
    df_event, df_stock = preprocess_data(df_event, df_stock)

    tab1, tab2 = st.tabs(["📋 Monitoring Event", "📦 Status Stok Device"])
    with tab1:
        render_tab1_monitoring_event(df_event)
    with tab2:
        render_tab2_status_stok(df_event.copy(), df_stock.copy())

if __name__ == "__main__":
    main()
