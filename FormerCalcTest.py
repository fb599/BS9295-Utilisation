import math
import numpy as np
import pandas as pd

### ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ ###

'''Constants for pipe design calculations based on BS9295:2020'''

# Native soil and embedment moduli
soil_modulus = 3          # MN/m² (Class S2 native soil)
embed_modulus = 10         # MN/m² (Class S2 bedding)

# Other constants based on BS9295
perforation_red = 0.95     # Perforation stiffness reduction factor
soil_density = 19.6        # kN/m³
water_density = 10.0       # kN/m³
long_modulus = 150         # N/mm² (pipe long-term modulus)
short_modulus = 800        # N/mm² (pipe short-term modulus)
deflection_coeff = 0.083   # BS9295 Table 15
deflection_lag = 1.0       # BS9295 Table 15 (S2 bedding @90% compaction)
oval_limit = 5.0           # Max allowable ovalisation (%)
gamma_uf = 1.1             # Partial factor (permanent unfavorable)
gamma_f = 0.9              # Partial factor (permanent favorable)
BUCKLING_FOS_MIN = 2.0     # Minimum factor of safety for buckling with soil
BUCKLING_FOS_MIN_AIR = 1.5 # Minimum factor of safety for buckling without soil
tamping_depth = 0.4        # Minimum depth to avoid tamping damage (m)

### ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ ###

'''Dictionaries for pipe properties which vary depending on SDR'''

# Initial Ovalisation due to Type B installation
INITIAL_OVAL = {0: 1.25,    # SDR11 (%)
                1: 1.25}   # SDR17 (%)

# Pipe weights obtained from BS9295 (kN/m)
PIPE_WEIGHTS = {
    "SDR11": 0.25,
    "SDR17": 0.16
}

### ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ ###

'''Key property arrays to be used in calculations'''

# Fixed input data for pipe diameters and SDR thicknesses
diameters = [110, 125, 160, 180, 200, 225, 250, 280, 315, 355, 400, 450, 500, 560, 630]             
sdr11 = [10.0, 11.4, 14.6, 16.4, 18.2, 20.5, 22.8, 25.5, 28.7, 32.3, 36.4, 40.9, 45.4, 50.8, 57.2]
sdr17 = [6.3, 7.1, 9.1, 10.2, 11.4, 12.8, 14.2, 15.9, 17.9, 20.1, 22.7, 25.5, 28.3, 31.7, 35.7]

# Crown depths from ground level (m)
crown_depths = [0.675, 0.775, 0.875, 0.975, 1.075, 1.175, 1.275, 1.375, 1.575, 1.775, 1.975, 2.175, 2.675, 3.175]

# Surcharge pressures obtained from BS9295 Fig 12 (kN/m²) for depths below sleeper
surcharge_pressure = [690, 480, 340, 245, 185, 140, 110, 95, 75, 65, 50, 40, 25, 15]

### ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ ###

'''Functions used throughout to facilitate overall utilisation calculation'''


# Reformatting function to create a dictionary of pipe properties
def make_pipe_dict(diams, s11, s17):
    return {d: [s11[i], s17[i]] for i, d in enumerate(diams)}


# Calculate pipe stiffness per BS9295 Eq (31) using MEAN DIAMETER
def pipe_stiffness(OD, t, modulus, perforated=True):

    MD = OD - t  # Mean diameter = Outer diameter - thickness
    I = t**3 / 12  # Second moment of area per mm (mm³)
    stiffness_val = (modulus * I) / (MD**3)

    return stiffness_val * perforation_red if perforated else stiffness_val


# Calculate Leonhardt's coefficient per BS9295 Eq (29)
def leonhardt_factor(B_trench, D_pipe, E_soil, E_embed):
    
    ratio = B_trench / D_pipe
    num = 0.985 + 0.544 * ratio
    denom = (1.985 - 0.456 * ratio) * (E_soil / E_embed) - (1 - ratio)

    return num / denom if denom != 0 else 1.0


# Calculate ovalisation per BS9295 Eq (35)
def ovalisation(total_pressure, stiffness, E_eff, sdr_idx):

    numerator = deflection_coeff * deflection_lag * total_pressure
    denominator = 8 * stiffness + 0.061 * E_eff
    dynamic_oval = (numerator / denominator) * 100  # Percentage

    return INITIAL_OVAL[sdr_idx] + dynamic_oval  # Return the total actual ovalisation percentage


# Calculate flotation and corresponding utilisation
def calculate_flotation(dia, depth, pipe_weight, invert_level=None):
    
    OD_m = dia / 1000  # Convert mm to m
    
    # Weight of soil (rectangular column) and total downward force (factored)
    W_soil = soil_density * depth * OD_m * 1.0  # kN (for 1m length)
    W_total = gamma_f * (pipe_weight + W_soil)
    
    # Uplift force (factored)
    if invert_level is not None:
        H_w = invert_level  # Most accurate when IL is known
    else:
        H_w = depth + OD_m/2  # Fallback calculation (CL + OD/2)
    
    UPL = gamma_uf * water_density * H_w * OD_m * 1.0  # kN (per metre length)
    
    return (UPL / W_total) * 100  # Utilisation percentage

### ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ ###

'''Calculating the overall utilisation (previous constants and functions remain the same until calculate_all_checks)'''


def calculate_all_checks(pipe_dict, depths, surcharges):
    results = []
    
    for dia, (sdr11_thk, sdr17_thk) in pipe_dict.items():
        # Trench width per Excel template
        trench_width = dia + 300  # mm
        
        # Effective soil modulus
        C_L = leonhardt_factor(trench_width, dia, soil_modulus, embed_modulus)
        E_eff = embed_modulus * C_L * 1000  # Convert MN/m² to kN/m²
        
        # Process both SDR types
        for sdr_idx, thickness in enumerate([sdr11_thk, sdr17_thk]):
            sdr_type = "SDR11" if sdr_idx == 0 else "SDR17"
            pipe_weight = PIPE_WEIGHTS[sdr_type]  # kN/m
            
            # Long-term stiffness for ovalisation (N/mm²)
            stiff_val = pipe_stiffness(dia, thickness, long_modulus)
            stiff_kN = stiff_val * 1000  # Convert N/mm² to kN/m²
            
            # Stiffness for buckling (without perforation reduction)
            stiff_buck_short = pipe_stiffness(dia, thickness, short_modulus, perforated=False)
            stiff_buck_long = pipe_stiffness(dia, thickness, long_modulus, perforated=False)
            
            # Mean diameter
            MD = dia - thickness  # mm
            
            for depth_idx, depth in enumerate(depths):
                surcharge = surcharges[depth_idx]
                
                # ================ OVALISATION CHECK ================
                soil_pressure = soil_density * depth  # kN/m²
                total_pressure = soil_pressure + surcharge  # kN/m²
                oval_percent = ovalisation(total_pressure, stiff_kN, E_eff, sdr_idx)
                oval_util = oval_percent / oval_limit  # As decimal
                
                # ================= FLOTATION CHECK =================
                flotation_util = calculate_flotation(
                    dia=dia,
                    depth=depth,
                    pipe_weight=pipe_weight,
                    invert_level=None  # !Pass actual invert_level if available!
                ) / 100  # Convert percentage to decimal
                
                # ================ BUCKLING CHECKS ================
                # Without soil (for covers < 1.5m)
                buckling_air_util = 0
                if depth < 1.5:
                    P_cr_a = 24 * stiff_buck_short * 1000  # kN/m²
                    FOS_air = P_cr_a / (soil_pressure + surcharge)
                    buckling_air_util = BUCKLING_FOS_MIN_AIR / FOS_air  # As decimal
                
                # With soil support
                P_cr_short = 0.6 * (E_eff/1000)**0.67 * (stiff_buck_short)**0.33  # MN/m²
                P_cr_long = 0.6 * (E_eff/1000)**0.67 * (stiff_buck_long)**0.33  # MN/m²
                P_cr_short_kN = P_cr_short * 1000  # kN/m²
                P_cr_long_kN = P_cr_long * 1000  # kN/m²
                FOS_soil = 1 / (soil_pressure/P_cr_long_kN + surcharge/P_cr_short_kN)
                buckling_soil_util = BUCKLING_FOS_MIN / FOS_soil  # As decimal
                
                # ================ OVERALL UTILISATION ================
                util_checks = [oval_util, flotation_util, buckling_soil_util]
                if depth < 1.5:
                    util_checks.append(buckling_air_util)
                
                max_util = max(util_checks)
                overall_status = 101 if max_util > 1.0 else max_util * 100  # Final percentage
                
                results.append({
                    "Diameter (mm)": dia,
                    "SDR Type": sdr_type,
                    "Thickness (mm)": thickness,
                    "Crown Depth (m)": depth,
                    "Ovalisation (%)": oval_percent,
                    "Ovalisation Util": oval_util * 100,
                    "Flotation Util": flotation_util * 100,
                    "Buckling Air Util": buckling_air_util * 100 if depth < 1.5 else np.nan,
                    "Buckling Soil Util": buckling_soil_util * 100,
                    "Tamping Safe": "YES" if depth >= tamping_depth else "NO",
                    "Overall Util": overall_status
                })
    
    return pd.DataFrame(results)

### ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ ###

'''Generating results'''

# Generate results
pipe_data = make_pipe_dict(diameters, sdr11, sdr17)
df = calculate_all_checks(pipe_data, crown_depths, surcharge_pressure)

### ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ ###

'''Exporting results to Excel with formatting (heavily AI assisted change formatting as required)'''


# ================ CREATE PIVOT TABLES ================

