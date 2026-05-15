import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import re

# --- SETUP KONEKSI GOOGLE SHEETS ---
def koneksi_sheet():
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    if "gcp_service_account" in st.secrets:
        creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
    else:
        # Untuk testing lokal
        creds = Credentials.from_service_account_file("kunci_rahasia.json", scopes=scope)
    client = gspread.authorize(creds)
    return client.open_by_key("1ZDLJ8Cz09RuMtEzyJpth-lFlrenRbpYBcHWEKLcia-c")

sh = koneksi_sheet()
sheet_barang = sh.worksheet("Barang")
sheet_penjualan = sh.worksheet("Penjualan")
sheet_operasional = sh.worksheet("Operasional")

# --- FUNGSI PEMBANTU ---
def get_all_data(worksheet):
    # Mengambil data mentah agar tidak terganggu format ribuan/Rp di Sheets
    data = worksheet.get_all_records(value_render_option='UNFORMATTED_VALUE')
    return pd.DataFrame(data)

def bersihkan_angka(kolom):
    # Menghapus semua karakter non-angka (Rp, titik, koma, spasi)
    return pd.to_numeric(kolom.astype(str).str.replace(r'[^\d]', '', regex=True), errors='coerce').fillna(0)

def generate_kode(nama_barang, df_barang):
    kategori = {'kemeja': 'A', 'inner': 'B', 'tshirt': 'C', 'dress': 'D', 'cardigan': 'E', 'vest': 'F'}
    nama_lower = nama_barang.lower()
    prefix = 'X'
    for kunci, huruf in kategori.items():
        if kunci in nama_lower:
            prefix = huruf
            break
    if df_barang.empty:
        return f"{prefix}1"
    count = len(df_barang[df_barang['Kode Item'].astype(str).str.startswith(prefix)])
    return f"{prefix}{count + 1}"

# --- UI STREAMLIT ---
st.set_page_config(page_title="GETMOICLOTHES Online", layout="wide")
st.title("👗 GETMOICLOTHES - Database Online Mode")

menu = ["Dashboard Keuangan", "Kasir & Resi (Nego)", "Input Stok Barang", "Input Operasional"]
choice = st.sidebar.selectbox("Menu Utama", menu)

# Load data awal
df_barang = get_all_data(sheet_barang)
df_penjualan = get_all_data(sheet_penjualan)
df_operasional = get_all_data(sheet_operasional)

# --- FIX TIPE DATA: Memaksa data dari Sheets jadi Angka Murni ---
if not df_barang.empty:
    df_barang['Harga Modal'] = bersihkan_angka(df_barang['Harga Modal'])
    df_barang['Stok'] = bersihkan_angka(df_barang['Stok'])

if not df_penjualan.empty:
    df_penjualan['Harga Modal'] = bersihkan_angka(df_penjualan['Harga Modal'])
    df_penjualan['Qty'] = bersihkan_angka(df_penjualan['Qty'])
    df_penjualan['Total Penjualan'] = bersihkan_angka(df_penjualan['Total Penjualan'])
    df_penjualan['Profit'] = bersihkan_angka(df_penjualan['Profit'])

if not df_operasional.empty:
    df_operasional['Biaya'] = bersihkan_angka(df_operasional['Biaya'])

if choice == "Dashboard Keuangan":
    st.subheader("📊 Laporan Real-Time (Source: Google Sheets)")
    modal_awal = 1000000
    
    total_aset_stok = (df_barang['Harga Modal'] * df_barang['Stok']).sum() if not df_barang.empty else 0
    total_kas_masuk = df_penjualan['Total Penjualan'].sum() if not df_penjualan.empty else 0
    total_hpp_laku = (df_penjualan['Harga Modal'] * df_penjualan['Qty']).sum() if not df_penjualan.empty else 0
    total_biaya_ops = df_operasional['Biaya'].sum() if not df_operasional.empty else 0
    total_profit = df_penjualan['Profit'].sum() if not df_penjualan.empty else 0
    
    sisa_kas = modal_awal - total_aset_stok - total_hpp_laku - total_biaya_ops + total_kas_masuk
    
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Modal Awal", f"Rp {modal_awal:,.0f}")
    c2.metric("Sisa Kas Fisik", f"Rp {sisa_kas:,.0f}")
    c3.metric("Uang di Stok", f"Rp {total_aset_stok:,.0f}")
    c4.metric("Total Profit", f"Rp {total_profit:,.0f}")

    st.markdown("---")
    st.write("**Daftar Barang Jualan:**")
    st.dataframe(df_barang, use_container_width=True)

elif choice == "Kasir & Resi (Nego)":
    st.subheader("🛒 Kasir Penjualan")
    if not df_barang.empty:
        opsi = [f"{row['Kode Item']} - {row['Nama Barang']}" for _, row in df_barang.iterrows() if row['Stok'] > 0]
        if opsi:
            pilihan = st.selectbox("Pilih Barang Laku", opsi)
            kode = pilihan.split(" - ")[0]
            item = df_barang[df_barang['Kode Item'] == kode].iloc[0]
            
            st.warning(f"Harga Modal: Rp {item['Harga Modal']:,.0f} | Stok Sisa: {int(item['Stok'])} pcs")
            
            col1, col2 = st.columns(2)
            qty = col1.number_input("Jumlah", min_value=1, max_value=int(item['Stok']))
            harga_deal = col2.number_input("Harga Jual Deal (Nego)", min_value=int(item['Harga Modal']))
            
            total = qty * harga_deal
            profit = (harga_deal - item['Harga Modal']) * qty
            profit_p = ((harga_deal - item['Harga Modal']) / item['Harga Modal']) * 100 if item['Harga Modal'] > 0 else 0
            
            if st.button("Proses Transaksi"):
                tgl = datetime.now().strftime("%Y-%m-%d %H:%M")
                # Update Stok di Sheet Barang
                row_idx = df_barang[df_barang['Kode Item'] == kode].index[0] + 2
                sheet_barang.update_cell(row_idx, 4, int(item['Stok'] - qty))
                
                # Catat Penjualan
                sheet_penjualan.append_row([tgl, kode, item['Nama Barang'], int(item['Harga Modal']), int(harga_deal), int(qty), int(total), int(profit), f"{profit_p:.2f}%"])
                
                st.success("Tercatat ke Google Sheets!")
                st.balloons()
        else:
            st.warning("Semua stok barang sedang habis.")
    else:
        st.error("Data barang kosong.")

elif choice == "Input Stok Barang":
    st.subheader("📦 Tambah Stok Baru")
    nama = st.text_input("Nama Barang")
    if nama:
        kode_baru = generate_kode(nama, df_barang)
        st.info(f"Kode Otomatis: {kode_baru}")
        
        h_modal = st.number_input("Harga Modal (HPP)", min_value=0)
        stok_awal = st.number_input("Jumlah Stok", min_value=1)
        
        if st.button("Simpan Barang"):
            sheet_barang.append_row([kode_baru, nama, h_modal, stok_awal])
            st.success("Barang Baru Berhasil Disimpan!")

elif choice == "Input Operasional":
    st.subheader("💸 Pengeluaran Operasional")
    nama_ops = st.text_input("Keterangan (Plastik, Bensin, dll)")
    biaya = st.number_input("Total Biaya", min_value=0)
    
    if st.button("Catat Pengeluaran"):
        tgl = datetime.now().strftime("%Y-%m-%d %H:%M")
        sheet_operasional.append_row([tgl, nama_ops, biaya])
        st.success("Biaya Operasional Tercatat!")
