import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime

# 1. SETUP DATABASE (DATA LAMA KAMU AMAN DI SINI)
conn = sqlite3.connect('database_jualan.db', check_same_thread=False)
c = conn.cursor()

# Tabel barang (Data lama kamu ada di sini, harga_jual lama akan kita abaikan saja)
c.execute('''CREATE TABLE IF NOT EXISTS barang 
             (id INTEGER PRIMARY KEY AUTOINCREMENT, 
              kode_item TEXT, nama TEXT, harga_beli REAL, harga_jual REAL, stok INTEGER)''')

# Tabel baru untuk Riwayat Penjualan
c.execute('''CREATE TABLE IF NOT EXISTS penjualan 
             (id INTEGER PRIMARY KEY AUTOINCREMENT, 
              tanggal TEXT, kode_item TEXT, nama_barang TEXT, 
              harga_modal REAL, harga_jual_deal REAL, qty INTEGER, 
              total_penjualan REAL, profit REAL, profit_persen REAL)''')

# Tabel baru untuk Biaya Operasional (Plastik, Bensin, dll)
c.execute('''CREATE TABLE IF NOT EXISTS operasional 
             (id INTEGER PRIMARY KEY AUTOINCREMENT, 
              tanggal TEXT, nama_pengeluaran TEXT, biaya REAL)''')
conn.commit()

# --- FUNGSI AUTO GENERATE KODE ---
def generate_kode(nama_barang):
    kategori = {'kemeja': 'A', 'inner': 'B', 'tshirt': 'C', 'dress': 'D', 'cardigan': 'E', 'vest': 'F'}
    nama_lower = nama_barang.lower()
    prefix = 'X' 
    for kunci, huruf in kategori.items():
        if kunci in nama_lower:
            prefix = huruf
            break
            
    c.execute(f"SELECT kode_item FROM barang WHERE kode_item LIKE '{prefix}%'")
    data_kategori = c.fetchall()
    return f"{prefix}{len(data_kategori) + 1}"

# --- UI STREAMLIT ---
st.set_page_config(page_title="GETMOICLOTHES System", layout="wide")
st.title("👗 GETMOICLOTHES System - Pro Version")

menu = ["Dashboard Keuangan & Penjualan", "Kasir & Resi (Nego)", "Manajemen Stok Barang", "Manajemen Operasional"]
choice = st.sidebar.selectbox("Pilih Menu", menu)

if choice == "Dashboard Keuangan & Penjualan":
    st.subheader("📊 Dashboard Keuangan (Real-Time)")
    
    modal_awal = 1000000
    
    # Ambil data
    df_barang = pd.read_sql_query("SELECT * FROM barang", conn)
    df_jual = pd.read_sql_query("SELECT * FROM penjualan", conn)
    df_ops = pd.read_sql_query("SELECT * FROM operasional", conn)
    
    # Kalkulasi Arus Kas
    total_aset_stok = (df_barang['harga_beli'] * df_barang['stok']).sum() if not df_barang.empty else 0
    total_hpp_terjual = (df_jual['harga_modal'] * df_jual['qty']).sum() if not df_jual.empty else 0
    total_kas_masuk = df_jual['total_penjualan'].sum() if not df_jual.empty else 0
    total_operasional = df_ops['biaya'].sum() if not df_ops.empty else 0
    total_profit = df_jual['profit'].sum() if not df_jual.empty else 0
    
    # Uang Kas Fisik = Modal Awal - (Uang tertahan di stok) - (Uang stok yang laku) - (Biaya Operasional) + (Uang Penjualan Masuk)
    sisa_uang_kas = modal_awal - total_aset_stok - total_hpp_terjual - total_operasional + total_kas_masuk
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Modal Awal", f"Rp {modal_awal:,.0f}")
    col2.metric("Sisa Uang Kas (Bisa Dipakai)", f"Rp {sisa_uang_kas:,.0f}")
    col3.metric("Total Profit Penjualan", f"Rp {total_profit:,.0f}")
    col4.metric("Uang Tertahan di Stok", f"Rp {total_aset_stok:,.0f}")
    
    st.markdown("---")
    st.subheader("📈 Laporan Penjualan (Item Laku)")
    if not df_jual.empty:
        # Tampilkan tabel penjualan yang rapi
        df_jual_display = df_jual[['tanggal', 'kode_item', 'nama_barang', 'harga_modal', 'harga_jual_deal', 'qty', 'total_penjualan', 'profit', 'profit_persen']]
        st.dataframe(df_jual_display.style.format({
            "harga_modal": "Rp {:,.0f}", 
            "harga_jual_deal": "Rp {:,.0f}",
            "total_penjualan": "Rp {:,.0f}",
            "profit": "Rp {:,.0f}",
            "profit_persen": "{:.2f}%"
        }), use_container_width=True)
    else:
        st.info("Belum ada barang yang terjual.")

