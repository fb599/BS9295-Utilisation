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
st.set_page_config(page_title="PE Pipe Design Checker", layout="wide")
st.title("PE100 SDR11/17 Pipe Design Calculator")

with st.sidebar:
    st.header("Design Parameters")
    params = {
        "soil_modulus": st.number_input("Native Soil Modulus (MN/m²)", value=DEFAULT_SOIL_MODULUS),
        "embed_modulus": st.number_input("Embedment Modulus (MN/m²)", value=DEFAULT_EMBED_MODULUS),
        "deflection_lag": st.number_input("Deflection Lag Factor", value=DEFAULT_DEFLECTION_LAG),
        "oval_limit": st.number_input("Ovalisation Limit (%)", value=DEFAULT_OVAL_LIMIT),
        "perforation_red": st.number_input("Perforation Reduction Factor", value=DEFAULT_PERFORATION_RED)
    }

def make_pipe_dict(diams, s11, s17):
    return {d: [s11[i], s17[i]] for i, d in enumerate(diams)}

def get_pipe_weight(diameter, sdr_type):
    return PIPE_WEIGHTS.get((diameter, sdr_type), 0.16 if sdr_type=="SDR17" else 0.25)

def pipe_stiffness(OD, t, modulus, perforated=True):
    MD = OD - t
    I = t**3 / 12
    base = (modulus * I) / (MD**3)
    return base * DEFAULT_PERFORATION_RED if perforated else base

def leonhardt_factor(B_trench, D_pipe, E_soil, E_embed):
    ratio = B_trench / D_pipe
    num = 0.985 + 0.544 * ratio
    denom = (1.985 - 0.456 * ratio) * (E_soil / E_embed) - (1 - ratio)
    return num/denom if denom != 0 else 1.0

def calculate_flotation(dia, depth, pipe_weight, invert_level=None):
    OD_m = dia / 1000
    W_soil = DEFAULT_SOIL_DENSITY * depth * OD_m
    W_total = DEFAULT_GAMMA_F * (pipe_weight + W_soil)
    H_w = invert_level if invert_level is not None else depth + OD_m/2
    UPL = DEFAULT_GAMMA_UF * DEFAULT_WATER_DENSITY * H_w * OD_m
    return UPL/W_total

def calculate_all_checks(pipe_dict, depths, surcharges):
    rows = []
    for dia, (t11, t17) in pipe_dict.items():
        trench_width = dia + 300
        C_L = leonhardt_factor(trench_width, dia, params["soil_modulus"], params["embed_modulus"])
        E_eff = params["embed_modulus"] * C_L * 1000
        for sdr_idx, thickness in enumerate([t11, t17]):
            sdr = "SDR11" if sdr_idx==0 else "SDR17"
            pw = get_pipe_weight(dia, sdr)
            stiff_long = pipe_stiffness(dia, thickness, DEFAULT_LONG_MODULUS)
            stiff_kN = stiff_long * 1000
            stiff_short = pipe_stiffness(dia, thickness, DEFAULT_SHORT_MODULUS, perforated=False)
            stiff_long_no = pipe_stiffness(dia, thickness, DEFAULT_LONG_MODULUS, perforated=False)
            for idx, depth in enumerate(depths):
                surcharge = surcharges[idx]
                soil_p = DEFAULT_SOIL_DENSITY * depth
                total_p = soil_p + surcharge
                oval_pct = (DEFAULT_DEFLECTION_COEFF * DEFAULT_DEFLECTION_LAG * total_p)/(8*stiff_kN + 0.061*E_eff)*100 + INITIAL_OVAL[sdr_idx]
                oval_util = oval_pct/params["oval_limit"]
                float_util = calculate_flotation(dia, depth, pw)
                air_util = 0
                if depth < 1.5:
                    Pcr_a = 24 * stiff_short * 1000
                    FOSa = Pcr_a/(soil_p + surcharge)
                    air_util = DEFAULT_BUCKLING_MIN_SAFE_AIR / FOSa
                Pcr_s = 0.6*(E_eff/1000)**0.67 * stiff_short**0.33
                Pcr_l = 0.6*(E_eff/1000)**0.67 * stiff_long_no**0.33
                FOSs = 1/(soil_p/(Pcr_l*1000) + surcharge/(Pcr_s*1000))
                soil_util = DEFAULT_BUCKLING_MIN_SAFE / FOSs
                util_list = [oval_util, float_util, soil_util] + ([air_util] if depth<1.5 else [])
                overall = min(max(util_list)*100, 100.0)
                rows.append({
                    "Diameter (mm)": dia,
                    "SDR Type": sdr,
                    "Crown Depth (m)": depth,
                    "Overall Utilisation (%)": overall
                })
    return pd.DataFrame(rows)
    
# --- Main Execution ---
if st.button("Generate Summary Table"):
    with st.spinner("Calculating utilisation..."):
        pipe_dict = make_pipe_dict(diameters=sdr11 + sdr17, sdr11=sdr11, sdr17=sdr17)
        df = calculate_table(pipe_dict, crown_depths, surcharge_pressure)

    st.success("✅ Summary generated.")
    st.dataframe(df, use_container_width=True)

    # Excel Export
    try:
        buffer = BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name="Summary Results")

            # Optional: diameter summary by transposing
            transposed = df.set_index("Crown Depth (m)").T
            transposed.to_excel(writer, sheet_name="Summary by Diameter")

            # Design Parameters
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
                    f"{params['embed_modulus']} MN/m²", "BS9295:2020", f"{params['oval_limit']}",
                    f"{INITIAL_OVAL[1]}", f"{INITIAL_OVAL[0]}", 
                    f"{params['perforation_red']}", f"{DEFAULT_LONG_MODULUS} MPa",
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

st.write("Note: 100(%) Overall Utilisation Denotes Failure")