# Function to create pivot table
def create_pivot(df, value_col, columns_order):

    pivot_df = df.pivot_table(
        index="Crown Depth (m)",
        columns=["Diameter (mm)", "SDR Type"],
        values=value_col
    )

    return pivot_df.reindex(columns=columns_order)

# Column order for all tables
col_order = [(d, sdr) for d in diameters for sdr in ["SDR17", "SDR11"]]

# Create individual tables
pivot_oval = create_pivot(df, "Ovalisation Util", col_order)
pivot_flotation = create_pivot(df, "Flotation Util", col_order)
pivot_buckling_air = create_pivot(df, "Buckling Air Util", col_order)
pivot_buckling_soil = create_pivot(df, "Buckling Soil Util", col_order)
pivot_overall = create_pivot(df, "Overall Util", col_order)
pivot_tamping = df.pivot_table(
    index="Crown Depth (m)",
    columns=["Diameter (mm)", "SDR Type"],
    values="Tamping Safe",
    aggfunc="first"  # Use 'first' to avoid aggregation issues with strings
).reindex(columns=col_order)


# Create raw ovalisation table
pivot_oval_raw = create_pivot(df, "Ovalisation (%)", col_order)


# ================ FORMATTING FUNCTIONS ================

def format_oval(val):
    if val <= oval_limit:
        return f"PASS ({val:.1f}%)"
    return f"FAIL ({val:.1f}%)"


def format_util(val):
    if val <= 100:
        return f"{val:.1f}%"
    return "FAIL"


def format_tamping(val):
    return val


def format_overall(val):
    return f"{val:.1f}"  # Just the number, no percent sign or FAIL


# Apply formatting
formatted_oval = pivot_oval_raw.map(format_oval)
formatted_flotation = pivot_flotation.map(format_util)
formatted_buckling_air = pivot_buckling_air.map(format_util)
formatted_buckling_soil = pivot_buckling_soil.map(format_util)
formatted_tamping = pivot_tamping.map(format_tamping)


# ================ EXPORT TO EXCEL ================

with pd.ExcelWriter("Pipe_Design_Results.xlsx") as writer:
    # Formatted results sheets
    formatted_oval.to_excel(writer, sheet_name="Ovalisation Results")
    formatted_flotation.to_excel(writer, sheet_name="Flotation Utilisation")
    formatted_buckling_air.to_excel(writer, sheet_name="Buckling Air Utilisation")
    formatted_buckling_soil.to_excel(writer, sheet_name="Buckling Soil Utilisation")
    formatted_tamping.to_excel(writer, sheet_name="Tamping Safety")
    pivot_overall.to_excel(writer, sheet_name="Overall Utilisation")
    
    # Raw data sheets
    pivot_oval_raw.to_excel(writer, sheet_name="Raw Ovalisation")
    pivot_oval.to_excel(writer, sheet_name="Raw Ovalisation Util")
    pivot_flotation.to_excel(writer, sheet_name="Raw Flotation Util")
    pivot_buckling_air.to_excel(writer, sheet_name="Raw Buckling Air Util")
    pivot_buckling_soil.to_excel(writer, sheet_name="Raw Buckling Soil Util")
    pivot_overall.to_excel(writer, sheet_name="Raw Overall Util")
    
    # Add metadata sheet
    metadata = pd.DataFrame({
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
            "PE100", "S2 (90% compaction)", "10 MN/m²", "10 MN/m²", 
            "BS9295:2020", "3%", "0.5%", "2.15%", "5%", "150 MPa", "800 MPa",
            "10 kN/m³", "19.6 kN/m³", "1.1", "0.9", "2.0", "1.5", "0.4 m"
        ]
    })
    metadata.to_excel(writer, sheet_name="Design Parameters", index=False)


# Test with Word document example (110mm SDR11 at 0.675m depth and 10MN/m² Native Soil Modulus)
test_case = df[
    (df["Diameter (mm)"] == 110) & 
    (df["SDR Type"] == "SDR11") & 
    (df["Crown Depth (m)"] == 0.675)
]


print("Word Document Example Validation:")
print(f"Expected Ovalisation: 8.78%")
print(f"Calculated Ovalisation: {test_case['Ovalisation (%)'].values[0]:.2f}%")
print(f"Expected Utilisation: 292.6%")
print(f"Calculated Utilisation: {test_case['Ovalisation Util'].values[0]:.1f}%")
print("\nFlotation Check:")
print(f"Expected Utilisation: 61.9%")
print(f"Calculated Utilisation: {test_case['Flotation Util'].values[0]:.1f}%")
print("\nBuckling with Soil:")
print(f"Expected Utilisation: 124.2%")
print(f"Calculated Utilisation: {test_case['Buckling Soil Util'].values[0]:.1f}%")
print("\nOverall Utilisation:")
print(f"Expected: 292.6%")
print(f"Calculated: {test_case['Overall Util'].values[0]:.1f}%")