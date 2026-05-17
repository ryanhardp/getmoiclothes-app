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

# --- LOAD, CLEAN & AUTO-RECALCULATE DATA ---
df_barang = get_clean_df(sheet_barang)
df_penjualan = get_clean_df(sheet_penjualan)
df_operasional = get_clean_df(sheet_operasional)

if not df_barang.empty:
    for col in ['Harga Modal', 'Stok']:
        if col in df_barang.columns:
            df_barang[col] = bersihkan_angka(df_barang[col])

if not df_penjualan.empty:
    for col in ['Harga Modal', 'Harga Jual', 'Qty', 'Total Penjualan', 'Profit']:
        if col in df_penjualan.columns:
            df_penjualan[col] = bersihkan_angka(df_penjualan[col])
            
    if 'Harga Jual' in df_penjualan.columns and 'Harga Modal' in df_penjualan.columns:
        df_penjualan['Total Penjualan'] = df_penjualan['Harga Jual']
        df_penjualan['Profit'] = df_penjualan['Total Penjualan'] - df_penjualan['Harga Modal']
        def hitung_persen(row):
            if row['Harga Modal'] > 0:
                return f"{(row['Profit'] / row['Harga Modal']) * 100:.1f}%"
            return "0%"
        df_penjualan['%Profit'] = df_penjualan.apply(hitung_persen, axis=1)

if not df_operasional.empty:
    if 'Biaya' in df_operasional.columns:
        df_operasional['Biaya'] = bersihkan_angka(df_operasional['Biaya'])

# --- UI STREAMLIT ---
st.set_page_config(page_title="GETMOICLOTHES Online", layout="wide", page_icon="👗")
st.title("👗 GETMOICLOTHES")
st.markdown("*Advanced Inventory & Point of Sales*")
st.markdown("---")

menu = [
    "📊 Dashboard Utama", 
    "🛒 Kasir & Resi", 
    "📈 Riwayat Penjualan", 
    "💸 Riwayat Operasional", 
    "📦 Input Stok Barang", 
    "📝 Input Operasional"
]
choice = st.sidebar.radio("Navigasi Menu", menu)

if choice == "📊 Dashboard Utama":
    st.subheader("Ringkasan Keuangan Global")
    modal_awal = 700000
    
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
    c3.metric("Uang Tertahan di Stok", f"Rp {total_aset_stok:,.0f}")
    
    c4, c5, c6 = st.columns(3)
    c4.metric("Laba Kotor (Untung Transaksi)", f"Rp {laba_kotor:,.0f}")
    c5.metric("Operasional (Non-Stok)", f"Rp {total_biaya_ops:,.0f}")
    c6.metric("Laba Bersih (Net Profit)", f"Rp {laba_bersih:,.0f}")
    
    st.markdown("---")
    st.markdown("### 🛍️ 5 Transaksi Terakhir")
    if not df_penjualan.empty:
        df_recent = df_penjualan.tail(5).iloc[::-1].copy()
        
        kolom_penting = ['Kode Item', 'Total Penjualan', 'Profit']
        kolom_ada = [k for k in kolom_penting if k in df_recent.columns]
        
        st.dataframe(
            df_recent[kolom_ada].style.set_properties(**{'text-align': 'center'}), 
            use_container_width=True, 
            hide_index=True, 
            column_config={
                "Kode Item": st.column_config.TextColumn("Kode Barang", width="medium"), # UDAH DIKECILIN JADI MEDIUM
                "Total Penjualan": st.column_config.NumberColumn(format="Rp %d"),
                "Profit": st.column_config.NumberColumn(format="Rp %d")
            }
        )
    else:
        st.info("Belum ada transaksi pecah telor nih bos.")

    st.markdown("---")
    with st.expander("👀 Klik di sini untuk melihat Rincian Sisa Stok & Status"):
        if not df_barang.empty:
            df_display = df_barang.copy()
            df_display = df_display.sort_values(by='Stok', ascending=False)
            df_display['Status'] = df_display['Stok'].apply(lambda x: "✅ Ready" if x > 0 else "❌ Sold Out")
            
            kolom_urutan = ['Kode Item', 'Nama Barang', 'Harga Modal', 'Stok', 'Status']
            kolom_ada = [k for k in kolom_urutan if k in df_display.columns]
            
            st.dataframe(
                df_display[kolom_ada].style.set_properties(**{'text-align': 'center'}), 
                use_container_width=True, 
                hide_index=True, 
                column_config={
                    "Kode Item": st.column_config.TextColumn("Kode Barang", width="medium"),
                    "Stok": st.column_config.NumberColumn(width="small"),
                    "Status": st.column_config.TextColumn(width="small"),
                    "Harga Modal": st.column_config.NumberColumn(format="Rp %d")
                }
            )
        else:
            st.info("Belum ada data barang.")

