import streamlit as st
import pandas as pd
import numpy as np
from io import BytesIO

st.set_page_config(page_title="PE100 Pipe Design Tool", layout="wide")

# --- Constants ---
soil_modulus = 2.5
embed_modulus = 10
perforation_red = 0.95
soil_density = 19.6
water_density = 10.0
long_modulus = 150
short_modulus = 800
deflection_coeff = 0.083
deflection_lag = 1.0
oval_limit = 3.0
gamma_uf = 1.1
gamma_f = 0.9
buckling_min_safe = 2.0
buckli_min_safe_air = 1.5
tamping_depth = 0.4

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

def make_pipe_dict(diams, s11, s17):
    return {d: [s11[i], s17[i]] for i, d in enumerate(diams)}

def get_pipe_weight(diameter, sdr_type):
    return PIPE_WEIGHTS.get((diameter, sdr_type), 0.16 if sdr_type == "SDR17" else 0.25)

def pipe_stiffness(OD, t, modulus, perforated=True):
    MD = OD - t
    I = t**3 / 12
    stiffness_val = (modulus * I) / (MD**3)
    return stiffness_val * perforation_red if perforated else stiffness_val

def leonhardt_factor(B_trench, D_pipe, E_soil, E_embed):
    ratio = B_trench / D_pipe
    num = 0.985 + 0.544 * ratio
    denom = (1.985 - 0.456 * ratio) * (E_soil / E_embed) - (1 - ratio)
    return num / denom if denom != 0 else 1.0

def ovalisation(total_pressure, stiffness, E_eff, sdr_idx):
    numerator = deflection_coeff * deflection_lag * total_pressure
    denominator = 8 * stiffness + 0.061 * E_eff
    dynamic_oval = (numerator / denominator) * 100
    return INITIAL_OVAL[sdr_idx] + dynamic_oval

def calculate_flotation(dia, depth, pipe_weight, invert_level=None):
    OD_m = dia / 1000
    W_soil = soil_density * depth * OD_m
    W_total = gamma_f * (pipe_weight + W_soil)
    H_w = invert_level if invert_level is not None else depth + OD_m/2
    UPL = gamma_uf * water_density * H_w * OD_m
    return (UPL / W_total) * 100

def calculate_all_checks(pipe_dict, depths, surcharges):
    results = []
    for dia, (sdr11_thk, sdr17_thk) in pipe_dict.items():
        trench_width = dia + 300
        C_L = leonhardt_factor(trench_width, dia, soil_modulus, embed_modulus)
        E_eff = embed_modulus * C_L * 1000
        for sdr_idx, thickness in enumerate([sdr11_thk, sdr17_thk]):
            sdr_type = "SDR11" if sdr_idx == 0 else "SDR17"
            pipe_weight = get_pipe_weight(dia, sdr_type)
            stiff_val = pipe_stiffness(dia, thickness, long_modulus)
            stiff_kN = stiff_val * 1000
            stiff_buck_short = pipe_stiffness(dia, thickness, short_modulus, perforated=False)
            stiff_buck_long = pipe_stiffness(dia, thickness, long_modulus, perforated=False)
            for depth_idx, depth in enumerate(depths):
                surcharge = surcharges[depth_idx]
                soil_pressure = soil_density * depth
                total_pressure = soil_pressure + surcharge
                oval_percent = ovalisation(total_pressure, stiff_kN, E_eff, sdr_idx)
                oval_util = oval_percent / oval_limit
                flotation_util = calculate_flotation(dia, depth, pipe_weight) / 100
                buckling_air_util = 0
                if depth < 1.5:
                    P_cr_a = 24 * stiff_buck_short * 1000
                    FOS_air = P_cr_a / (soil_pressure + surcharge)
                    buckling_air_util = buckli_min_safe_air / FOS_air
                P_cr_short = 0.6 * (E_eff/1000)**0.67 * stiff_buck_short**0.33
                P_cr_long = 0.6 * (E_eff/1000)**0.67 * stiff_buck_long**0.33
                P_cr_short_kN = P_cr_short * 1000
                P_cr_long_kN = P_cr_long * 1000
                FOS_soil = 1 / (soil_pressure/P_cr_long_kN + surcharge/P_cr_short_kN)
                buckling_soil_util = buckling_min_safe / FOS_soil
                util_checks = [oval_util, flotation_util, buckling_soil_util]
                if depth < 1.5:
                    util_checks.append(buckling_air_util)
                max_util = max(util_checks)
                overall_status = 101 if max_util > 1.0 else max_util * 100
                results.append({
                    "Diameter (mm)": dia,
                    "SDR Type": sdr_type,
                    "Crown Depth (m)": depth,
                    "Ovalisation (%)": oval_percent,
                    "Overall Utilisation (%)": overall_status,
                    "Flotation Util (%)": flotation_util * 100,
                    "Buckling Soil Util (%)": buckling_soil_util * 100,
                    "Tamping Safe": "YES" if depth >= tamping_depth else "NO"
                })
    return pd.DataFrame(results)

# --- Streamlit UI ---

st.title("PE100 Pipe Structural Design Calculator")

pipe_data = make_pipe_dict(diameters, sdr11, sdr17)

if st.button("Run Design Checks"):
    df = calculate_all_checks(pipe_data, crown_depths, surcharge_pressure)
    st.success("✅ Calculations completed.")
    st.dataframe(df)

    # Export to Excel
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Design Results')
    buffer.seek(0)
    st.download_button("📥 Download Excel Report", data=buffer, file_name="Pipe_Design_Results.xlsx")

