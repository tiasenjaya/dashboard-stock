import streamlit as st
import pandas as pd
from urllib.parse import quote
from datetime import date

st.set_page_config(page_title="Monitoring Stock Device Event", layout="wide")

if st.button("🔄 Refresh Data"):
    st.cache_data.clear()
    st.rerun()

@st.cache_data
def load_data():
    sheet_id = "1nAPJdN6BJ1G2EHlcR0SnzIjcWCYycoLO6Dmki5IBp3Y"
    sheet_event = quote("List Event")
    sheet_temp = quote("Device Used Temporary")
    sheet_perm = quote("Device Used Permanently")

    url_event = f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&sheet={sheet_event}"
    url_temp = f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&sheet={sheet_temp}"
    url_perm = f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&sheet={sheet_perm}"

    df_event = pd.read_csv(url_event)
    df_temp_stock = pd.read_csv(url_temp)
    df_perm_stock = pd.read_csv(url_perm)

    return df_event, df_temp_stock, df_perm_stock

def preprocess_data(df_event, df_temp_stock, df_perm_stock):
    df_event.columns = df_event.columns.str.strip()
    df_event = df_event.loc[:, ~df_event.columns.str.contains("^Unnamed")]
    df_event["Status"] = df_event["Status"].fillna("Waiting")
    df_event["Total Device"] = df_event[
        ["Numbers of Tablet", "Numbers of Printer", "Numbers of Mobile POS (MPOS)"]
    ].fillna(0).sum(axis=1)
    return df_event, df_temp_stock, df_perm_stock

def count_stock(df_stock, tipe):
    df = df_stock[df_stock["Type"].str.lower().str.strip() == tipe]
    return df.shape[0]


def device_name(dev):
    mapping = {
        "tablet": "Numbers of Tablet",
        "printer bluetooth": "Numbers of Printer",
        "mobile pos": "Numbers of Mobile POS (MPOS)"
    }
    return mapping.get(dev, dev)

def count_ready_device(df_stock, df_event, selected_date, device_type, view_option):
    stok = df_stock[df_stock["Type"].str.lower() == device_type.lower()]
    jumlah_stok = stok.shape[0]

    selected_date = pd.to_datetime(selected_date).date()
    df_event = df_event.copy()
    df_event["Event Start Date"] = pd.to_datetime(df_event["Event Start Date"], errors="coerce")
    df_event["Event End Date"] = pd.to_datetime(df_event["Event End Date"], errors="coerce")
    df_event["Status"] = df_event["Status"].astype(str).str.strip().str.lower()
    df_event["Event Status"] = df_event["Event Status"].astype(str).str.strip().str.lower()

    aktif = (
        df_event["Event Start Date"].notna() &
        df_event["Event End Date"].notna() &
        (df_event["Event Start Date"].dt.date <= selected_date) &
        (df_event["Event End Date"].dt.date >= selected_date) &
        (df_event["Status"].isin(["in use", "on prepare"]))
    )

    if view_option.lower() in ["temporary stock", "permanent stock"]:
        aktif &= df_event["Event Status"].str.lower() == view_option.lower().replace(" stock", "")

    df_aktif = df_event[aktif]

    kolom_event = {
        "tablet": "Numbers of Tablet",
        "printer bluetooth": "Numbers of Printer",
        "mobile pos": "Numbers of Mobile POS (MPOS)"
    }[device_type.lower()]

    jumlah_dipakai = df_aktif[kolom_event].sum()
    return jumlah_stok - jumlah_dipakai