elif choice == "Kasir & Resi (Nego)":
    st.subheader("🛒 Transaksi Penjualan (Bisa Nego)")
    df = pd.read_sql_query("SELECT * FROM barang WHERE stok > 0", conn)
    
    if not df.empty:
        pilihan_barang = [f"{row['kode_item']} - {row['nama']}" for index, row in df.iterrows()]
        item_dipilih = st.selectbox("Pilih Barang", pilihan_barang)
        
        kode_terpilih = item_dipilih.split(" - ")[0]
        detail = df[df['kode_item'] == kode_terpilih].iloc[0]
        
        # Tampilkan info modal agar penjual tahu batas bawah nego
        st.info(f"💡 Info HPP/Modal: **Rp {detail['harga_beli']:,.0f}** | Sisa Stok: **{detail['stok']} pcs**")
        
        col1, col2 = st.columns(2)
        with col1:
            jumlah = st.number_input("Jumlah Beli", min_value=1, max_value=int(detail['stok']))
        with col2:
            # Input harga jual di kasir
            harga_jual_deal = st.number_input("Harga Jual (Hasil Deal/Nego) per Pcs", min_value=int(detail['harga_beli']), value=int(detail['harga_beli'] + 10000))
        
        total_harga = harga_jual_deal * jumlah
        profit_total = (harga_jual_deal - detail['harga_beli']) * jumlah
        profit_persen = ((harga_jual_deal - detail['harga_beli']) / detail['harga_beli']) * 100
        
        if st.button("Proses Bayar & Cetak Resi"):
            waktu_skrg = datetime.now().strftime("%Y-%m-%d %H:%M")
            
            # Kurangi stok
            c.execute('UPDATE barang SET stok = stok - ? WHERE kode_item = ?', (int(jumlah), kode_terpilih))
            
            # Catat ke riwayat penjualan
            c.execute('''INSERT INTO penjualan (tanggal, kode_item, nama_barang, harga_modal, harga_jual_deal, qty, total_penjualan, profit, profit_persen)
                         VALUES (?,?,?,?,?,?,?,?,?)''', 
                      (waktu_skrg, kode_terpilih, detail['nama'], detail['harga_beli'], harga_jual_deal, int(jumlah), total_harga, profit_total, profit_persen))
            conn.commit()
            
            st.success("Transaksi Berhasil!")
            st.markdown("---")
            st.markdown(f"""
            ### 🧾 RESI GETMOICLOTHES
            **Waktu:** {waktu_skrg}  
            **Kode Item:** {kode_terpilih}  
            **Barang:** {detail['nama']}  
            **Harga Deal:** Rp {harga_jual_deal:,.0f}  
            **Qty:** {jumlah} pcs  
            **TOTAL BAYAR: Rp {total_harga:,.0f}**
            ---
            """)
            st.balloons()
    else:
        st.warning("Stok barang jualan sedang kosong.")

elif choice == "Manajemen Stok Barang":
    st.subheader("📦 Tambah Stok Barang Jualan")
    st.write("Catatan: Input Harga Jual sudah dihilangkan. Harga Jual dimasukkan saat di Menu Kasir.")
    
    nama_input = st.text_input("Nama Barang (Cth: Kemeja Polka Biru)")
    
    if nama_input:
        st.info(f"💡 Kode otomatis: **{generate_kode(nama_input)}**")
        
    with st.form("form_tambah_stok"):
        h_beli = st.number_input("Harga Beli / Modal (Per Pcs)", min_value=0)
        stok = st.number_input("Jumlah Stok", min_value=0)
        submit = st.form_submit_button("Simpan Barang")
        
        if submit and nama_input:
            kode_final = generate_kode(nama_input)
            # Kita set harga_jual ke 0 saja di database karena sudah tidak dipakai di sini
            c.execute('INSERT INTO barang (kode_item, nama, harga_beli, harga_jual, stok) VALUES (?,?,?,?,?)', 
                      (kode_final, nama_input, h_beli, 0, stok))
            conn.commit()
            st.success(f"Berhasil! {nama_input} tersimpan.")
            
    st.markdown("---")
    st.write("**Daftar Stok Saat Ini:**")
    df_stok = pd.read_sql_query("SELECT kode_item, nama, harga_beli, stok FROM barang", conn)
    st.dataframe(df_stok)

elif choice == "Manajemen Operasional":
    st.subheader("💸 Pengeluaran Operasional (Non-Stok)")
    st.write("Masukkan biaya yang tidak bisa dijual lagi (contoh: Plastik, Bensin, Sabun Cuci, Kaca, dll). Biaya ini akan langsung memotong sisa uang kas.")
    
    with st.form("form_operasional"):
        nama_ops = st.text_input("Nama Pengeluaran (Cth: Beli Plastik Packing)")
        biaya_ops = st.number_input("Total Biaya (Rp)", min_value=0)
        submit_ops = st.form_submit_button("Catat Pengeluaran")
        
        if submit_ops and nama_ops:
            waktu_skrg = datetime.now().strftime("%Y-%m-%d %H:%M")
            c.execute('INSERT INTO operasional (tanggal, nama_pengeluaran, biaya) VALUES (?,?,?)', (waktu_skrg, nama_ops, biaya_ops))
            conn.commit()
            st.success("Pengeluaran operasional berhasil dicatat!")
            
    df_ops_display = pd.read_sql_query("SELECT * FROM operasional", conn)
    if not df_ops_display.empty:
        st.dataframe(df_ops_display)