import streamlit as st
import pandas as pd
import io
import requests
import matplotlib.pyplot as plt


# =========================================================
# 🎨 CS-MACH1 BRANDING
# =========================================================
st.image("logo.png", width=250)

st.set_page_config(
    page_title="CS-MACH1 my envlogger pipeline",
    page_icon="logo.png",
    layout="wide"
)

st.markdown(
    """
    <style>

    /* HEADER STYLE */
    .main-header {
        font-size: 34px;
        font-weight: 700;
        color: #00A6D6;
        margin-bottom: 0px;
    }

    .sub-header {
        font-size: 16px;
        color: #555;
        margin-bottom: 20px;
    }

    /* BUTTON STYLE */
    .stButton>button {
        background-color: #00A6D6;
        color: white;
        border-radius: 8px;
        border: none;
    }

    .stButton>button:hover {
        background-color: #007EA3;
        color: white;
    }

    </style>
    """,
    unsafe_allow_html=True
)


st.markdown(
    "<div class='main-header'>🌊 CS-MACH1: What does my envlogger dive data say about Sea Water Temperature ? 🌡 </div>",
    unsafe_allow_html=True
)

st.markdown(
    "<div class='sub-header'>Ocean temperature comparison platform (in-situ loggers vs CORA reanalysis)</div>",
    unsafe_allow_html=True
)

# =========================================================
# 🧠 LOGGER CSV PROCESSING
# =========================================================
@st.cache_data(show_spinner=False)
def envlogcsv_to_df(env_data, verbose=0):

    # -------------------------
    # METADATA
    # -------------------------
    serial = env_data.iloc[9, 1]
    name = env_data.iloc[10, 1]
    sampling = env_data.iloc[13, 1]

    # -------------------------
    # FLEXIBLE LAT/LON ROWS
    # -------------------------
    if str(env_data.iloc[15, 0]).strip().lower() == 'lat':
        latitude = env_data.iloc[15, 1]
        longitude = env_data.iloc[16, 1]
    else:
        latitude = env_data.iloc[16, 1]
        longitude = env_data.iloc[17, 1]

    latitude = pd.to_numeric(latitude, errors='coerce')
    longitude = pd.to_numeric(longitude, errors='coerce')

    if verbose:
        st.write(f"Latitude: {latitude}")
        st.write(f"Longitude: {longitude}")

    # -------------------------
    # FALLBACK COORDINATES
    # -------------------------
    if pd.isna(latitude) or pd.isna(longitude):

        if verbose:
            st.warning("Invalid coordinates -> using Bogliasco fallback")

        latitude = 44.377253
        longitude = 9.073425

    # -------------------------
    # SPECIAL SURF CASE
    # -------------------------
    if isinstance(name, str) and 'surf' in name.lower():
        latitude = 43.573851
        longitude = 7.126338

    # -------------------------
    # EXTRACT DATA
    # -------------------------
    df = env_data.iloc[21:, :].copy()

    df = df.dropna().reset_index(drop=True)

    df.columns = ['time', 'temperature']

    df['time'] = pd.to_datetime(
        df['time'],
        errors='coerce'
    )

    df['temperature'] = pd.to_numeric(
        df['temperature'],
        errors='coerce'
    )

    df = df.dropna(subset=['time', 'temperature'])

    # -------------------------
    # METADATA COLUMNS
    # -------------------------
    df['serial'] = serial
    df['custom_name'] = name
    df['sampling_f'] = sampling
    df['latitude'] = latitude
    df['longitude'] = longitude

    # useful for plotting
    df['month'] = df['time'].dt.month

    return df


# =========================================================
# 🌊 CORA LOADING
# =========================================================
@st.cache_data(ttl=86400, show_spinner=False)
def load_cora_data(latitude, longitude):

    latitude = round(float(latitude), 2)
    longitude = round(float(longitude), 2)

    cora_url = (
        "https://erddap.emodnet-physics.eu/erddap/griddap/"
        "INSITU_GLO_PHY_TS_OA_MY_013_052_TEMP.csv"
        f"?TEMP[(1990-01-01T00:00:00Z):1:(2023-06-15T00:00:00Z)]"
        f"[(1.0):1:(1)]"
        f"[({latitude}):1:({latitude})]"
        f"[({longitude}):1:({longitude})]"
    )

    response = requests.get(
        cora_url,
        timeout=30,
        verify=False
    )

    response.raise_for_status()

    # ERDDAP sometimes returns HTML error pages
    if "<html" in response.text.lower():
        raise ValueError("CORA server returned HTML instead of CSV")

    df = pd.read_csv(
        io.StringIO(response.text),
        skiprows=[1]
    )

    df['time'] = pd.to_datetime(
        df['time'],
        errors='coerce'
    )

    df['TEMP'] = pd.to_numeric(
        df['TEMP'],
        errors='coerce'
    )

    df = df.dropna(subset=['time', 'TEMP'])

    df['month'] = df['time'].dt.month

    df.head()

    return df