elif choice == "🛒 Kasir & Resi":
    st.subheader("Kasir Keranjang Belanja")
    if not df_barang.empty:
        opsi_semua = [f"{row['Kode Item']} - {row['Nama Barang']}" for _, row in df_barang.iterrows() if row['Stok'] > 0]
        
        pilihan_keranjang = st.multiselect("Pilih SEMUA Barang (Baju & Packaging) yang mau di-checkout:", opsi_semua, placeholder="Cari barang disini...")
        
        if pilihan_keranjang:
            st.markdown("### 📝 Atur Jumlah (Qty)")
            col_q1, col_q2 = st.columns(2)
            
            qty_dict = {}
            total_modal_baju = 0
            total_modal_pack = 0
            qty_baju_total = 0
            rincian_nama = []
            
            for idx, p in enumerate(pilihan_keranjang):
                kode = p.split(" - ")[0]
                item = df_barang[df_barang['Kode Item'] == kode].iloc[0]
                
                if idx % 2 == 0:
                    qty = col_q1.number_input(f"📦 Qty: {item['Nama Barang']}", min_value=1, max_value=int(item['Stok']), value=1)
                else:
                    qty = col_q2.number_input(f"📦 Qty: {item['Nama Barang']}", min_value=1, max_value=int(item['Stok']), value=1)
                
                qty_dict[kode] = qty
                sub_modal = item['Harga Modal'] * qty
                rincian_nama.append(f"{qty}x {item['Nama Barang']}")
                
                is_packaging = kode.startswith('P') or any(k in item['Nama Barang'].lower() for k in ['plastik', 'print', 'resi', 'polymailer'])
                
                if is_packaging:
                    total_modal_pack += sub_modal
                else:
                    total_modal_baju += sub_modal
                    qty_baju_total += qty  
            
            total_modal_semua = total_modal_baju + total_modal_pack
            
            st.markdown("---")
            st.info(f"💡 **TOTAL MODAL (HPP): Rp {total_modal_semua:,.0f}** \n *(Baju: Rp {total_modal_baju:,.0f} | Packaging: Rp {total_modal_pack:,.0f})*")
            
            harga_deal_total = st.number_input("💰 Total Harga Jual (Uang Diterima)", min_value=int(total_modal_semua))
            
            st.markdown("### 💳 Metode Pembayaran")
            metode_payment = st.selectbox("Pilih Bank / Platform:", ["Transfer BCA", "Transfer Seabank", "Full Shopee", "Cash / Lainnya"])
            
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("Proses Transaksi", type="primary"):
                tgl = datetime.now().strftime("%Y-%m-%d %H:%M")
                
                for kode, q in qty_dict.items():
                    row_idx = df_barang[df_barang['Kode Item'] == kode].index[0] + 2
                    stok_lama = df_barang[df_barang['Kode Item'] == kode].iloc[0]['Stok']
                    sheet_barang.update_cell(row_idx, 4, int(stok_lama - q))
                
                profit = harga_deal_total - total_modal_semua
                profit_persen = f"{(profit/total_modal_semua)*100:.1f}%" if total_modal_semua > 0 else "0%"
                
                nama_tercatat = " + ".join(rincian_nama) + f" [{metode_payment}]"
                kode_tercatat = " + ".join(qty_dict.keys())
                
                sheet_penjualan.append_row([tgl, kode_tercatat, nama_tercatat, int(total_modal_semua), int(harga_deal_total), int(qty_baju_total), int(harga_deal_total), int(profit), profit_persen])
                
                st.toast('Transaksi Berhasil Tersimpan!', icon='✅')
                st.toast('Stok otomatis dikurangi.', icon='📉')
                st.balloons()
        else:
            st.info("Pilih barang di atas untuk mulai transaksi.")
    else:
        st.error("Data barang masih kosong.")