def calculate_stock_summary(df_event, df_temp_stock, df_perm_stock, selected_date, view_option):
    # Gabung data stok jika All Stock
    if view_option == "All Stock":
        df_stock = pd.concat([df_temp_stock, df_perm_stock], ignore_index=True)
    elif view_option == "Temporary Stock":
        df_stock = df_temp_stock.copy()
    else:  # Permanent Stock
        df_stock = df_perm_stock.copy()

    # Perhitungan ready per jenis device
    ready_tablet = count_ready_device(df_stock, df_event, selected_date, "tablet", view_option)
    ready_printer = count_ready_device(df_stock, df_event, selected_date, "printer bluetooth", view_option)
    ready_mpos = count_ready_device(df_stock, df_event, selected_date, "mobile pos", view_option)

    # Simpan hasil
    stock_summary = {
        "tablet": {"ready": ready_tablet},
        "printer bluetooth": {"ready": ready_printer},
        "mobile pos": {"ready": ready_mpos},
        "total_device": ready_tablet + ready_printer + ready_mpos
    }

    # Untuk keperluan analisis lanjut
    selected_date = pd.to_datetime(selected_date).date()
    df_event["Event Start Date"] = pd.to_datetime(df_event["Event Start Date"], errors="coerce")
    df_event["Event End Date"] = pd.to_datetime(df_event["Event End Date"], errors="coerce")
    df_event["Status"] = df_event["Status"].astype(str).str.strip().str.lower()
    df_event["Event Status"] = df_event["Event Status"].astype(str).str.strip().str.lower()

    is_active = (
        df_event["Event Start Date"].notna() &
        df_event["Event End Date"].notna() &
        (df_event["Event Start Date"].dt.date <= selected_date) &
        (df_event["Event End Date"].dt.date >= selected_date) &
        (df_event["Status"].isin(["in use", "on prepare"]))
    )

    df_event_active = df_event[is_active].copy()
    df_temp = df_event_active[df_event_active["Event Status"] == "temporary"]
    df_perm = df_event_active[df_event_active["Event Status"] == "permanent"]
    
    # Tambahan data jika masih membutuhkan struktur total_temp dan used_temp per device
    stock_summary["tablet"].update({
        "total_temp": df_temp_stock[df_temp_stock["Type"].str.lower() == "tablet"].shape[0],
        "used_temp": df_temp["Numbers of Tablet"].sum(),
        "total_perm": df_perm_stock[df_perm_stock["Type"].str.lower() == "tablet"].shape[0],
        "used_perm": df_perm["Numbers of Tablet"].sum()
    })

    stock_summary["printer bluetooth"].update({
        "total_temp": df_temp_stock[df_temp_stock["Type"].str.lower() == "printer bluetooth"].shape[0],
        "used_temp": df_temp["Numbers of Printer"].sum(),
        "total_perm": df_perm_stock[df_perm_stock["Type"].str.lower() == "printer bluetooth"].shape[0],
        "used_perm": df_perm["Numbers of Printer"].sum()
    })

    stock_summary["mobile pos"].update({
        "total_temp": df_temp_stock[df_temp_stock["Type"].str.lower() == "mobile pos"].shape[0],
        "used_temp": df_temp["Numbers of Mobile POS (MPOS)"].sum(),
        "total_perm": df_perm_stock[df_perm_stock["Type"].str.lower() == "mobile pos"].shape[0],
        "used_perm": df_perm["Numbers of Mobile POS (MPOS)"].sum()
    })

    return stock_summary, df_event_active, df_temp, df_perm

def render_tab1_monitoring_event(df_event):
    st.header("📋 Monitoring Pengajuan Event")
    mode = st.radio("Tampilkan Event berdasarkan:", ["Status Event", "Filter by Event", "Filter by PIC"], horizontal=True)
    df_event["Event Start Date"] = pd.to_datetime(df_event["Event Start Date"], errors="coerce")
    df_event["Event End Date"] = pd.to_datetime(df_event["Event End Date"], errors="coerce")
    df_event = df_event.replace(r'^\s*$', pd.NA, regex=True)
    df_event = df_event.dropna(subset=["Event Name", "Event Location"], how="all")

    if mode == "Status Event":
        status_list = df_event["Status"].dropna().unique().tolist()
        status_filter = st.selectbox("Filter berdasarkan Status Event", ["All"] + status_list)
        if status_filter != "All":
            df_event = df_event[df_event["Status"] == status_filter]
        df_event = df_event.sort_values("Event Start Date", ascending=False)
        st.markdown("### 📋 Detail Event")
        cols = st.columns(2)
        for i, (_, row) in enumerate(df_event.iterrows()):
            col = cols[i % 2]
            with col:
                st.markdown(f"""
                    <div style="border:1px solid #ccc; border-radius:10px; padding:15px; margin-bottom:10px; background-color:#f9f9f9;">
                        <b>📧 PIC:</b> {row.get('Email Address', '-') }<br>
                        <b>🎯 Event:</b> {row.get('Event Name', '-') }<br>
                        <b>📍 Lokasi:</b> {row.get('Event Location', '-') }<br>
                        <b>📅 Start:</b> {row.get('Event Start Date', '-') }<br>
                        <b>📅 End:</b> {row.get('Event End Date', '-') }
                    </div>
                """, unsafe_allow_html=True)

    elif mode == "Filter by Event":
        list_event = df_event["Event Name"].dropna().unique().tolist()
        selected_event = st.selectbox("Pilih Event", sorted(list_event))
        df_selected = df_event[df_event["Event Name"] == selected_event]
        if not df_selected.empty:
            row = df_selected.iloc[0]
            col1, col2, col3 = st.columns(3)
            col1.metric("PIC", row.get("Email Address", "-"))
            col1.metric("Event Name", row.get("Event Name", "-"))
            col1.metric("Total Device", int(row.get("Total Device", 0)))
            
            col2.metric("Location", row.get("Event Location", "-"))
            start_date = row.get("Event Start Date")
            start_date = start_date.strftime("%Y-%m-%d") if isinstance(start_date, pd.Timestamp) else str(start_date)
            col2.metric("Start", start_date)

            col3.metric("Status", row.get("Status", "-"))
            end_date = row.get("Event End Date")
            end_date = end_date.strftime("%Y-%m-%d") if isinstance(end_date, pd.Timestamp) else str(end_date)
            col3.metric("End", end_date)
        else:
            st.warning("Event tidak ditemukan.")

    else:
        pic_list = sorted(df_event["Email Address"].dropna().unique())
        selected_pic = st.selectbox("Pilih Nama PIC (Sales)", pic_list)
        user_data = df_event[df_event["Email Address"] == selected_pic]
        if user_data.empty:
            st.warning("PIC ini belum memiliki nama event yang valid.")
        else:
            selected_event = st.selectbox("Pilih Event", user_data["Event Name"].dropna().tolist())
            selected_row = user_data[user_data["Event Name"] == selected_event].iloc[0]
            col1, col2, col3 = st.columns(3)
            col1.metric("Event", selected_row.get("Event Name", "-"))
            col2.metric("Lokasi", selected_row.get("Event Location", "-"))
            col3.metric("Status", selected_row.get("Status", "-"))

            start_date = selected_row.get("Event Start Date")
            if isinstance(start_date, pd.Timestamp):
                start_date = start_date.strftime("%Y-%m-%d")
            col1.metric("Start", start_date)

            end_date = selected_row.get("Event End Date")
            if isinstance(end_date, pd.Timestamp):
                end_date = end_date.strftime("%Y-%m-%d")
            col2.metric("End", end_date)

            col3.metric("Total Device", int(selected_row.get("Total Device", 0)))
            st.dataframe(user_data.reset_index(drop=True), use_container_width=True)

