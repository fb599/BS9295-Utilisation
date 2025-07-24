import math
import numpy as np
import pandas as pd

# Constants
PERFORATION_REDUCTION = 0.95
WATER_DENSITY = 10  # kN/m³
SOIL_DENSITY = 19.6  # kN/m³
PIPE_MODULUS = 150  # MN/m² (converted to N/mm²)
DEFLECTION_COEFF = 0.083
SOIL_MODULUS = 10  # MN/m²
EMBED_MODULUS = 10  # MN/m²

# Precomputed values
INITIAL_OVAL = {0: 0.5, 1: 2.15}  # For SDR11 and SDR17
PIPE_WEIGHT = {0: 0.25, 1: 0.16}  # kN/m for SDR11 and SDR17

def dictionary(diameters, sdr11, sdr17):
    return {d: [s11, s17] for d, s11, s17 in zip(diameters, sdr11, sdr17)}

def stiffness(outer_diameter, thickness, perforated):

    """Calculate pipe stiffness (N/mm²)."""
    unit_I = thickness**4 / 12  # mm⁴/mm

    # Use OUTER diameter for buckling (BS 9295 Eq. 34)
    stiffness_val = (PIPE_MODULUS * unit_I) / (outer_diameter**3)
    return stiffness_val * PERFORATION_REDUCTION if perforated else stiffness_val

def leonhardt(trench_width, outer_diameter, soil_mod, embed_mod):

    """Effective soil modulus correction."""
    if 4.3 * outer_diameter < trench_width:
        return 1.0
    return (0.985 + 0.544 * (trench_width / outer_diameter)) / ((1.985 - 0.456 * (trench_width / outer_diameter)) * (soil_mod / embed_mod) - (1 - (trench_width / outer_diameter)))

def buckling(stiffness_val, effective_soil_mod, pressures):

    """Buckling resistance safety factors."""
    buck_res = 0.6 * (stiffness_val * effective_soil_mod)**(1/3) * effective_soil_mod**(2/3)
    return [buck_res / p for p in pressures]

def ovalisation(deflection_coeff, pressure, stiffness_val, eff_soil_mod, sdr_index):

    """Total ovalisation factor (%)."""
    dynamic_oval = (deflection_coeff * pressure) / (8 * stiffness_val + 0.061 * eff_soil_mod)
    return (INITIAL_OVAL[sdr_index] + dynamic_oval) / 3.0  # Normalized to 3%

def flotation(outer_diameter, soil_depth, sdr_index):

    """Flotation safety factor."""
    outer_dia_m = outer_diameter / 1000  # m
    weight_water = (math.pi * (outer_dia_m**2) / 4) * WATER_DENSITY
    soil_weight = (SOIL_DENSITY - WATER_DENSITY) * soil_depth * outer_dia_m
    down_force = soil_weight + PIPE_WEIGHT[sdr_index]
    return down_force / weight_water

def utilisation(iterdict, ground_depths, surcharges, perforated):
    results = {}
    
    for dia, sdr_vals in iterdict.items():
        trench_width = dia + 300  # mm
        eff_soil_mod = EMBED_MODULUS * leonhardt(trench_width, dia, SOIL_MODULUS, EMBED_MODULUS)
        
        for i, thickness in enumerate(sdr_vals):
            key = (dia, "SDR11" if i == 0 else "SDR17")
            stiff = stiffness(dia, thickness, perforated)
            pressures = [SOIL_DENSITY * depth/1000 + sur for depth, sur in zip(ground_depths, surcharges)]
            
            # Buckling safety
            buck_safety = buckling(stiff, eff_soil_mod, pressures)
            
            # Ovalisation and flotation
            oval_factors = [
                ovalisation(DEFLECTION_COEFF, p, stiff, eff_soil_mod, i)
                for p in pressures
            ]
            flotation_safety = [flotation(dia, depth, i) for depth in ground_depths]
            
            # Critical buckling (without soil)
            unit_I = thickness**4 / 12
            pbuck_crit = (24 * PIPE_MODULUS * unit_I) / (dia**3) * 1000 # kN/m²
            buck_crit_safety = [(pbuck_crit / p) / 1.5 for p in pressures]
            
            # Max utilisation per pressure scenario
            results[key] = [
            max(oval, 1 / flot if flot != 0 else 999, 1 / crit if crit != 0 else 999) for oval, flot, crit in zip(oval_factors, flotation_safety, buck_crit_safety)
            ]

    
    return results

# Key property arrays
diameters = [110, 125, 160, 180, 200, 225, 250, 280, 315, 355, 400, 450, 500, 560, 630] 
sdr11 = [10.0, 11.4, 14.6, 16.4, 18.2, 20.5, 22.8, 25.5, 28.7, 32.3, 36.4, 40.9, 45.4, 50.8, 57.2]
sdr17 = [6.3, 7.1, 9.1, 10.2, 11.4, 12.8, 14.2, 15.9, 17.9, 20.1, 22.7, 25.5, 28.3, 31.7, 35.7]

ground_crown = [0.675, 0.775, 0.875, 0.975, 1.075, 1.175, 1.275, 1.375, 1.575, 1.775, 1.975, 2.175, 2.675, 3.175]
surcharge_pressure = [690, 480, 340, 245, 185, 140, 110, 95, 75, 65, 50, 40, 25, 15]  # kN/m²

iterdict = dictionary(diameters, sdr11, sdr17)
final_data = utilisation(iterdict, ground_crown, surcharge_pressure, perforated=False)

import pandas as pd

# Convert final_data to DataFrame
df_data = []
for (dia, sdr), utilisations in final_data.items():
    for depth, util in zip(ground_crown, utilisations):
        df_data.append({
            "Diameter (mm)": dia,
            "SDR Type": sdr,
            "Crown Depth (m)": depth,
            "Utilisation": util
        })

df = pd.DataFrame(df_data)

pivot_df = df.pivot_table(
    index="Crown Depth (m)",
    columns=["Diameter (mm)", "SDR Type"],
    values="Utilisation"
)

col_order = [(d, sdr) for d in diameters for sdr in ["SDR17", "SDR11"]]
pivot_df = pivot_df[col_order]

with pd.ExcelWriter("Pipe_Utilisation_Results.xlsx") as writer:
    pivot_df.to_excel(writer, sheet_name="Utilisation Results")