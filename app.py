import streamlit as st
import pandas as pd
from datetime import datetime, time, timedelta
import io

# --- 1. إعدادات الأمان وقاعدة بيانات المستخدمين ---
USERS = {
    "admin_nazih": {"password": "admin_password_2026", "role": "admin"},
    "user_team": {"password": "work_password_123", "role": "user"}
}

# --- 2. إعدادات الصفحة ---
st.set_page_config(page_title="Ajust d'Alarme - Private Access", layout="wide")

# --- 3. منطق تسجيل الدخول (Login Logic) ---
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
    st.session_state.role = None

def login():
    st.markdown("<h2 style='text-align: center;'>🔐 Connexion Requise</h2>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        username = st.text_input("Identifiant (Username)")
        password = st.text_input("Mot de passe", type="password")
        if st.button("Se connecter"):
            if username in USERS and USERS[username]["password"] == password:
                st.session_state.authenticated = True
                st.session_state.role = USERS[username]["role"]
                st.rerun()
            else:
                st.error("Identifiants incorrects")

# --- 4. تشغيل التطبيق بعد التحقق ---
if not st.session_state.authenticated:
    login()
else:
    # زر تسجيل الخروج في الشريط الجانبي
    if st.sidebar.button("🚪 Déconnexion"):
        st.session_state.authenticated = False
        st.session_state.role = None
        st.rerun()

    # الواجهة الأمامية
    IMAGE_URL = "https://archive.challenge.ma/wp-content/uploads/2022/04/shutterstock_275763713-2-800x400-1.jpg"
    st.image(IMAGE_URL, use_container_width=True)

    st.markdown(f"<h1 style='text-align: center; color: #1E3A8A; font-family: Merriweather, serif;'>Ajust d'Alarme ({st.session_state.role})</h1>", unsafe_allow_html=True)
    st.markdown("---")

    # Sidebar (Paramètres)
    st.sidebar.header("🗓️ Paramètres Généraux")
    target_date = st.sidebar.date_input("Date de travail", datetime.now())

    st.sidebar.markdown("---")
    st.sidebar.header("⚙️ Configuration Cas Spécial")
    selected_wtgs = st.sidebar.multiselect("Turbines concernées", [f"WTG{str(i).zfill(2)}" for i in range(1, 62)])

    st.sidebar.subheader("⏰ Plage Horaire (Cas Spécial)")
    cs_start_h = st.sidebar.time_input("Heure de début", time(8, 0, 0))
    cs_end_h = st.sidebar.time_input("Heure de fin", time(17, 0, 0))

    cs_resp = st.sidebar.selectbox("Responsable (CS)", ["EEM", "WTG", "ONEE"])
    cs_impact = st.sidebar.selectbox("Nature de l'impact", ["Déclenchement", "Bridage", "Inspection Générale", "Coupure"])

    # Base Alarmes
    st.sidebar.markdown("---")
    st.sidebar.header("📋 Base des Codes (Excel)")
    base_file = st.sidebar.file_uploader("Charger Base Excel", type=["xlsx"])

    dict_alarme = {}
    if base_file:
        try:
            df_base = pd.read_excel(base_file)
            df_base.columns = [str(c).strip() for c in df_base.columns]
            for _, row in df_base.iterrows():
                code = str(row['cod alarm']).strip()
                resp = str(row['responsable']).strip()
                if "EEM" in resp.upper(): pri = 1
                elif "CORRMAINT" in resp.upper(): pri = 2
                elif "MANUALSTOP" in resp.upper(): pri = 3
                else: pri = 4
                dict_alarme[code] = {'resp': resp, 'pri': pri}
            st.sidebar.success(f"✅ {len(dict_alarme)} codes chargés")
        except Exception as e:
            st.sidebar.error(f"Erreur format Base Excel: {e}")

    # Zone de téléchargement du Journal
    uploaded_file = st.file_uploader("📂 Charger le Journal Système (Excel)", type=["xlsx"])

    if uploaded_file:
        try:
            raw_df = pd.read_excel(uploaded_file, header=None)
            header_row_index = None
            for i, row in raw_df.iterrows():
                if row.astype(str).str.contains('WTG0', case=False).any():
                    header_row_index = i
                    break
            
            if header_row_index is not None:
                df = pd.read_excel(uploaded_file, skiprows=header_row_index)
                df = df.dropna(how='all', axis=1).iloc[:, :5]
                df.columns = ['WTG', 'Code', 'Text', 'Start', 'End']
                
                df['S_DT'] = pd.to_datetime(df['Start'], dayfirst=True)
                df['E_DT'] = pd.to_datetime(df['End'], dayfirst=True)
                
                d_day_start = datetime.combine(target_date, time(0, 0, 0))
                d_day_end = datetime.combine(target_date, time(23, 59, 59))
                
                df = df.dropna(subset=['S_DT', 'E_DT'])
                df = df[(df['S_DT'] <= d_day_end) & (df['E_DT'] >= d_day_start)].copy()

                all_events = []
                for wtg in selected_wtgs:
                    s_cs = datetime.combine(target_date, cs_start_h)
                    e_cs = datetime.combine(target_date, cs_end_h)
                    all_events.append({'WTG': wtg, 'Code': 'CAS_SPEC', 'Text': cs_impact, 'Start': s_cs, 'End': e_cs, 'Resp': cs_resp, 'Impact': cs_impact, 'Pri': 0})

                for _, row in df.iterrows():
                    s = max(row['S_DT'], d_day_start)
                    e = min(row['E_DT'], d_day_end)
                    if s < e:
                        info = dict_alarme.get(str(row['Code']).strip(), {'resp': 'WTG', 'pri': 4})
                        all_events.append({'WTG': row['WTG'], 'Code': row['Code'], 'Text': row['Text'], 'Start': s, 'End': e, 'Resp': info['resp'], 'Impact': '-', 'Pri': info['pri']})

                processed_data = []
                if all_events:
                    events_df = pd.DataFrame(all_events)
                    for wtg, group in events_df.groupby('WTG'):
                        group = group.sort_values(by=['Start', 'Pri'])
                        current_timeline = []
                        for _, ev in group.iterrows():
                            ev_dict = ev.to_dict()
                            if not current_timeline:
                                current_timeline.append(ev_dict)
                            else:
                                last = current_timeline[-1]
                                if ev_dict['Start'] < last['End']:
                                    if ev_dict['Pri'] < last['Pri']: 
                                        old_end = last['End']
                                        last['End'] = ev_dict['Start'] 
                                        current_timeline.append(ev_dict) 
                                        if old_end > ev_dict['End']:
                                            rem = last.copy()
                                            rem['Start'] = ev_dict['End']
                                            rem['End'] = old_end
                                            current_timeline.append(rem)
                                    elif ev_dict['Pri'] == last['Pri']:
                                        last['End'] = max(last['End'], ev_dict['End'])
                                    else: 
                                        if ev_dict['End'] > last['End']:
                                            ev_dict['Start'] = last['End']
                                            current_timeline.append(ev_dict)
                                else:
                                    current_timeline.append(ev_dict)
                        processed_data.extend(current_timeline)

                if processed_data:
                    final_df = pd.DataFrame(processed_data)
                    final_df['Durée_Sec'] = (final_df['End'] - final_df['Start']).dt.total_seconds()
                    final_df['Durée_H'] = final_df['Durée_Sec'] / 3600
                    final_df['Start_Str'] = final_df['Start'].dt.strftime('%H:%M:%S')
                    final_df['End_Str'] = final_df['End'].dt.strftime('%H:%M:%S')

                    st.success(f"✅ Travail terminé (Session: {st.session_state.role})")
                    st.dataframe(final_df[['WTG', 'Code', 'Text', 'Start_Str', 'End_Str', 'Resp', 'Durée_H']])

                    output = io.BytesIO()
                    with pd.ExcelWriter(output, engine='openpyxl') as writer:
                        final_df.to_excel(writer, index=False)
                    st.download_button("📥 Télécharger le Rapport Excel", data=output.getvalue(), file_name=f"Rapport_Akhfennire_{target_date}.xlsx")

        except Exception as e:
            st.error(f"Une erreur est survenue : {e}")

    st.markdown("---")
    st.markdown("<p style='text-align: center; color: gray; font-size: 10px;'>created by nazih said</p>", unsafe_allow_html=True)