def render_tab2_status_stok(df_event, df_temp_stock, df_perm_stock):
    st.header("📊 Status Stok Device")

    with st.expander("❓ Apa yang dimaksud dengan Device Temporary dan Permanent?", expanded=True):
        st.markdown("""
        - **Temporary**: Perangkat yang digunakan untuk kebutuhan jangka pendek (event sementara). Cocok untuk dilihat jika Anda ingin mengecek **ketersediaan stok yang bisa dipakai dalam waktu dekat**.
        - **Permanent**: Perangkat yang dialokasikan untuk kebutuhan jangka panjang dan **tidak akan kembali ke stok dalam waktu dekat** (misalnya: digunakan di lokasi tetap atau event permanen).
        """)

    view_option = st.radio("Pilih jenis device yang ingin dicek:", ["Temporary Stock", "Permanent Stock", "All Stock"], horizontal=True)
    selected_date = st.date_input("Pilih tanggal pengecekan:", date.today())

    # Tambahkan setelah pemilihan filter & tanggal
    #st.write("📊 Distribusi Tipe di Device Temporary:")
    #st.write(df_temp_stock["Type"].value_counts())

    #st.write("📊 Distribusi Tipe di Device Permanent:")
    #st.write(df_perm_stock["Type"].value_counts())

    stock_summary, df_event_active, df_temp_event, df_perm_event = calculate_stock_summary(
        df_event, df_temp_stock, df_perm_stock, selected_date, view_option
    )

    st.subheader("📈 Ringkasan Stok Ready")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Device", int(stock_summary["total_device"]))
    col2.metric("Tablet Ready", int(stock_summary["tablet"]["ready"]))
    col3.metric("Printer Bluetooth Ready", int(stock_summary["printer bluetooth"]["ready"]))
    col4.metric("Mobile Pos Ready", int(stock_summary["mobile pos"]["ready"]))

    st.markdown("---")
    st.subheader("📋 Detail Penggunaan Device (Event Aktif)")

    # Filter tampilan tabel agar sesuai jenis stok yang dipilih
    if view_option == "Temporary Stock":
        df_event_active_display = df_event_active[df_event_active["Event Status"].str.lower() == "temporary"]
    elif view_option == "Permanent Stock":
        df_event_active_display = df_event_active[df_event_active["Event Status"].str.lower() == "permanent"]
    else:
        df_event_active_display = df_event_active

    st.dataframe(df_event_active_display)


def main():
    df_event, df_temp_stock, df_perm_stock = load_data()
    df_event, df_temp_stock, df_perm_stock = preprocess_data(df_event, df_temp_stock, df_perm_stock)
    tab1, tab2 = st.tabs(["📋 Monitoring Event", "📦 Status Stok Device"])
    with tab1:
        render_tab1_monitoring_event(df_event.copy())
    with tab2:
        render_tab2_status_stok(df_event.copy(), df_temp_stock.copy(), df_perm_stock.copy())

if __name__ == "__main__":
    main()
