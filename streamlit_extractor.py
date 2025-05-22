import streamlit as st
import pandas as pd
import pdfplumber
import PyPDF2
import re
import io
from datetime import datetime
import base64

# Configurazione pagina
st.set_page_config(
    page_title="Credit Card Extractor",
    page_icon="💳",
    layout="wide",
    initial_sidebar_state="expanded"
)

def extract_movements_from_pdf(pdf_file):
    """Estrae i movimenti da un singolo PDF"""
    movements = []
    
    try:
        with pdfplumber.open(pdf_file) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    page_movements = parse_movements_from_text(text)
                    movements.extend(page_movements)
                    
    except Exception as e:
        st.warning(f"Errore lettura PDF con pdfplumber: {str(e)}")
        
        # Fallback con PyPDF2
        try:
            pdf_file.seek(0)  # Reset file pointer
            reader = PyPDF2.PdfReader(pdf_file)
            for page_num in range(len(reader.pages)):
                page = reader.pages[page_num]
                text = page.extract_text()
                if text:
                    page_movements = parse_movements_from_text(text)
                    movements.extend(page_movements)
        except Exception as e2:
            st.error(f"Errore anche con PyPDF2: {str(e2)}")
            
    return movements

def parse_movements_from_text(text):
    """Analizza il testo e estrae i movimenti"""
    movements = []
    
    # Pattern per trovare le linee dei movimenti
    # Formato: CODICE DATA_OP DATA_REG DESCRIZIONE IMPORTO
    movement_pattern = r'(\d{20,})\s+(\d{8})\s+(\d{2}\/\d{2}\/\d{4})\s+(\d{2}\/\d{2}\/\d{4})\s+(.+?)\s+(\d+,\d{2})(?:\s|$)'
    
    matches = re.findall(movement_pattern, text, re.MULTILINE)
    
    for match in matches:
        try:
            code, date_code, operation_date, registration_date, description, amount_str = match
            
            # Pulisci la descrizione
            description = description.strip()
            description = re.sub(r'\s+', ' ', description)
            
            # Converti l'importo
            amount = float(amount_str.replace(',', '.'))
            
            # Usa la data di registrazione come data principale
            date_obj = datetime.strptime(registration_date, "%d/%m/%Y")
            
            movement = {
                'Data': date_obj.strftime("%d/%m/%Y"),
                'Data_Operazione': operation_date,
                'Descrizione': description,
                'Importo': amount,
                'Codice_Riferimento': code
            }
            
            movements.append(movement)
            
        except (ValueError, IndexError):
            continue
    
    # Pattern semplificato se il primo non trova nulla
    if not movements:
        simple_pattern = r'(\d{2}\/\d{2}\/\d{4})\s+(\d{2}\/\d{2}\/\d{4})\s+(.+?)\s+(\d+,\d{2})(?:\s|$)'
        simple_matches = re.findall(simple_pattern, text, re.MULTILINE)
        
        for match in simple_matches:
            try:
                operation_date, registration_date, description, amount_str = match
                
                description = description.strip()
                description = re.sub(r'\s+', ' ', description)
                
                amount = float(amount_str.replace(',', '.'))
                
                date_obj = datetime.strptime(registration_date, "%d/%m/%Y")
                
                movement = {
                    'Data': date_obj.strftime("%d/%m/%Y"),
                    'Data_Operazione': operation_date,
                    'Descrizione': description,
                    'Importo': amount,
                    'Codice_Riferimento': ''
                }
                
                movements.append(movement)
                
            except (ValueError, IndexError):
                continue
    
    return movements

def process_data(data, remove_duplicates, sort_by_date):
    """Elabora i dati estratti"""
    if not data:
        return data
    
    # Rimuovi duplicati
    if remove_duplicates:
        seen = set()
        unique_data = []
        
        for movement in data:
            key = (movement['Data'], movement['Descrizione'], movement['Importo'])
            if key not in seen:
                seen.add(key)
                unique_data.append(movement)
        
        data = unique_data
    
    # Ordina per data
    if sort_by_date:
        data.sort(key=lambda x: datetime.strptime(x['Data'], "%d/%m/%Y"))
    
    return data

def create_download_link(df, filename):
    """Crea link per download CSV"""
    csv = df.to_csv(index=False)
    b64 = base64.b64encode(csv.encode()).decode()
    href = f'<a href="data:file/csv;base64,{b64}" download="{filename}">📥 Scarica {filename}</a>'
    return href

