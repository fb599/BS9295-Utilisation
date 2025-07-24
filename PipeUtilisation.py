import math
import numpy as np
import time

# Pipe perforation flag
# Set to True if the pipe is perforated, otherwise set to False

perforation = False

# Key property arrays

diameters = [110, 125, 160, 180, 200, 225, 250, 280, 315, 355, 400, 450, 500, 560, 630] 
sdr11 = [10.0, 11.4, 14.6, 16.4, 18.2, 20.5, 22.8, 25.5, 28.7, 32.3, 36.4, 40.9, 45.4, 50.8, 57.2]
sdr17 = [6.3, 7.1, 9.1, 10.2, 11.4, 12.8, 14.2, 15.9, 17.9, 20.1, 22.7, 25.5, 28.3, 31.7, 35.7]

ground_crown = [0.675, 0.775, 0.875, 0.975, 1.075, 1.175, 1.275, 1.375, 1.575, 1.775, 1.975, 2.175, 2.675, 3.175]
sleeper_crown = [0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 1.1, 1.2, 1.4, 1.6, 1.8, 2.0, 2.5, 3.0] 
surcharge_pressure = [690, 480, 340, 245, 185, 140, 110, 95, 75, 65, 50, 40, 25, 15] # kN/m^2

# Function to initialise a dictionary with diameters and their corresponding SDR values
# The dictionary will have diameter as keys and a list of SDR values as values

def dictionary(diameter, sdr11, sdr17):
    dictionary = {d: [s11, s17] for d, s11, s17 in zip(diameter, sdr11, sdr17)}
    return dictionary

"""Function to perform the utilisation calculations"""

def utilisation(iterdict, ground, surcharge, perforation):
    utilvals = []
    
    # Specify native soil and embedment properties
    soil_modulus = 10 # MN/m^2
    soil_density = 19.6  # kN/m^3
    embed_modulus = 10  # MN/m^2

    pipe_modulus = 150 # MN/m^2
    deflection_coeff = 0.083
    # strainf_11 = 4.0
    # strainf_17 = 4.5

    # Iterate over each key (diameter) in the dictionary
    for diameter, sdr_values in iterdict.items():  
        
        # Iterate over each thickness for the current diameter
        # Dictionary indexed as {diameter: [sdr11, sdr17]}
        for thickness in sdr_values:  
            sub_utilvals = []
            total_pressure = []
            ppf_safety = []

            # Calculating geometric properties
            D = diameter - thickness  # mm
            trench_width = diameter + 300 # mm
            unit_I = (1*thickness)**4 / 12 # mm^4/mm
            
            stiffness = stiffness(pipe_modulus, D, unit_I, perforation)
            
            # Calculate the effective soil modulus using Leonhardt's method
            effective_soil_modulus = embed_modulus * Leonhardt(trench_width, diameter, soil_modulus, embed_modulus)

            # Calculate total pressure on the pipe
            for k in range(len(ground)):
                soil_pressure = soil_density * ground[k]/1000
                total_pressure.append(soil_pressure + surcharge[k]) # kN/m^2

            # Calculate the buckling resistance and pressure safety factor
            buckling_resistance = buckling(stiffness, effective_soil_modulus, total_pressure)
            ppf_safety.append(buckling_resistance)

            # Calculate the ovalisation safety factor
            thickness_index = enumerate(sdr_values)
            sub_utilvals.append(ovalisation(deflection_coeff, total_pressure, stiffness, effective_soil_modulus, thickness_index))

            pbuck_crit = (24 * 150 * unit_I) / (D**3)  # Critical buckling pressure in kN/m^2
            sub_utilvals.append((pbuck_crit/soil_pressure)/1.5)

            for k in range(len(ground)):
                if flotation(diameter, ground, thickness_index) > 1.1:
                    pass
                else:
                    sub_utilvals.append(1)
            
            utilvals.append(max(sub_utilvals))
    
    return utilvals


"""Calculate the stiffness of the pipe"""

def stiffness(pipe_modulus, diameter, unit_I, perforation):
    
    stiffness = (pipe_modulus * 10e3 * unit_I) / (diameter**3)
    if perforation == True:  # Accounting for perforation
            stiffness *= 0.95

    return stiffness


"""Calculate the effective soil modulus using Leonhardt's method"""

def Leonhardt(trench_width, diameter, soil_modulus, embed_modulus):

    if 4.3 * diameter < trench_width:
        C_L = 1.0
    else:
        # Equation (29) from BS9295
        C_L = (0.985 + (0.544*trench_width/diameter)) / ((1.985-0.456*(trench_width/diameter)) * (soil_modulus/embed_modulus)-(1-(trench_width/diameter)))

    return C_L  


"""Calculate the buckling resistance and associated pressure safety factor"""

def buckling(stiffness, effective_soil_modulus, total_pressure):

    buckling_resistance = 0.6 * (stiffness * effective_soil_modulus)**(1/3) * effective_soil_modulus**(2/3) # MN/m^2
    ppf_safety = [buckling_resistance / pressure for pressure in total_pressure]  # List comprehension

    return ppf_safety


"""Calculate the ovalisation factor based on deflection coefficient, total pressure, stiffness, effective soil modulus and thickness"""

def ovalisation(deflection_coeff, total_pressure, stiffness, effective_soil_modulus, thickness_index):

    # Pre-factored ovalisation percentages from !Type B! installation 
    initial_oval = {
        0: 0.5 + 0.5,   # SDR11 (first value in list)
        1: 0.5 + 2.15   # SDR17 (second value in list)
    }

    initial_ovalisation = initial_oval[thickness_index]

    time_ovalisation = ((deflection_coeff * total_pressure) / ((8 * stiffness) + 0.061 * effective_soil_modulus))
    total_ovalisation = initial_ovalisation + time_ovalisation
    factor = total_ovalisation / 3.0

    return factor


"""Calculate the flotation safety factor based on the pipe's diameter and soil density"""

def flotation(diameter, ground, thickness_index):

    water_density = 10  # kN/m^3
    weight_water = (math.pi * (diameter**2) / 4) * water_density  # kN/m

    pipe_weight = [
        0.25, 
        0.16
    ]  # Weights for SDR11 and SDR17 in kN/m
    
    for k in range(len(ground)):
        soil_weight = (19.6 - 10) * ground[k] * diameter / 1000  # kN/m    

    down_res = soil_weight + pipe_weight[thickness_index]

    return down_res / weight_water


iterdict = dictionary(diameters, sdr11, sdr17)

final_data = utilisation(iterdict, ground_crown, surcharge_pressure, perforation)