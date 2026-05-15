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
st.title("👗 GETMOICLOTHES - Advanced Cart System")

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
        col1.metric("Total Baju Terjual (Qty)", f"{df_penjualan['Qty'].sum():,.0f} pcs")
        col2.metric("Total Omset Masuk", f"Rp {df_penjualan['Total Penjualan'].sum():,.0f}")
        st.dataframe(df_penjualan, use_container_width=True)
    else:
        st.info("Belum ada data penjualan.")

elif choice == "Riwayat Operasional":
    st.subheader("💸 Laporan Biaya Operasional")
    if not df_operasional.empty:
        st.metric("Total Uang Terpakai (Non-Stok)", f"Rp {df_operasional['Biaya'].sum():,.0f}")
        st.dataframe(df_operasional, use_container_width=True)
    else:
        st.info("Belum ada data pengeluaran operasional.")

elif choice == "Kasir & Resi (Nego)":
    st.subheader("🛒 Kasir Keranjang Belanja")
    if not df_barang.empty:
        opsi_semua = [f"{row['Kode Item']} - {row['Nama Barang']}" for _, row in df_barang.iterrows() if row['Stok'] > 0]
        
        # SATU KOTAK UNTUK SEMUA PILIHAN
        pilihan_keranjang = st.multiselect("Pilih SEMUA Barang (Baju & Packaging) yang mau di-checkout:", opsi_semua, placeholder="Pilih baju, celana, plastik, print resi...")
        
        if pilihan_keranjang:
            st.markdown("### 📝 Atur Jumlah (Qty)")
            col_q1, col_q2 = st.columns(2)
            
            qty_dict = {}
            total_modal_baju = 0
            total_modal_pack = 0
            qty_baju_total = 0
            rincian_nama = []
            
            # Bikin input Qty & Hitung Modal Langsung
            for idx, p in enumerate(pilihan_keranjang):
                kode = p.split(" - ")[0]
                item = df_barang[df_barang['Kode Item'] == kode].iloc[0]
                
                # Tampilan selang-seling biar rapi
                if idx % 2 == 0:
                    qty = col_q1.number_input(f"📦 Qty: {item['Nama Barang']}", min_value=1, max_value=int(item['Stok']), value=1)
                else:
                    qty = col_q2.number_input(f"📦 Qty: {item['Nama Barang']}", min_value=1, max_value=int(item['Stok']), value=1)
                
                qty_dict[kode] = qty
                sub_modal = item['Harga Modal'] * qty
                rincian_nama.append(f"{qty}x {item['Nama Barang']}")
                
                # Deteksi otomatis: Apakah ini packaging? (Kode depan P atau ada kata plastik/resi/print)
                is_packaging = kode.startswith('P') or any(k in item['Nama Barang'].lower() for k in ['plastik', 'print', 'resi', 'polymailer'])
                
                if is_packaging:
                    total_modal_pack += sub_modal
                else:
                    total_modal_baju += sub_modal
                    qty_baju_total += qty  # Ini yang bakal dihitung sebagai Qty Penjualan di Sheets!
            
            total_modal_semua = total_modal_baju + total_modal_pack
            
            st.markdown("---")
            st.markdown("### 💡 Rincian Modal (HPP)")
            st.info(f"👕 **Modal Baju ({qty_baju_total} pcs):** Rp {total_modal_baju:,.0f} \n\n"
                    f"📦 **Modal Packaging/Resi:** Rp {total_modal_pack:,.0f} \n\n"
                    f"**= TOTAL MODAL TRANSAKSI: Rp {total_modal_semua:,.0f}**")
            
            st.markdown("### 💰 Pembayaran Akhir")
            harga_deal_total = st.number_input("Total Harga Jual (Uang Diterima dari Customer)", min_value=int(total_modal_semua))
            
            if st.button("Proses Transaksi"):
                tgl = datetime.now().strftime("%Y-%m-%d %H:%M")
                
                # 1. Update Stok Semua Barang di Keranjang
                for kode, q in qty_dict.items():
                    row_idx = df_barang[df_barang['Kode Item'] == kode].index[0] + 2
                    stok_lama = df_barang[df_barang['Kode Item'] == kode].iloc[0]['Stok']
                    sheet_barang.update_cell(row_idx, 4, int(stok_lama - q))
                
                # 2. Hitung Profit
                profit = harga_deal_total - total_modal_semua
                profit_persen = f"{(profit/total_modal_semua)*100:.1f}%" if total_modal_semua > 0 else "0%"
                
                nama_tercatat = " + ".join(rincian_nama)
                kode_tercatat = "BUNDLE" if len(qty_dict) > 1 else list(qty_dict.keys())[0]
                
                # 3. Catat ke Penjualan (Qty yang masuk murni qty baju)
                sheet_penjualan.append_row([tgl, kode_tercatat, nama_tercatat, int(total_modal_semua), int(harga_deal_total), int(qty_baju_total), int(harga_deal_total), int(profit), profit_persen])
                
                st.success("Selesai! Stok berkurang & tercatat akurat.")
                st.balloons()
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
