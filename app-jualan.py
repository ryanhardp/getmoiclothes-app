import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

# --- SETUP KONEKSI ---
def koneksi_sheet():
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    if "gcp_service_account" in st.secrets:
        creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
    else:
        creds = Credentials.from_service_account_file("kunci_rahasia.json", scopes=scope)
    client = gspread.authorize(creds)
    return client.open_by_key("1ZDLJ8Cz09RuMtEzyJpth-lFlrenRbpYBcHWEKLcia-c")

sh = koneksi_sheet()
sheet_barang = sh.worksheet("Barang")
sheet_penjualan = sh.worksheet("Penjualan")
sheet_operasional = sh.worksheet("Operasional")

# --- FUNGSI PEMBERSIH DATA ---
def get_clean_df(worksheet):
    data = worksheet.get_all_records(value_render_option='UNFORMATTED_VALUE')
    df = pd.DataFrame(data)
    if not df.empty:
        df.columns = [str(c).strip() for c in df.columns]
    return df

def bersihkan_angka(kolom):
    return pd.to_numeric(kolom.astype(str).str.replace(r'[^\d]', '', regex=True), errors='coerce').fillna(0)

def generate_kode(nama_barang, df_barang):
    kategori = {'kemeja': 'A', 'inner': 'B', 'tshirt': 'C', 'dress': 'D', 'cardigan': 'E', 'vest': 'F'}
    nama_lower = nama_barang.lower()
    prefix = 'X'
    for kunci, huruf in kategori.items():
        if kunci in nama_lower:
            prefix = huruf
            break
    if df_barang.empty or 'Kode Item' not in df_barang.columns:
        return f"{prefix}1"
    count = len(df_barang[df_barang['Kode Item'].astype(str).str.startswith(prefix)])
    return f"{prefix}{count + 1}"

# --- LOAD & CLEAN DATA ---
df_barang = get_clean_df(sheet_barang)
df_penjualan = get_clean_df(sheet_penjualan)
df_operasional = get_clean_df(sheet_operasional)

for df, cols in [(df_barang, ['Harga Modal', 'Stok']), 
                 (df_penjualan, ['Harga Modal', 'Qty', 'Total Penjualan', 'Profit']),
                 (df_operasional, ['Biaya'])]:
    if not df.empty:
        for col in cols:
            if col in df.columns:
                df[col] = bersihkan_angka(df[col])

# --- UI STREAMLIT ---
st.set_page_config(page_title="GETMOICLOTHES Online", layout="wide")
st.title("👗 GETMOICLOTHES - Full System")

# MENU BARU (Ditambah Riwayat Penjualan & Riwayat Operasional)
menu = [
    "Dashboard Utama", 
    "Riwayat Penjualan", 
    "Riwayat Operasional", 
    "Kasir & Resi (Nego)", 
    "Input Stok Barang", 
    "Input Operasional"
]
choice = st.sidebar.selectbox("Menu Utama", menu)

if choice == "Dashboard Utama":
    st.subheader("📊 Ringkasan Keuangan Global")
    modal_awal = 1000000
    
    total_aset_stok = (df_barang['Harga Modal'] * df_barang['Stok']).sum() if 'Harga Modal' in df_barang.columns else 0
    total_kas_masuk = df_penjualan['Total Penjualan'].sum() if 'Total Penjualan' in df_penjualan.columns else 0
    total_hpp_laku = (df_penjualan['Harga Modal'] * df_penjualan['Qty']).sum() if 'Harga Modal' in df_penjualan.columns else 0
    total_biaya_ops = df_operasional['Biaya'].sum() if 'Biaya' in df_operasional.columns else 0
    total_profit = df_penjualan['Profit'].sum() if 'Profit' in df_penjualan.columns else 0
    
    sisa_kas = modal_awal - total_aset_stok - total_hpp_laku - total_biaya_ops + total_kas_masuk
    
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Modal Awal", f"Rp {modal_awal:,.0f}")
    c2.metric("Sisa Kas Fisik", f"Rp {sisa_kas:,.0f}")
    c3.metric("Uang di Stok", f"Rp {total_aset_stok:,.0f}")
    c4.metric("Total Profit", f"Rp {total_profit:,.0f}")
    
    st.markdown("---")
    st.write("**Daftar Sisa Stok Barang:**")
    if not df_barang.empty:
        st.dataframe(df_barang, use_container_width=True)
    else:
        st.info("Belum ada data barang.")

