import streamlit as st
import pandas as pd
import numpy as np
from io import BytesIO

# --- Constants ---
DEFAULT_SOIL_MODULUS = 2.5
DEFAULT_EMBED_MODULUS = 10.0
DEFAULT_PERFORATION_RED = 0.95
DEFAULT_SOIL_DENSITY = 19.6
DEFAULT_WATER_DENSITY = 10.0
DEFAULT_LONG_MODULUS = 150.0
DEFAULT_SHORT_MODULUS = 800.0
DEFAULT_DEFLECTION_COEFF = 0.083
DEFAULT_DEFLECTION_LAG = 1.0
DEFAULT_OVAL_LIMIT = 3.0
DEFAULT_GAMMA_UF = 1.1
DEFAULT_GAMMA_F = 0.9
DEFAULT_BUCKLING_MIN_SAFE = 2.0
DEFAULT_BUCKLING_MIN_SAFE_AIR = 1.5
DEFAULT_TAMPING_DEPTH = 0.4

INITIAL_OVAL = {0: 0.5, 1: 2.15}

PIPE_WEIGHTS = {
    (110, "SDR17"): 2.08 * 0.00980665, (110, "SDR11"): 3.14 * 0.00980665,
    (125, "SDR17"): 2.66 * 0.00980665, (125, "SDR11"): 4.08 * 0.00980665,
    (160, "SDR17"): 4.35 * 0.00980665, (160, "SDR11"): 6.67 * 0.00980665,
    (180, "SDR17"): 5.48 * 0.00980665, (180, "SDR11"): 8.42 * 0.00980665,
    (200, "SDR17"): 6.79 * 0.00980665, (200, "SDR11"): 10.40 * 0.00980665,
    (225, "SDR17"): 8.55 * 0.00980665, (225, "SDR11"): 13.10 * 0.00980665,
    (250, "SDR17"): 10.60 * 0.00980665, (250, "SDR11"): 16.20 * 0.00980665,
    (280, "SDR17"): 13.20 * 0.00980665, (280, "SDR11"): 20.30 * 0.00980665,
    (315, "SDR17"): 16.70 * 0.00980665, (315, "SDR11"): 25.70 * 0.00980665,
    (355, "SDR17"): 21.20 * 0.00980665, (355, "SDR11"): 32.60 * 0.00980665,
    (400, "SDR17"): 26.90 * 0.00980665, (400, "SDR11"): 41.40 * 0.00980665,
    (450, "SDR17"): 34.00 * 0.00980665, (450, "SDR11"): 52.40 * 0.00980665,
    (500, "SDR17"): 41.90 * 0.00980665, (500, "SDR11"): 64.60 * 0.00980665,
    (560, "SDR17"): 52.50 * 0.00980665, (560, "SDR11"): 81.10 * 0.00980665,
    (630, "SDR17"): 66.50 * 0.00980665, (630, "SDR11"): 102.50 * 0.00980665
}

diameters = [110, 125, 160, 180, 200, 225, 250, 280, 315, 355, 400, 450, 500, 560, 630]
sdr11 = [10.0, 11.4, 14.6, 16.4, 18.2, 20.5, 22.8, 25.5, 28.7, 32.3, 36.4, 40.9, 45.4, 50.8, 57.2]
sdr17 = [6.3, 7.1, 9.1, 10.2, 11.4, 12.8, 14.2, 15.9, 17.9, 20.1, 22.7, 25.5, 28.3, 31.7, 35.7]

crown_depths = [0.675, 0.775, 0.875, 0.975, 1.075, 1.175, 1.275, 1.375, 1.575, 1.775, 1.975, 2.175, 2.675, 3.175]
surcharge_pressure = [690, 480, 340, 245, 185, 140, 110, 95, 75, 65, 50, 40, 25, 15]

# --- Streamlit UI ---
st.set_page_config(page_title="PE80/100 Pipe Design Tool SDR11/17", layout="wide")
st.title("PE80/100 SDR11/17 Pipe Structural Design Calculator")

# --- Sidebar with adjustable parameters ---
with st.sidebar:
    st.header("Design Parameters")
    params = {
        "soil_modulus": st.number_input(
            "Native Soil Modulus (MN/m²)",
            value=DEFAULT_SOIL_MODULUS,
            min_value=0.1,
            max_value=100.0,
            step=0.1
        ),
        "embed_modulus": st.number_input(
            "Embedment Modulus (MN/m²)",
            value=DEFAULT_EMBED_MODULUS,
            min_value=0.1,
            max_value=100.0,
            step=0.1
        ),
        "deflection_lag": st.number_input(
            "Deflection Lag Factor",
            value=DEFAULT_DEFLECTION_LAG,
            min_value=0.1,
            max_value=2.0,
            step=0.05
        ),
        "oval_limit": st.number_input(
            "Ovalisation Limit (%)",
            value=DEFAULT_OVAL_LIMIT,
            min_value=1.0,
            max_value=10.0,
            step=0.1
        ),
        "perforation_red": st.number_input(
            "Perforation Reduction Factor",
            value=DEFAULT_PERFORATION_RED,
            min_value=0.01,
            max_value=1.0,
            step=0.01
        )
    }

