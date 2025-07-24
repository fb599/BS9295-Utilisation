import math
import numpy as np
import pandas as pd

# Constants based on BS9295
PERFORATION_REDUCTION = 0.95
SOIL_DENSITY = 19.6        # kN/m³
PIPE_MODULUS_LONG = 150    # Long-term modulus (N/mm²) - Match Word doc example
DEFLECTION_COEFF = 0.083   # BS9295 Table 15
SOIL_MODULUS = 10          # MN/m² (Class S2 native soil)
EMBED_MODULUS = 10         # MN/m² (Class S2 bedding)
DEFLECTION_LAG = 1.0       # BS9295 Table 15 (S2 bedding)
OVAL_LIMIT = 3.0           # Max allowable ovalization (%)

# Initial Ovalization (BS9295 Table 17 - Type B installation)
INITIAL_OVAL = {0: 0.5,    # SDR11 (%)
                1: 2.15}   # SDR17 (%)

# Input data
diameters = [110, 125, 160, 180, 200, 225, 250, 280, 315, 355, 400, 450, 500, 560, 630]
sdr11 = [10.0, 11.4, 14.6, 16.4, 18.2, 20.5, 22.8, 25.5, 28.7, 32.3, 36.4, 40.9, 45.4, 50.8, 57.2]
sdr17 = [6.3, 7.1, 9.1, 10.2, 11.4, 12.8, 14.2, 15.9, 17.9, 20.1, 22.7, 25.5, 28.3, 31.7, 35.7]

# Crown depths from ground level (m)
crown_depths = [0.675, 0.775, 0.875, 0.975, 1.075, 1.175, 1.275, 1.375, 1.575, 1.775, 1.975, 2.175, 2.675, 3.175]

# Surcharge pressures from BS9295 Fig 12 (kN/m²) for depths below sleeper
surcharge_pressure = [690, 480, 340, 245, 185, 140, 110, 95, 75, 65, 50, 40, 25, 15]

def make_pipe_dict(diams, s11, s17):
    return {d: [s11[i], s17[i]] for i, d in enumerate(diams)}

def pipe_stiffness(OD, t, modulus, perforated=True):
    """Calculate pipe stiffness per BS9295 Eq (31) using MEAN DIAMETER"""
    MD = OD - t  # Mean diameter = Outer diameter - thickness
    I = t**3 / 12  # Second moment of area per mm (mm³)
    stiffness_val = (modulus * I) / (MD**3)
    return stiffness_val * PERFORATION_REDUCTION if perforated else stiffness_val

def leonhardt_factor(B_trench, D_pipe, E_soil, E_embed):
    """Calculate Leonhardt's coefficient per BS9295 Eq (29)"""
    ratio = B_trench / D_pipe
    num = 0.985 + 0.544 * ratio
    denom = (1.985 - 0.456 * ratio) * (E_soil / E_embed) - (1 - ratio)
    return num / denom if denom != 0 else 1.0

def ovalization(total_pressure, stiffness, E_eff, sdr_idx):
    """Calculate ovalization per BS9295 Eq (35)"""
    numerator = DEFLECTION_COEFF * DEFLECTION_LAG * total_pressure
    denominator = 8 * stiffness + 0.061 * E_eff
    dynamic_oval = (numerator / denominator) * 100  # Percentage
    total_oval = INITIAL_OVAL[sdr_idx] + dynamic_oval
    return total_oval  # Return actual ovalization percentage

