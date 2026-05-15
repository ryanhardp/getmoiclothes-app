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
    kategori = {'kemeja': 'A', 'inner': 'B', 'tshirt': 'C', 'dress': 'D', 'cardigan': 'E', 'vest': 'F', 'plastik': 'P', 'print': 'P', 'resi': 'P'}
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
st.title("👗 GETMOICLOTHES - Advanced System")

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
    
    laba_kotor = df_penjualan['Profit'].sum() if 'Profit' in df_penjualan.columns else 0
    laba_bersih = laba_kotor - total_biaya_ops
    sisa_kas = modal_awal - total_aset_stok - total_hpp_laku - total_biaya_ops + total_kas_masuk
    
    c1, c2, c3 = st.columns(3)
    c1.metric("Modal Awal", f"Rp {modal_awal:,.0f}")
    c2.metric("Sisa Kas Fisik di Tangan", f"Rp {sisa_kas:,.0f}")
    c3.metric("Uang Tertahan di Stok (Baju+Pack)", f"Rp {total_aset_stok:,.0f}")
    
    st.markdown("---")
    st.markdown("### 💰 Analisis Profit & Operasional")
    c4, c5, c6 = st.columns(3)
    c4.metric("Laba Kotor (Untung Transaksi)", f"Rp {laba_kotor:,.0f}")
    c5.metric("Operasional (Non-Stok)", f"Rp {total_biaya_ops:,.0f}")
    c6.metric("Laba Bersih (Net Profit)", f"Rp {laba_bersih:,.0f}")
    
    st.markdown("---")
    st.write("**Daftar Sisa Stok Barang & Packaging:**")
    if not df_barang.empty:
        st.dataframe(df_barang, use_container_width=True)

elif choice == "Riwayat Penjualan":
    st.subheader("📈 Laporan Data Penjualan")
    if not df_penjualan.empty:
        col1, col2 = st.columns(2)
        col1.metric("Total Baju Utama Terjual", f"{df_penjualan['Qty'].sum():,.0f} pcs")
        col2.metric("Total Omset Masuk", f"Rp {df_penjualan['Total Penjualan'].sum():,.0f}")
        st.dataframe(df_penjualan, use_container_width=True)
    else:
        st.info("Belum ada data penjualan.")

elif choice == "Riwayat Operasional":
    st.subheader("💸 Laporan Biaya Operasional")
    st.warning("Catatan: Biaya packaging/resi TIDAK masuk ke sini, melainkan otomatis masuk ke Modal Penjualan per transaksi.")
    if not df_operasional.empty:
        st.metric("Total Uang Terpakai (Non-Stok)", f"Rp {df_operasional['Biaya'].sum():,.0f}")
        st.dataframe(df_operasional, use_container_width=True)
    else:
        st.info("Belum ada data pengeluaran operasional.")