elif choice == "Riwayat Penjualan":
    st.subheader("📈 Laporan Data Penjualan")
    if not df_penjualan.empty:
        total_item_laku = df_penjualan['Qty'].sum() if 'Qty' in df_penjualan.columns else 0
        total_omset = df_penjualan['Total Penjualan'].sum() if 'Total Penjualan' in df_penjualan.columns else 0
        
        col1, col2 = st.columns(2)
        col1.metric("Total Item Terjual", f"{total_item_laku:,.0f} pcs")
        col2.metric("Total Omset Masuk", f"Rp {total_omset:,.0f}")
        
        st.markdown("---")
        st.dataframe(df_penjualan, use_container_width=True)
    else:
        st.info("Belum ada data penjualan tercatat. Transaksi dari kasir akan muncul di sini.")

elif choice == "Riwayat Operasional":
    st.subheader("💸 Laporan Biaya Operasional")
    if not df_operasional.empty:
        total_ops = df_operasional['Biaya'].sum() if 'Biaya' in df_operasional.columns else 0
        
        st.metric("Total Uang Terpakai (Non-Stok)", f"Rp {total_ops:,.0f}")
        
        st.markdown("---")
        st.dataframe(df_operasional, use_container_width=True)
    else:
        st.info("Belum ada data pengeluaran operasional. Pengeluaran seperti plastik/bensin akan muncul di sini.")

elif choice == "Kasir & Resi (Nego)":
    st.subheader("🛒 Kasir Penjualan")
    if not df_barang.empty:
        opsi = [f"{row['Kode Item']} - {row['Nama Barang']}" for _, row in df_barang.iterrows() if row['Stok'] > 0]
        if opsi:
            pilihan = st.selectbox("Pilih Barang", opsi)
            kode = pilihan.split(" - ")[0]
            item = df_barang[df_barang['Kode Item'] == kode].iloc[0]
            
            st.warning(f"Modal: Rp {item['Harga Modal']:,.0f} | Stok Sisa: {int(item['Stok'])} pcs")
            
            col1, col2 = st.columns(2)
            qty = col1.number_input("Jumlah Beli", min_value=1, max_value=int(item['Stok']))
            harga_deal = col2.number_input("Harga Jual Deal per Pcs", min_value=int(item['Harga Modal']))
            
            if st.button("Proses Transaksi"):
                tgl = datetime.now().strftime("%Y-%m-%d %H:%M")
                row_idx = df_barang[df_barang['Kode Item'] == kode].index[0] + 2
                
                # Kurangi Stok
                sheet_barang.update_cell(row_idx, 4, int(item['Stok'] - qty))
                
                # Hitung Total dan Profit
                total = qty * harga_deal
                profit = total - (item['Harga Modal'] * qty)
                profit_persen = f"{(profit/total)*100:.1f}%" if total > 0 else "0%"
                
                # Catat ke Sheet Penjualan
                sheet_penjualan.append_row([tgl, kode, item['Nama Barang'], int(item['Harga Modal']), int(harga_deal), int(qty), int(total), int(profit), profit_persen])
                
                st.success("Transaksi Berhasil! Stok berkurang & penjualan tercatat.")
                st.balloons()
        else: 
            st.warning("Semua stok barang sedang habis.")
    else:
        st.error("Data barang masih kosong.")

elif choice == "Input Stok Barang":
    st.subheader("📦 Tambah Stok Baru")
    with st.form("form_stok"):
        nama = st.text_input("Nama Barang")
        h_modal = st.number_input("Harga Modal per Pcs", min_value=0)
        stok_awal = st.number_input("Jumlah Stok", min_value=1)
        
        if st.form_submit_button("Simpan Barang"):
            if nama:
                kode_baru = generate_kode(nama, df_barang)
                sheet_barang.append_row([kode_baru, nama, h_modal, stok_awal])
                st.success(f"Tersimpan! {nama} masuk dengan Kode: {kode_baru}")
            else: 
                st.error("Nama barang wajib diisi.")

elif choice == "Input Operasional":
    st.subheader("💸 Catat Pengeluaran Operasional")
    with st.form("form_ops"):
        ket = st.text_input("Keterangan (Contoh: Beli Plastik Packing, Bensin)")
        biaya = st.number_input("Total Biaya", min_value=0)
        
        if st.form_submit_button("Catat Biaya"):
            if ket:
                tgl = datetime.now().strftime("%Y-%m-%d %H:%M")
                sheet_operasional.append_row([tgl, ket, biaya])
                st.success("Pengeluaran operasional berhasil dicatat!")
            else: 
                st.error("Keterangan pengeluaran wajib diisi.")
