import streamlit as st
import pandas as pd
from io import BytesIO

# Constants
DEFAULT_DEFLECTION_COEFF = 0.108
DEFAULT_LONG_MODULUS = 1000
DEFAULT_SHORT_MODULUS = 1200
DEFAULT_WATER_DENSITY = 9.81
DEFAULT_SOIL_DENSITY = 18
DEFAULT_GAMMA_UF = 1.1
DEFAULT_GAMMA_F = 1.5
DEFAULT_BUCKLING_MIN_SAFE = 2.0
DEFAULT_BUCKLING_MIN_SAFE_AIR = 1.5
DEFAULT_TAMPING_DEPTH = 0.3
INITIAL_OVAL = [2.0, 3.0]  # SDR11, SDR17

params = {
    "soil_modulus": 30,
    "embed_modulus": 120,
    "oval_limit": 6.0,
    "deflection_lag": 1.0,
    "perforation_red": 0.1,
}

# Sample calculation functions
def calculate_utilisation(total_pressure, stiffness, E_eff, sdr_idx):
    numerator = DEFAULT_DEFLECTION_COEFF * params["deflection_lag"] * total_pressure
    denominator = 8 * stiffness + 0.061 * E_eff
    dynamic_oval = (numerator / denominator) * 100
    total_oval = INITIAL_OVAL[sdr_idx] + dynamic_oval
    utilisation = total_oval / params["oval_limit"]
    utilisation_percent = min(utilisation * 100, 100.00)  # Cap at 100
    return f"{utilisation_percent:.2f}"

# Dummy data
summary_data = {
    "Pipe Size (mm)": [100, 150, 200],
    "Total Pressure (kN/m²)": [35, 50, 65],
    "Stiffness (kN/m²)": [800, 1000, 1100],
    "Effective Modulus (MPa)": [900, 950, 1000],
    "SDR Index": [0, 1, 0],  # 0 = SDR11, 1 = SDR17
}

summary_df = pd.DataFrame(summary_data)
summary_df["Overall Utilisation (%)"] = summary_df.apply(
    lambda row: calculate_utilisation(
        row["Total Pressure (kN/m²)"],
        row["Stiffness (kN/m²)"],
        row["Effective Modulus (MPa)"],
        row["SDR Index"]
    ),
    axis=1
)

# Display
st.title("Pipe Design Summary")
st.markdown("### Overall Utilisation (%)")
st.dataframe(summary_df[["Pipe Size (mm)", "Overall Utilisation (%)"]], use_container_width=True)

# Excel Export with error handling
try:
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        # Main results sheet
        summary_df.to_excel(writer, index=False, sheet_name="Summary Results")

        # Summary by diameter or other grouping could go here
        # For now we just re-use same df
        summary_df.to_excel(writer, sheet_name="Summary by Diameter", index=False)

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
        data=summary_df.to_csv(index=False).encode('utf-8'),
        file_name="Pipe_Design_Results.csv",
        mime="text/csv"
    )

# git commands to save changes

# git add .
# git commit -m "Added adjustable parameters to Streamlit app and improved export functionality"
# git push

st.write("Note: 101(%) Overall Utilisation Denotes Failure")