# --- Functions ---
def make_pipe_dict(diams, s11, s17):
    return {d: [s11[i], s17[i]] for i, d in enumerate(diams)}

def get_pipe_weight(diameter, sdr_type):
    return PIPE_WEIGHTS.get((diameter, sdr_type), 0.16 if sdr_type == "SDR17" else 0.25)

def pipe_stiffness(OD, t, modulus, perforated=True):
    MD = OD - t
    I = t**3 / 12
    stiffness_val = (modulus * I) / (MD**3)
    return stiffness_val * params.get("perforation_red", DEFAULT_PERFORATION_RED) if perforated else stiffness_val

def leonhardt_factor(B_trench, D_pipe, E_soil, E_embed):
    ratio = B_trench / D_pipe
    num = 0.985 + 0.544 * ratio
    denom = (1.985 - 0.456 * ratio) * (E_soil / E_embed) - (1 - ratio)
    return num / denom if denom != 0 else 1.0

def ovalisation(total_pressure, stiffness, E_eff, sdr_idx):
    numerator = DEFAULT_DEFLECTION_COEFF * params["deflection_lag"] * total_pressure
    denominator = 8 * stiffness + 0.061 * E_eff
    dynamic_oval = (numerator / denominator) * 100
    return INITIAL_OVAL[sdr_idx] + dynamic_oval

def calculate_flotation(dia, depth, pipe_weight, invert_level=None):
    OD_m = dia / 1000
    W_soil = DEFAULT_SOIL_DENSITY * depth * OD_m
    W_total = DEFAULT_GAMMA_F * (pipe_weight + W_soil)
    H_w = invert_level if invert_level is not None else depth + OD_m/2
    UPL = DEFAULT_GAMMA_UF * DEFAULT_WATER_DENSITY * H_w * OD_m
    return (UPL / W_total) * 100

def calculate_all_checks(pipe_dict, depths, surcharges):
    results = []
    for dia, (sdr11_thk, sdr17_thk) in pipe_dict.items():
        trench_width = dia + 300
        C_L = leonhardt_factor(trench_width, dia, params["soil_modulus"], params["embed_modulus"])
        E_eff = params["embed_modulus"] * C_L * 1000
        
        for sdr_idx, thickness in enumerate([sdr11_thk, sdr17_thk]):
            sdr_type = "SDR11" if sdr_idx == 0 else "SDR17"
            pipe_weight = get_pipe_weight(dia, sdr_type)
            stiff_val = pipe_stiffness(dia, thickness, DEFAULT_LONG_MODULUS)
            stiff_kN = stiff_val * 1000
            stiff_buck_short = pipe_stiffness(dia, thickness, DEFAULT_SHORT_MODULUS, perforated=False)
            stiff_buck_long = pipe_stiffness(dia, thickness, DEFAULT_LONG_MODULUS, perforated=False)
            
            for depth_idx, depth in enumerate(depths):
                surcharge = surcharges[depth_idx]
                soil_pressure = DEFAULT_SOIL_DENSITY * depth
                total_pressure = soil_pressure + surcharge
                oval_percent = ovalisation(total_pressure, stiff_kN, E_eff, sdr_idx)
                oval_util = oval_percent / params["oval_limit"]
                flotation_util = calculate_flotation(dia, depth, pipe_weight) / 100
                buckling_air_util = 0
                
                if depth < 1.5:
                    P_cr_a = 24 * stiff_buck_short * 1000
                    FOS_air = P_cr_a / (soil_pressure + surcharge)
                    buckling_air_util = DEFAULT_BUCKLING_MIN_SAFE_AIR / FOS_air
                
                P_cr_short = 0.6 * (E_eff/1000)**0.67 * stiff_buck_short**0.33
                P_cr_long = 0.6 * (E_eff/1000)**0.67 * stiff_buck_long**0.33
                P_cr_short_kN = P_cr_short * 1000
                P_cr_long_kN = P_cr_long * 1000
                FOS_soil = 1 / (soil_pressure/P_cr_long_kN + surcharge/P_cr_short_kN)
                buckling_soil_util = DEFAULT_BUCKLING_MIN_SAFE / FOS_soil
                
                util_checks = [oval_util, flotation_util, buckling_soil_util]
                if depth < 1.5:
                    util_checks.append(buckling_air_util)
                
                max_util = max(util_checks)
                overall_status = "FAIL (101%)" if max_util > 1.0 else f"PASS ({max_util*100:.1f}%)"
                
                # Format individual checks
                oval_display = f"FAIL ({oval_percent:.1f}%)" if oval_util > 1 else f"PASS ({oval_percent:.1f}%)"
                flotation_display = f"FAIL ({flotation_util*100:.1f}%)" if flotation_util > 1 else f"PASS ({flotation_util*100:.1f}%)"
                buckling_soil_display = f"FAIL ({buckling_soil_util*100:.1f}%)" if buckling_soil_util > 1 else f"PASS ({buckling_soil_util*100:.1f}%)"
                buckling_air_display = ""
                if depth < 1.5:
                    buckling_air_display = f"FAIL ({buckling_air_util*100:.1f}%)" if buckling_air_util > 1 else f"PASS ({buckling_air_util*100:.1f}%)"
                
                results.append({
                    "Diameter (mm)": dia,
                    "SDR Type": sdr_type,
                    "Crown Depth (m)": depth,
                    "Ovalisation": oval_display,
                    "Flotation": flotation_display,
                    "Buckling (Soil)": buckling_soil_display,
                    "Buckling (Air)": buckling_air_display if depth < 1.5 else "N/A",
                    "Overall Status": overall_status,
                    "Tamping Safe": "YES" if depth >= DEFAULT_TAMPING_DEPTH else "NO"
                })
    return pd.DataFrame(results)

