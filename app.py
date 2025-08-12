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

def _normalize_cols(df: pd.DataFrame) -> pd.DataFrame:
    """Bersihkan nama kolom: trim, hapus BOM, kompres spasi."""
    df = df.copy()
    df.columns = (
        df.columns.astype(str)
        .str.replace("\ufeff", "", regex=False)   # hapus BOM
        .str.strip()
        .str.replace(r"\s+", " ", regex=True)     # kompres spasi
    )
    return df

def _coerce_expected_headers(df: pd.DataFrame) -> pd.DataFrame:
    """
    Beberapa ekspor CSV membawa nilai baris pertama ke nama kolom,
    mis: 'Type Printer Bluetooth ...' → paksa jadi 'Type' berdasarkan prefix.
    """
    expected = [
        "Type",
        "Brand",
        "Model",
        "Specification",
        "Serial Number",
        "Status Device",
        "Location",
        "Notes Device",
    ]
    mapping = {}
    for c in df.columns:
        cs = c.strip()
        # cari header yang cocok sbg prefix
        match = next((e for e in expected if cs.lower().startswith(e.lower())), None)
        if match:
            mapping[c] = match  # rename ke header yang benar
    return df.rename(columns=mapping)

def _standardize_stock_df(df: pd.DataFrame) -> pd.DataFrame:
    """Pastikan ada kolom 'type' yang konsisten untuk stok device."""
    df = _normalize_cols(df)
    df = _coerce_expected_headers(df)            # <-- perbaiki header bocor
    # setelah dipaksa, cek lagi kolom Type
    type_col = next((c for c in df.columns if c.lower() == "type"), None)
    if type_col is None:
        # debug yang ramah
        st.error(f"Kolom 'Type' tidak ditemukan. Kolom tersedia: {list(df.columns)}")
        # tampilkan 2 baris pertama agar kelihatan struktur datanya
        st.write("Contoh 2 baris pertama:", df.head(2))
        raise KeyError("Type")
    df["type"] = df[type_col].astype(str).str.strip().str.lower()
    return df


def preprocess_data(df_event, df_temp_stock, df_perm_stock):
    # event
    df_event = _normalize_cols(df_event)
    df_event = df_event.loc[:, ~df_event.columns.str.contains(r"^Unnamed", regex=True)]
    df_event["Status"] = df_event.get("Status", "Waiting").fillna("Waiting")
    df_event["Total Device"] = df_event[
        ["Numbers of Tablet", "Numbers of Printer", "Numbers of Mobile POS (MPOS)"]
    ].fillna(0).sum(axis=1)

    # stock (temporary & permanent)
    df_temp_stock = _standardize_stock_df(df_temp_stock)
    df_perm_stock = _standardize_stock_df(df_perm_stock)

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

# Tambahkan di atas (global helpers)
CONSUME_STATUSES = {"in use", "on prepare", "pending"}          # memotong stok
NEUTRAL_STATUSES = {"returned", "cancel", "waiting"} # tidak memotong stok (informasi saja)
STATUS_ORDER = ["in use", "on prepare", "pending"]

def count_ready_device(df_stock, df_event, selected_date, device_type, view_option):
    # 1) Total stok dari sheet stok (temp/permanen/atau gabungan)
    stok = df_stock[df_stock["type"] == device_type.lower()]
    jumlah_stok = stok.shape[0]

    # 2) Normalisasi & pilih event yang benar-benar mengurangi stok
    selected_date = pd.to_datetime(selected_date).date()
    df_event = df_event.copy()
    df_event["Event Start Date"] = pd.to_datetime(df_event["Event Start Date"], errors="coerce")
    df_event["Event End Date"]   = pd.to_datetime(df_event["Event End Date"],   errors="coerce")
    df_event["Status"]       = df_event["Status"].astype(str).str.strip().str.lower()
    df_event["Event Status"] = df_event["Event Status"].astype(str).str.strip().str.lower()

    # Hanya status yang memotong stok
    status = df_event["Status"]
    consumes = df_event["Status"].isin(CONSUME_STATUSES)

    # Aktif di tanggal terpilih (overlap)
    within_date = (
        df_event["Event Start Date"].notna() &
        df_event["Event End Date"].notna() &
        (df_event["Event Start Date"].dt.date <= selected_date) &
        (df_event["Event End Date"].dt.date >= selected_date)
    )

    is_pending = (status == "pending")
    aktif = consumes & (within_date | is_pending)

    # Batasi sesuai view_option (Temporary / Permanent) bila dipilih
    if view_option.lower() in ["temporary stock", "permanent stock"]:
        aktif &= df_event["Event Status"] == view_option.lower().replace(" stock", "")

    df_aktif = df_event[aktif]

    kolom_event = {
        "tablet": "Numbers of Tablet",
        "printer bluetooth": "Numbers of Printer",
        "mobile pos": "Numbers of Mobile POS (MPOS)",
    }[device_type.lower()]

    jumlah_dipakai = df_aktif[kolom_event].sum()

    # 3) Ready = stok - dipakai (opsional: cegah negatif agar lebih ramah UI)
    ready = jumlah_stok - jumlah_dipakai
    return max(0, int(ready))