# Interfaccia principale
def main():
    st.title("💳 Credit Card Extractor")
    st.markdown("### Estrai automaticamente i movimenti dagli estratti conto PDF")
    
    # Sidebar per opzioni
    st.sidebar.header("⚙️ Opzioni")
    
    remove_duplicates = st.sidebar.checkbox("Rimuovi duplicati", value=True)
    sort_by_date = st.sidebar.checkbox("Ordina per data", value=True)
    include_extra_cols = st.sidebar.checkbox("Includi colonne extra", value=False)
    
    st.sidebar.markdown("---")
    st.sidebar.markdown("**💡 Come usare:**")
    st.sidebar.markdown("1. Carica i file PDF")
    st.sidebar.markdown("2. Configura le opzioni")
    st.sidebar.markdown("3. Clicca 'Estrai Movimenti'")
    st.sidebar.markdown("4. Scarica il CSV")
    
    # Upload dei file
    st.header("📁 Carica Estratti Conto")
    uploaded_files = st.file_uploader(
        "Seleziona uno o più file PDF",
        type=['pdf'],
        accept_multiple_files=True,
        help="Puoi caricare più estratti conto contemporaneamente"
    )
    
    if uploaded_files:
        st.success(f"✅ {len(uploaded_files)} file caricati")
        
        # Mostra lista file
        with st.expander("📋 File caricati"):
            for i, file in enumerate(uploaded_files, 1):
                file_size = len(file.getvalue()) / 1024  # KB
                st.write(f"{i}. **{file.name}** ({file_size:.1f} KB)")
        
        # Pulsante per estrarre
        if st.button("🚀 Estrai Movimenti", type="primary", use_container_width=True):
            
            # Progress bar
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            all_movements = []
            
            # Elabora ogni file
            for i, uploaded_file in enumerate(uploaded_files):
                status_text.text(f"Elaborazione {uploaded_file.name}...")
                progress_bar.progress((i + 1) / len(uploaded_files))
                
                # Estrai movimenti
                movements = extract_movements_from_pdf(uploaded_file)
                
                if movements:
                    all_movements.extend(movements)
                    st.success(f"✅ {len(movements)} movimenti da {uploaded_file.name}")
                else:
                    st.warning(f"⚠️ Nessun movimento trovato in {uploaded_file.name}")
            
            # Elabora tutti i dati
            if all_movements:
                status_text.text("Elaborazione dati...")
                processed_data = process_data(all_movements, remove_duplicates, sort_by_date)
                
                # Converti in DataFrame
                df = pd.DataFrame(processed_data)
                
                # Seleziona colonne da mostrare
                if include_extra_cols:
                    columns = ['Data', 'Data_Operazione', 'Descrizione', 'Importo', 'Codice_Riferimento']
                else:
                    columns = ['Data', 'Descrizione', 'Importo']
                
                # Filtra solo le colonne esistenti
                available_columns = [col for col in columns if col in df.columns]
                df_display = df[available_columns]
                
                # Formatta importi
                if 'Importo' in df_display.columns:
                    df_display['Importo'] = df_display['Importo'].apply(lambda x: f"€ {x:.2f}")
                
                status_text.text("✅ Elaborazione completata!")
                progress_bar.progress(1.0)
                
                # Risultati
                st.header("📊 Risultati")
                
                # Statistiche
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    st.metric("Movimenti totali", len(processed_data))
                
                with col2:
                    total_amount = sum([m['Importo'] for m in processed_data])
                    st.metric("Totale importi", f"€ {total_amount:.2f}")
                
                with col3:
                    if processed_data:
                        dates = [datetime.strptime(m['Data'], "%d/%m/%Y") for m in processed_data]
                        period_days = (max(dates) - min(dates)).days + 1
                        st.metric("Periodo (giorni)", period_days)
                
                with col4:
                    avg_amount = total_amount / len(processed_data) if processed_data else 0
                    st.metric("Importo medio", f"€ {avg_amount:.2f}")
                
                # Tabella movimenti
                st.subheader("📋 Movimenti estratti")
                st.dataframe(df_display, use_container_width=True, height=400)
                
                # Download
                st.subheader("💾 Download")
                
                # Prepara DataFrame per download (senza formattazione euro)
                df_download = df[available_columns].copy()
                
                # Genera nome file
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"movimenti_estratti_{timestamp}.csv"
                
                # Link download
                st.markdown(create_download_link(df_download, filename), unsafe_allow_html=True)
                
                # Statistiche per periodo
                if len(processed_data) > 1:
                    st.subheader("📈 Analisi per mese")
                    
                    # Raggruppa per mese
                    df_analysis = df.copy()
                    df_analysis['Data'] = pd.to_datetime(df_analysis['Data'], format='%d/%m/%Y')
                    df_analysis['Mese'] = df_analysis['Data'].dt.to_period('M')
                    
                    monthly_stats = df_analysis.groupby('Mese').agg({
                        'Importo': ['count', 'sum', 'mean']
                    }).round(2)
                    
                    monthly_stats.columns = ['Numero movimenti', 'Totale €', 'Media €']
                    st.dataframe(monthly_stats, use_container_width=True)
            
            else:
                st.error("❌ Nessun movimento trovato in nessun file")
                st.info("💡 Verifica che i PDF siano estratti conto validi")

    else:
        # Informazioni quando non ci sono file
        st.info("👆 Carica uno o più file PDF per iniziare")
        
        # Esempio
        with st.expander("📖 Formati supportati"):
            st.markdown("""
            **Questo estrattore funziona con:**
            - ✅ Estratti Cartimpronta/Numia 
            - ✅ Estratti Banco BPM
            - ✅ Altri estratti con formato simile
            
            **Pattern riconosciuti:**
            - Date in formato GG/MM/AAAA
            - Descrizioni commercianti
            - Importi con virgola decimale
            - Codici riferimento operazione
            """)

if __name__ == "__main__":
    main()