elif choice == "Kasir & Resi (Nego)":
    st.subheader("🛒 Kasir Penjualan Fleksibel")
    if not df_barang.empty:
        opsi_semua = [f"{row['Kode Item']} - {row['Nama Barang']}" for _, row in df_barang.iterrows() if row['Stok'] > 0]
        
        if opsi_semua:
            st.markdown("**Langkah 1: Pilih Barang Utama**")
            pilihan_baju = st.selectbox("Pilih Baju/Celana (Wajib)", opsi_semua)
            kode_baju = pilihan_baju.split(" - ")[0]
            item_baju = df_barang[df_barang['Kode Item'] == kode_baju].iloc[0]
            
            st.markdown("**Langkah 2: Pilih Tambahan (Opsional)**")
            pilihan_tambahan = st.multiselect("Pilih Tambahan (Plastik / Resi / Baju Lain)", opsi_semua, placeholder="Bisa pilih lebih dari satu...")
            
            st.markdown("---")
            st.markdown("### 📝 Atur Jumlah (Qty) Masing-Masing")
            
            col_q1, col_q2 = st.columns(2)
            
            # Input untuk baju utama
            qty_baju = col_q1.number_input(f"📦 Qty: {item_baju['Nama Barang']}", min_value=1, max_value=int(item_baju['Stok']), value=1)
            
            # Input dinamis untuk tiap barang tambahan
            qty_tambahan = {}
            for idx, p in enumerate(pilihan_tambahan):
                kode_p = p.split(" - ")[0]
                item_p = df_barang[df_barang['Kode Item'] == kode_p].iloc[0]
                
                # Biar tampilannya rapi kanan-kiri
                if idx % 2 == 0:
                    qty_tambahan[kode_p] = col_q2.number_input(f"📦 Qty: {item_p['Nama Barang']}", min_value=1, max_value=int(item_p['Stok']), value=1)
                else:
                    qty_tambahan[kode_p] = col_q1.number_input(f"📦 Qty: {item_p['Nama Barang']}", min_value=1, max_value=int(item_p['Stok']), value=1)
            
            # --- LOGIKA PERHITUNGAN MODAL ---
            total_modal_baju = item_baju['Harga Modal'] * qty_baju
            total_modal_tambahan = 0
            nama_lengkap_transaksi = f"{qty_baju}x {item_baju['Nama Barang']}"
            
            for p in pilihan_tambahan:
                kode_p = p.split(" - ")[0]
                item_p = df_barang[df_barang['Kode Item'] == kode_p].iloc[0]
                qty_p = qty_tambahan[kode_p]
                
                total_modal_tambahan += (item_p['Harga Modal'] * qty_p)
                nama_lengkap_transaksi += f" + {qty_p}x {item_p['Nama Barang']}"
            
            total_modal_semua = total_modal_baju + total_modal_tambahan
            
            st.info(f"💡 **Total Modal HPP Semua Item: Rp {total_modal_semua:,.0f}**")
            
            st.markdown("### 💰 Pembayaran Akhir")
            harga_deal_total = st.number_input("Total Harga Jual Deal (Keseluruhan yg dibayar customer)", min_value=int(total_modal_semua))
            
            if st.button("Proses Transaksi Bundle"):
                tgl = datetime.now().strftime("%Y-%m-%d %H:%M")
                
                # 1. Potong Stok Utama
                row_idx_baju = df_barang[df_barang['Kode Item'] == kode_baju].index[0] + 2
                sheet_barang.update_cell(row_idx_baju, 4, int(item_baju['Stok'] - qty_baju))
                
                # 2. Potong Stok Tambahan
                for p in pilihan_tambahan:
                    kode_p = p.split(" - ")[0]
                    item_p = df_barang[df_barang['Kode Item'] == kode_p].iloc[0]
                    row_idx_p = df_barang[df_barang['Kode Item'] == kode_p].index[0] + 2
                    sheet_barang.update_cell(row_idx_p, 4, int(item_p['Stok'] - qty_tambahan[kode_p]))
                
                # 3. Hitung Profit Total
                profit = harga_deal_total - total_modal_semua
                profit_persen = f"{(profit/total_modal_semua)*100:.1f}%" if total_modal_semua > 0 else "0%"
                kode_tercatat = kode_baju if not pilihan_tambahan else "BUNDLE"
                
                # 4. Catat Penjualan (Disatukan di 1 baris)
                sheet_penjualan.append_row([tgl, kode_tercatat, nama_lengkap_transaksi, int(total_modal_semua), int(harga_deal_total), int(qty_baju), int(harga_deal_total), int(profit), profit_persen])
                
                st.success("Selesai! Stok Baju dan Packaging udah dipotong sesuai porsinya.")
                st.balloons()
        else: 
            st.warning("Semua stok barang sedang habis.")
    else:
        st.error("Data barang masih kosong.")

elif choice == "Input Stok Barang":
    st.subheader("📦 Tambah Stok Baru (Termasuk Plastik/Resi)")
    with st.form("form_stok"):
        nama = st.text_input("Nama Barang / Packaging")
        h_modal = st.number_input("Harga Modal per Pcs", min_value=0)
        stok_awal = st.number_input("Jumlah Stok", min_value=1)
        
        if st.form_submit_button("Simpan Data"):
            if nama:
                kode_baru = generate_kode(nama, df_barang)
                sheet_barang.append_row([kode_baru, nama, h_modal, stok_awal])
                st.success(f"Tersimpan! {nama} masuk dengan Kode: {kode_baru}")
            else: 
                st.error("Nama wajib diisi.")

elif choice == "Input Operasional":
    st.subheader("💸 Catat Pengeluaran Murni")
    st.info("Gunakan menu ini HANYA untuk pengeluaran yang tidak berbentuk barang fisik (Misal: Bensin kurir, Ads IG).")
    with st.form("form_ops"):
        ket = st.text_input("Keterangan Pengeluaran")
        biaya = st.number_input("Total Biaya", min_value=0)
        
        if st.form_submit_button("Catat Biaya"):
            if ket:
                tgl = datetime.now().strftime("%Y-%m-%d %H:%M")
                sheet_operasional.append_row([tgl, ket, biaya])
                st.success("Pengeluaran operasional berhasil dicatat!")
            else: 
                st.error("Keterangan pengeluaran wajib diisi.")