elif choice == "📈 Riwayat Penjualan":
    st.subheader("Laporan Data Penjualan")
    if not df_penjualan.empty:
        col1, col2, col3 = st.columns(3)
        col1.metric("Total Baju Terjual (Qty)", f"{df_penjualan['Qty'].sum():,.0f} pcs")
        col2.metric("Total Omset Masuk", f"Rp {df_penjualan['Total Penjualan'].sum():,.0f}")
        col3.metric("Total Untung (Profit)", f"Rp {df_penjualan['Profit'].sum():,.0f}")
        
        df_display_penjualan = df_penjualan.copy()
        df_display_penjualan = df_display_penjualan.iloc[::-1]
        
        if 'Nama Barang' in df_display_penjualan.columns:
            df_display_penjualan['Payment'] = df_display_penjualan['Nama Barang'].astype(str).str.extract(r'\[(.*?)\]')
            df_display_penjualan['Payment'] = df_display_penjualan['Payment'].fillna('Lainnya')
        
        kolom_tampil = ['Kode Item', 'Harga Modal', 'Harga Jual', 'Profit', 'Payment'] # Posisi kolom gue sesuaikan dikit biar proporsional
        kolom_ada = [k for k in kolom_tampil if k in df_display_penjualan.columns]
        
        st.dataframe(
            df_display_penjualan[kolom_ada].style.set_properties(**{'text-align': 'center'}), 
            use_container_width=True, 
            hide_index=True,
            column_config={
                "Kode Item": st.column_config.TextColumn("Kode Barang", width="medium"), # UDAH DIKECILIN
                "Harga Modal": st.column_config.NumberColumn(format="Rp %d"),
                "Harga Jual": st.column_config.NumberColumn(format="Rp %d"),
                "Payment": st.column_config.TextColumn("Payment", width="small"),
                "Profit": st.column_config.NumberColumn(format="Rp %d")
            }
        )
    else:
        st.info("Belum ada data penjualan.")

elif choice == "💸 Riwayat Operasional":
    st.subheader("Laporan Biaya Operasional")
    if not df_operasional.empty:
        st.metric("Total Uang Terpakai (Non-Stok)", f"Rp {df_operasional['Biaya'].sum():,.0f}")
        st.dataframe(
            df_operasional.style.set_properties(**{'text-align': 'center'}), 
            use_container_width=True, 
            hide_index=True
        )
    else:
        st.info("Belum ada data pengeluaran operasional.")

elif choice == "📦 Input Stok Barang":
    st.subheader("Tambah Stok Baru")
    with st.form("form_stok"):
        nama = st.text_input("Nama Barang / Packaging")
        h_modal = st.number_input("Harga Modal per Pcs", min_value=0)
        stok_awal = st.number_input("Jumlah Stok", min_value=1)
        
        if st.form_submit_button("Simpan Data"):
            if nama:
                kode_baru = generate_kode(nama, df_barang)
                sheet_barang.append_row([kode_baru, nama, h_modal, stok_awal])
                st.toast(f'{nama} masuk dengan Kode: {kode_baru}', icon='📦')
            else: 
                st.error("Nama wajib diisi.")

elif choice == "📝 Input Operasional":
    st.subheader("Catat Pengeluaran Murni")
    with st.form("form_ops"):
        ket = st.text_input("Keterangan Pengeluaran (Bensin, Ads, dll)")
        biaya = st.number_input("Total Biaya", min_value=0)
        
        if st.form_submit_button("Catat Biaya"):
            if ket:
                tgl = datetime.now().strftime("%Y-%m-%d %H:%M")
                sheet_operasional.append_row([tgl, ket, biaya])
                st.toast('Pengeluaran berhasil dicatat!', icon='💸')
            else: 
                st.error("Keterangan pengeluaran wajib diisi.")
