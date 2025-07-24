import numpy as np
from scipy import constants as const

def density(Media):
    if Media == "Water":
        return 999.972

def Uplift(debug=False):  # Add a debug parameter (default: False)
    while True:
        Shape = input("Is your Slab Rectangular (R) or Circular (C)? ").upper()
        if Shape in ["R", "C"]:
            break 
        else:
            print("Invalid shape. Please enter 'R' for Rectangular or 'C' for Circular.")

    Depth = float(input("What is the Thickness of your Slab: "))

    if Shape == "C":
        Diameter = float(input("What is the Diameter of your Slab: "))
        Vol = (np.pi) * (Diameter ** 2) / 4 * Depth
        if debug:
            print(f"Volume (Circular): π × ({Diameter}^2 / 4) × {Depth} = {Vol:.4f} m³")

    elif Shape == "R": 
        Width = float(input("What is the First Side Length of your Slab: "))
        Length = float(input("What is the Second Side Length of your Slab: "))
        Vol = Depth * Width * Length
        if debug:
            print(f"Volume (Rectangular): {Depth} × {Width} × {Length} = {Vol:.4f} m³")

    else:
        raise ValueError("Invalid shape. Only 'R' or 'C' are accepted.")

    uplift_force = const.g * Vol * density("Water") / 1000  # Calculate first for clarity
    if debug:
        print(f"Uplift Force: g × Volume × Density / 1000 = {const.g:.2f} × {Vol:.4f} × {density('Water'):.3f} / 1000 = {uplift_force:.4f} kN")

    return uplift_force

print("The Uplift Force is:", Uplift(debug=True), "kN")  # Enable debug prints
# print("The Uplift Force is:", Uplift(), "kN")          # Silent mode (default)