# --- Main App Logic ---
pipe_data = make_pipe_dict(diameters, sdr11, sdr17)

if st.button("Run Design Checks"):
    with st.spinner("Calculating..."):
        df = calculate_all_checks(pipe_data, crown_depths, surcharge_pressure)
    
    st.success("✅ Calculations completed.")
    
    # Display results in a more organized way
    st.subheader("Design Results Summary")
    
    # Create tabs for different views
    tab1, tab2 = st.tabs(["Detailed Results", "Summary by Diameter"])
    
    with tab1:
        st.dataframe(df)
    
    with tab2:
        # Pivot the data for a better summary view
        summary_df = df.pivot_table(
            index=["Diameter (mm)", "SDR Type"],
            columns="Crown Depth (m)",
            values="Overall Status",
            aggfunc='first'
        )
        st.dataframe(summary_df)
    
    # Excel Export with error handling
    try:
        buffer = BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            # Main results sheet
            df.to_excel(writer, index=False, sheet_name="Summary Results")
            
            # Additional sheets with detailed calculations
            summary_df.to_excel(writer, sheet_name="Summary by Diameter")
            
            # Parameters sheet
            params_df = pd.DataFrame({
                "Parameter": [
                    "Pipe Material", "Bedding Class", "Native Soil Modulus", 
                    "Embedment Modulus", "Design Standard", "Ovalisation Limit",
                    "Initial Ovalisation (SDR11)", "Initial Ovalisation (SDR17)",
                    "Perforation Reduction", "Long-term Modulus", "Short-term Modulus",
                    "Water Density", "Soil Density", "Uplift Partial Factor (unfav)",
                    "Uplift Partial Factor (fav)", "Buckling FOS (soil)", 
                    "Buckling FOS (air)", "Min Tamping Depth"
                ],
                "Value": [
                    "PE100", "S2 (90% compaction)", f"{params['soil_modulus']} MN/m²",
                    f"{params['embed_modulus']} MN/m²", "BS9295:2020", f"{params['oval_limit']}%",
                    f"{INITIAL_OVAL[0]}%", f"{INITIAL_OVAL[1]}%", 
                    f"{int((1 - params['perforation_red']) * 100)}%", f"{DEFAULT_LONG_MODULUS} MPa",
                    f"{DEFAULT_SHORT_MODULUS} MPa", f"{DEFAULT_WATER_DENSITY} kN/m³",
                    f"{DEFAULT_SOIL_DENSITY} kN/m³", f"{DEFAULT_GAMMA_UF}",
                    f"{DEFAULT_GAMMA_F}", f"{DEFAULT_BUCKLING_MIN_SAFE}",
                    f"{DEFAULT_BUCKLING_MIN_SAFE_AIR}", f"{DEFAULT_TAMPING_DEPTH} m"
                ]
            })

            params_df.to_excel(writer, index=False, sheet_name="Design Parameters")
            
        st.download_button(
            "📥 Download Full Excel Report",
            data=buffer.getvalue(),
            file_name="Pipe_Design_Results.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    except Exception as e:
        st.error(f"Excel export failed: {str(e)}. Showing data as CSV instead.")
        st.download_button(
            "📥 Download CSV",
            data=df.to_csv(index=False).encode('utf-8'),
            file_name="Pipe_Design_Results.csv",
            mime="text/csv"
        )

# git commands to save changes

# git add .
# git commit -m "Added adjustable parameters to Streamlit app and improved export functionality"
# git push

st.write("Note: 101(%) Overall Utilisation Denotes Failure")