# =========================================================
# 🎯 STREAMLIT UI
# =========================================================
#st.title(" CORA vs Multiple Logger Temperature Comparison")

uploaded_files = st.file_uploader(
    "Upload one or more envlog CSV files",
    type=["csv"],
    accept_multiple_files=True
)

# ---------------------------------------------------------
# STORE FILES IN SESSION
# ---------------------------------------------------------
if uploaded_files:
    st.session_state["uploaded_files"] = uploaded_files

# ---------------------------------------------------------
# RESET BUTTON
# ---------------------------------------------------------
#col1, col2 = st.columns(2)

start_button = st.button("▶️ Start Processing") 
if st.button("🧹 Reset"):
    st.session_state.clear()
    st.rerun()

# =========================================================
# PROCESS DATA
# =========================================================
if start_button and "uploaded_files" in st.session_state:

    uploaded_files = st.session_state["uploaded_files"]

    logger_data = {}

    progress_bar = st.progress(0)
    status_text = st.empty()

    # -----------------------------------------------------
    # PROCESS EACH FILE
    # -----------------------------------------------------
    for i, file in enumerate(uploaded_files):

        status_text.write(f"Processing {file.name} ...")

        try:

            raw_df = pd.read_csv(file)

            df = envlogcsv_to_df(raw_df)

            if not df.empty:
                logger_data[file.name] = df

        except Exception as e:

            st.warning(f"Failed processing {file.name}: {e}")

        progress_bar.progress((i + 1) / len(uploaded_files))

    if len(logger_data) == 0:
        st.error("No valid logger datasets found.")
        st.stop()

    # save results
    st.session_state["logger_data"] = logger_data