def calculate_stock_summary(df_event, df_temp_stock, df_perm_stock, selected_date, view_option):

    # Gabung data stok jika All Stock
    if view_option == "All Stock":
        df_stock = pd.concat([df_temp_stock, df_perm_stock], ignore_index=True)
    elif view_option == "Temporary Stock":
        df_stock = df_temp_stock.copy()
    else:  # Permanent Stock
        df_stock = df_perm_stock.copy()

    #st.write("📌 Kolom tersedia:", df_stock.columns.tolist())

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

    status = df_event["Status"]
    overlap = (
        df_event["Event Start Date"].notna() &
        df_event["Event End Date"].notna() &
        (df_event["Event Start Date"].dt.date <= selected_date) &
        (df_event["Event End Date"].dt.date >= selected_date)
    )

    is_pending = (status == "pending")

    is_active = status.isin(CONSUME_STATUSES) & (overlap | is_pending)

    df_event_active = df_event[is_active].copy()
    df_temp = df_event_active[df_event_active["Event Status"] == "temporary"]
    df_perm = df_event_active[df_event_active["Event Status"] == "permanent"]

    # Tentukan scope event sesuai tab yang dipilih
    if view_option == "Temporary Stock":
        scope_df = df_temp
    elif view_option == "Permanent Stock":
        scope_df = df_perm
    else:  # All Stock
        scope_df = df_event_active

    # Hanya status yang memang mengurangi stok
    df_consume = scope_df[scope_df["Status"].isin(CONSUME_STATUSES)]

    def _breakdown_for(colname: str) -> dict:
        # Kelompokkan per status, isi 0 untuk status yang tak muncul agar rapi
        return (
            df_consume.groupby("Status")[colname].sum()
            .reindex(STATUS_ORDER, fill_value=0)
            .to_dict()
        )

    # Simpan breakdown ke stock_summary per device
    stock_summary["tablet"]["used_breakdown"] = _breakdown_for("Numbers of Tablet")
    stock_summary["printer bluetooth"]["used_breakdown"] = _breakdown_for("Numbers of Printer")
    stock_summary["mobile pos"]["used_breakdown"] = _breakdown_for("Numbers of Mobile POS (MPOS)")

    
    # Tambahan data jika masih membutuhkan struktur total_temp dan used_temp per device
    stock_summary["tablet"].update({
        "total_temp": df_temp_stock[df_temp_stock["type"] == "tablet"].shape[0],
        "used_temp": df_temp["Numbers of Tablet"].sum(),
        "total_perm": df_perm_stock[df_perm_stock["type"] == "tablet"].shape[0],
        "used_perm": df_perm["Numbers of Tablet"].sum(),
    })

    stock_summary["printer bluetooth"].update({
        "total_temp": df_temp_stock[df_temp_stock["type"] == "printer bluetooth"].shape[0],
        "used_temp": df_temp["Numbers of Printer"].sum(),
        "total_perm": df_perm_stock[df_perm_stock["type"] == "printer bluetooth"].shape[0],
        "used_perm": df_perm["Numbers of Printer"].sum(),
    })

    stock_summary["mobile pos"].update({
        "total_temp": df_temp_stock[df_temp_stock["type"] == "mobile pos"].shape[0],
        "used_temp": df_temp["Numbers of Mobile POS (MPOS)"].sum(),
        "total_perm": df_perm_stock[df_perm_stock["type"] == "mobile pos"].shape[0],
        "used_perm": df_perm["Numbers of Mobile POS (MPOS)"].sum(),
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
    #st.write(df_temp_stock["type"].value_counts())

    #st.write("📊 Distribusi Tipe di Device Permanent:")
    #st.write(df_perm_stock["type"].value_counts())

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
    with st.expander("Breakdown pemakaian (In Use vs On Prepare vs Pending)"):
        tb = stock_summary["tablet"]["used_breakdown"]
        pb = stock_summary["printer bluetooth"]["used_breakdown"]
        mp = stock_summary["mobile pos"]["used_breakdown"]

        fmt = lambda d, k: int((d.get(k, 0) or 0))

        st.markdown(
            f"""
            **Tablet** — In Use: **{fmt(tb, 'in use')}**, On Prepare: **{fmt(tb, 'on prepare')}**, Pending: **{fmt(tb, 'pending')}**  
            **Printer Bluetooth** — In Use: **{fmt(pb, 'in use')}**, On Prepare: **{fmt(pb, 'on prepare')}**, Pending: **{fmt(pb, 'pending')}**  
            **Mobile POS** — In Use: **{fmt(mp, 'in use')}**, On Prepare: **{fmt(mp, 'on prepare')}**, Pending: **{fmt(mp, 'pending')}**
            """
        )

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
