import numpy as np
from scipy import constants as const

def density(Media):
    if Media == "Water":
        return 999.972

def Uplift():
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

    elif Shape == "R": 
        Width = float(input("What is the First Side Length of your Slab: "))
        Length = float(input("What is the Second Side Length of your Slab: "))
        Vol = Depth * Width * Length

    else:
        raise ValueError("Invalid shape. Only 'R' or 'C' are accepted.")

    return const.g * Vol * density("Water") / 1000 

# print("The Uplift Force is: ", Uplift(), "kN")