# =========================================================
# DISPLAY RESULTS
# =========================================================
if "logger_data" in st.session_state:

    logger_data = st.session_state["logger_data"]

    # -----------------------------------------------------
    # LOCATION FROM FIRST LOGGER
    # -----------------------------------------------------
    first_key = list(logger_data.keys())[0]

    latitude = logger_data[first_key]['latitude'].mean()
    longitude = logger_data[first_key]['longitude'].mean()

    # -----------------------------------------------------
    # LOAD CORA
    # -----------------------------------------------------
    try:

        with st.spinner("Loading CORA data..."):

            cora_data = load_cora_data(
                latitude,
                longitude
            )

    except Exception as e:

        st.error(f"CORA loading failed: {e}")
        st.stop()

    # -----------------------------------------------------
    # CORA MONTHLY STATS
    # -----------------------------------------------------
   
    cora_temp_data = cora_data
    cora_temp_data['month'] = cora_temp_data['time'].dt.month
    cora_monthly_stats = cora_temp_data.groupby('month')['TEMP'].agg(['mean', 'std']).reset_index()

    plt.figure(figsize=(12, 6))
    

    # -----------------------------------------------------
    # PLOT
    # -----------------------------------------------------
    fig, ax = plt.subplots(figsize=(10, 5))

    # CORA reference
    ax.scatter(cora_monthly_stats['month'], cora_monthly_stats['mean'], label='Monthly Mean Temperature')
    ax.errorbar(cora_monthly_stats['month'], cora_monthly_stats['mean'], yerr=cora_monthly_stats['std'], fmt='o', capsize=3, label='Monthly Standard Deviation')

    # -----------------------------------------------------
    # LOGGER STAR MARKERS
    # -----------------------------------------------------
    for fn in logger_data.keys():

        sdata = logger_data[fn]

        d = sdata['time'].iloc[0].month
        tavg = sdata['temperature'].mean()
        label = sdata['custom_name'].iloc[0]
        year = sdata['time'].iloc[0].year
       
        # marker selection by year
        if year == 2025:
            marker = '*'
        elif year == 2026:
            marker = '^'   # triangle
        elif year == 2027:
            marker = 's'   # square
        else:
            marker = 'o'   # fallback
        
        ax.plot(d, tavg, marker=marker, markersize=10, linestyle='None', label=label)

    # -----------------------------------------------------
    # FORMAT
    # -----------------------------------------------------
    ax.set_xticks(range(1, 13))

    ax.set_xticklabels([
        'Jan', 'Feb', 'Mar', 'Apr',
        'May', 'Jun', 'Jul', 'Aug',
        'Sep', 'Oct', 'Nov', 'Dec'
    ])

    ax.set_xlabel("Month")
    ax.set_ylabel("Temperature [°C]")

    ax.set_title(
        "CORA vs Multiple Logger Monthly Temperature"
    )

    ax.grid(True)
    #ax.legend()
    fig.tight_layout()

    st.pyplot(fig)

    # -----------------------------------------------------
    # PLOT
    # -----------------------------------------------------
 
    fig2, ax2 = plt.subplots(figsize=(10, 5))

    # Group by year and plot
    for year, year_data in cora_temp_data.groupby(cora_temp_data['time'].dt.year):
        year_data['day_of_year'] = year_data['time'].dt.dayofyear
        
        ax2.plot(year_data['day_of_year'], year_data['TEMP'], label=year, marker='.', linestyle='--')
        
        for fn in logger_data.keys():
            sdata = logger_data[fn]
            d = sdata['time'].iloc[0].timetuple().tm_yday
            tavg = sdata['temperature'].mean()
            label = sdata['custom_name'].iloc[0]      
            year = sdata['time'].iloc[0].year
            
            # marker selection by year
            if year == 2025:
                marker = '*'
            elif year == 2026:
                marker = '^'   # triangle
            elif year == 2027:
                marker = 's'   # square
            else:
                marker = 'o'   # fallback
            
            ax2.plot(d, tavg, marker=marker, markersize=10, linestyle='None', label=label)
            #ax2.plot(d, tavg, '*', markersize=20, label=label)
    
    # Set labels and
    ax2.set_xlabel('Day of Year')
    ax2.set_ylabel('Temperature [°C]')
    ax2.set_title(f'Interannual Temperature Variability at ({latitude:.2f}, {longitude:.2f})')
    ax2.grid(True)
    fig2.tight_layout()
    st.pyplot(fig2)

    # -----------------------------------------------------
    # -----------------------------------------------------
    # 📊 SUMMARY STATISTICS CSV
    # -----------------------------------------------------
    st.markdown("---")
    st.markdown("### 📊 Riepilogo statistiche per file")

    summary_rows = []

    for fn, sdata in logger_data.items():
        summary_rows.append({
            "file_name": fn,
            "latitude": sdata['latitude'].iloc[0],
            "longitude": sdata['longitude'].iloc[0],
            "datetime": sdata['time'].iloc[0],
            "temperature_mean": round(sdata['temperature'].mean(), 3),
            "temperature_median": round(sdata['temperature'].median(), 3)
        })

    summary_df = pd.DataFrame(summary_rows)

    st.dataframe(summary_df, use_container_width=True)

    csv_buffer = io.StringIO()
    summary_df.to_csv(csv_buffer, index=False)

    st.download_button(
        label="💾 Save processed data",
        data=csv_buffer.getvalue(),
        file_name="cs-mach1_summary_stats.csv",
        mime="text/csv"
    )
    st.markdown("---")

    # -----------------------------------------------------
    # 📈 TIMESERIES PLOT DEL SUMMARY
    # -----------------------------------------------------
    st.markdown("### 📈 Timeseries delle statistiche")

    summary_df_sorted = summary_df.sort_values("datetime")

    fig3, ax3 = plt.subplots(figsize=(10, 5))

    ax3.plot(
        summary_df_sorted['datetime'],
        summary_df_sorted['temperature_mean'],
        marker='.',
        linestyle='-',
        color = 'r',
        label='Temperature mean'
    )

    ax3.plot(
        summary_df_sorted['datetime'],
        summary_df_sorted['temperature_median'],
        marker='+',
        linestyle='--',
        color = 'b',
        label='Temperature median'
    )

    # etichette con nome file su ogni punto
    '''
    for _, row in summary_df_sorted.iterrows():
        ax3.annotate(
            row['file_name'],
            (row['datetime'], row['temperature_mean']),
            textcoords="offset points",
            xytext=(0, 8),
            ha='center',
            fontsize=5,
            rotation=30
        )
    '''

    ax3.set_xlabel("Date")
    ax3.set_ylabel("Temperature [°C]")
    ax3.set_title("Timeseries stats")
    ax3.legend()
    ax3.grid(True)
    fig3.autofmt_xdate()
    fig3.tight_layout()

    st.pyplot(fig3)
    st.markdown("---")
    
    st.markdown(
        """
        <div style='text-align: center; color: grey; font-size: 13px;'>
        CS-MACH1 Project • Ocean Temperature Monitoring Platform
        </div>
        """,
        unsafe_allow_html=True
    )
    # -----------------------------------------------------
    

    st.info("Note: ⭐ stars = 2025 data, ▲ triangles = 2026 data, ■ squares = 2027 data.")
  
   