def calculate_ovalization(pipe_dict, depths, surcharges):
    results = []
    
    for dia, (sdr11_thk, sdr17_thk) in pipe_dict.items():
        # Trench width per Excel template
        trench_width = dia + 300  # mm
        
        # Effective soil modulus
        C_L = leonhardt_factor(trench_width, dia, SOIL_MODULUS, EMBED_MODULUS)
        E_eff = EMBED_MODULUS * C_L * 1000  # Convert MN/m² to kN/m²
        
        # Process both SDR types
        for sdr_idx, thickness in enumerate([sdr11_thk, sdr17_thk]):
            sdr_type = "SDR11" if sdr_idx == 0 else "SDR17"
            
            # Long-term stiffness for ovalization (N/mm²)
            stiff_val = pipe_stiffness(dia, thickness, PIPE_MODULUS_LONG)
            stiff_kN = stiff_val * 1000  # Convert N/mm² to kN/m²
            
            for depth_idx, depth in enumerate(depths):
                surcharge = surcharges[depth_idx]
                
                # Total pressure calculation (soil + surcharge)
                soil_pressure = SOIL_DENSITY * depth  # kN/m²
                total_pressure = soil_pressure + surcharge  # kN/m²
                
                # Calculate ovalization
                oval_percent = ovalization(total_pressure, stiff_kN, E_eff, sdr_idx)
                util_percent = (oval_percent / OVAL_LIMIT) * 100  # Utilization percentage
                
                results.append({
                    "Diameter (mm)": dia,
                    "SDR Type": sdr_type,
                    "Thickness (mm)": thickness,
                    "Crown Depth (m)": depth,
                    "Ovalization (%)": oval_percent,
                    "Utilization (%)": util_percent
                })
    
    return pd.DataFrame(results)

# Generate results
pipe_data = make_pipe_dict(diameters, sdr11, sdr17)
df = calculate_ovalization(pipe_data, crown_depths, surcharge_pressure)

# Pivot to match Excel format (ovalization %)
pivot_oval = df.pivot_table(
    index="Crown Depth (m)",
    columns=["Diameter (mm)", "SDR Type"],
    values="Ovalization (%)"
)

# Pivot for utilization %
pivot_util = df.pivot_table(
    index="Crown Depth (m)",
    columns=["Diameter (mm)", "SDR Type"],
    values="Utilization (%)"
)

# Reorder columns to match template
col_order = [(d, sdr) for d in diameters for sdr in ["SDR17", "SDR11"]]
pivot_oval = pivot_oval.reindex(columns=col_order)
pivot_util = pivot_util.reindex(columns=col_order)

# Format output based on utilization
def format_oval_result(val):
    if val <= OVAL_LIMIT:
        return f"PASS ({val:.1f}%)"
    else:
        return f"FAIL ({val:.1f}%)"

formatted_df = pivot_oval.applymap(format_oval_result)

# Export to Excel
with pd.ExcelWriter("Ovalization_Results.xlsx") as writer:
    formatted_df.to_excel(writer, sheet_name="Ovalization Results")
    pivot_util.to_excel(writer, sheet_name="Utilization Percentage")
    pivot_oval.to_excel(writer, sheet_name="Raw Ovalization Values")
    
    # Add metadata sheet
    metadata = pd.DataFrame({
        "Parameter": [
            "Pipe Material", "Bedding Class", "Native Soil Modulus", 
            "Embedment Modulus", "Design Standard", "Ovalization Limit", 
            "Initial Ovalization (SDR11)", "Initial Ovalization (SDR17)", 
            "Perforation Reduction", "Long-term Modulus"
        ],
        "Value": [
            "PE100", "S2 (90% compaction)", "10 MN/m²", "10 MN/m²", 
            "BS9295:2020", "3%", "0.5%", "2.15%", "5%", "150 MPa"
        ]
    })
    metadata.to_excel(writer, sheet_name="Design Parameters", index=False)

# Test with Word document example (110mm SDR11 at 0.675m depth)
test_case = df[
    (df["Diameter (mm)"] == 110) & 
    (df["SDR Type"] == "SDR11") & 
    (df["Crown Depth (m)"] == 0.675)
]

print("Word Document Example Validation:")
print(f"Expected Ovalization: 8.78%")
print(f"Calculated Ovalization: {test_case['Ovalization (%)'].values[0]:.2f}%")
print(f"Expected Utilization: 292.6%")
print(f"Calculated Utilization: {test_case['Utilization (%)'].values[0]:.1f}%")