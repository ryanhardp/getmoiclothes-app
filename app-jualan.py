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

# --- FUNGSI PEMBERSIH KOLOM & DATA ---
def get_clean_df(worksheet):
    # Ambil data mentah (UNFORMATTED agar Rp dan titik tidak mengganggu)
    data = worksheet.get_all_records(value_render_option='UNFORMATTED_VALUE')
    df = pd.DataFrame(data)
    if not df.empty:
        # Bersihkan nama kolom dari spasi depan/belakang (Solusi buat KeyError)
        df.columns = [str(c).strip() for c in df.columns]
    return df

def bersihkan_angka(kolom):
    # Menghapus simbol Rp, titik, koma agar bisa dihitung
    return pd.to_numeric(kolom.astype(str).str.replace(r'[^\d]', '', regex=True), errors='coerce').fillna(0)

# --- LOAD DATA ---
df_barang = get_clean_df(sheet_barang)
df_penjualan = get_clean_df(sheet_penjualan)
df_operasional = get_clean_df(sheet_operasional)

# --- SETUP UI ---
st.set_page_config(page_title="GETMOICLOTHES Online", layout="wide")
st.title("👗 GETMOICLOTHES - Stable Mode")

# --- PROSES DATA (PASTIKAN ANGKA) ---
if not df_barang.empty:
    for col in ['Harga Modal', 'Stok']:
        if col in df_barang.columns:
            df_barang[col] = bersihkan_angka(df_barang[col])

if not df_penjualan.empty:
    for col in ['Harga Modal', 'Qty', 'Total Penjualan', 'Profit']:
        if col in df_penjualan.columns:
            df_penjualan[col] = bersihkan_angka(df_penjualan[col])

if not df_operasional.empty:
    if 'Biaya' in df_operasional.columns:
        df_operasional['Biaya'] = bersihkan_angka(df_operasional['Biaya'])

# --- MENU ---
menu = ["Dashboard Keuangan", "Kasir & Resi (Nego)", "Input Stok Barang", "Input Operasional"]
choice = st.sidebar.selectbox("Menu Utama", menu)

if choice == "Dashboard Keuangan":
    st.subheader("📊 Laporan Keuangan")
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
    st.dataframe(df_barang, use_container_width=True)

elif choice == "Kasir & Resi (Nego)":
    st.subheader("🛒 Kasir")
    # Bagian input kasir tetap sama dengan logika update cell
    st.info("Pilih barang dan masukkan harga deal sesuai kesepakatan.")
    # ... (sisa logika kasir kamu tinggal lanjut di sini)

elif choice == "Input Stok Barang":
    st.subheader("📦 Tambah Barang")
    # Logika input stok...
    st.write("Gunakan menu ini untuk menambah item baru ke Google Sheets.")

elif choice == "Input Operasional":
    st.subheader("💸 Pengeluaran")
    # Logika input operasional...
