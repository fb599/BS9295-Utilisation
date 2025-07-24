import numpy as np
import matplotlib.pyplot as plt

# =========================
# SECTION 1: Constants and Material Properties (Eurocode 2)
# =========================

# Concrete properties
fck = 30.0  # Concrete characteristic compressive strength (MPa)
gamma_c = 1.5 # Partial safety factor for concrete
fcd = fck / gamma_c # Design compressive strength of concrete (MPa)

# Eurocode 2 concrete stress-strain parameters (for parabolic-rectangular diagram)
# For fck <= 50 MPa
eta = 1.0 # factor for effective strength (alpha_cc in some codes, here 0.85 for 0.85*fcd)
epsilon_c2 = 0.002 # Strain at peak stress
epsilon_cu3 = 0.0035 # Ultimate concrete strain

# Steel properties
fyk = 500.0 # Steel characteristic yield strength (MPa)
gamma_s = 1.15 # Partial safety factor for steel
fyd = fyk / gamma_s # Design yield strength of steel (MPa)
Es = 200000.0 # Modulus of elasticity of steel (MPa)
epsilon_yd = fyd / Es # Yield strain of steel

# =========================
# SECTION 2: Reinforcement Bar Class
# =========================

class ReinforcementBar:
    """
    Represents a single reinforcing bar in the concrete section.
    y_coord: Distance from the top fiber of the concrete section to the bar's centroid (mm).
    area: Cross-sectional area of the bar (mm^2).
    """
    def __init__(self, y_coord, area):
        self.y_coord = y_coord
        self.area = area

# =========================
# SECTION 3: Stress-Strain Models (Eurocode 2)
# =========================

def concrete_stress(epsilon_c, fcd):
    """
    Calculates the design compressive stress in concrete based on strain.
    Uses the parabolic-rectangular stress-strain diagram from Eurocode 2.
    epsilon_c: Concrete strain (negative for compression).
    fcd: Design compressive strength of concrete (MPa).
    """
    if epsilon_c >= 0: # Tension or zero strain
        return 0.0
    elif epsilon_c > -epsilon_c2: # Parabolic part
        return eta * fcd * (1 - (1 - epsilon_c / (-epsilon_c2))**2)
    elif epsilon_c >= -epsilon_cu3: # Rectangular part
        return eta * fcd
    else: # Beyond ultimate strain
        return 0.0 # Or some residual strength if specified, but typically 0 for ULS

def steel_stress(epsilon_s, fyd, Es):
    """
    Calculates the design stress in steel based on strain.
    Uses the bilinear stress-strain diagram from Eurocode 2.
    epsilon_s: Steel strain.
    fyd: Design yield strength of steel (MPa).
    Es: Modulus of elasticity of steel (MPa).
    """
    if abs(epsilon_s) <= epsilon_yd: # Elastic region
        return epsilon_s * Es
    elif abs(epsilon_s) <= 0.01: # Plastic region (assuming 0.01 as ultimate steel strain for simplicity)
        return np.sign(epsilon_s) * fyd
    else: # Beyond ultimate steel strain
        return 0.0 # Failure of steel

# =========================
# SECTION 4: Calculate Section Capacity for a Given Neutral Axis Depth
# =========================

def calculate_nm_point(x_na, reinforcement_bars, b, h, fcd, fyd, Es, epsilon_cu3):
    """
    Calculates the axial force (N) and bending moment (M) for a given neutral axis depth (x_na).
    x_na: Depth of the neutral axis from the top fiber (mm).
    reinforcement_bars: List of ReinforcementBar objects.
    b: Section width (mm).
    h: Section height (mm).
    fcd: Design compressive strength of concrete (MPa).
    fyd: Design yield strength of steel (MPa).
    Es: Modulus of elasticity of steel (MPa).
    epsilon_cu3: Ultimate concrete strain.

    Returns:
    N: Axial force (kN, positive for compression).
    M: Bending moment (kNm, positive for moment causing compression at top).
    """
    N_total = 0.0
    M_total = 0.0
    
    # Section centroid for moment calculation (from top fiber)
    centroid_y = h / 2.0

    # 1. Concrete Contribution
    # Determine the depth of the concrete stress block (alpha_cc * x_na, where alpha_cc is a factor)
    # For fck <= 50 MPa, Eurocode 2 allows a rectangular stress block of depth 0.8 * x_na
    # and uniform stress of 0.85 * fcd.
    
    # Simplified rectangular stress block parameters for EC2 (for fck <= 50 MPa)
    lambda_factor = 0.8 # Factor for depth of stress block
    alpha_cc = 0.85 # Factor for effective concrete strength

    if x_na <= 0: # No concrete in compression
        Nc = 0.0
        Mc = 0.0
    else:
        # Depth of the rectangular stress block
        y_c = min(lambda_factor * x_na, h) # Stress block cannot exceed section height
        
        # Force in concrete
        Nc = alpha_cc * fcd * b * y_c # Force in compression (positive for compression)
        
        # Lever arm for concrete force (distance from centroid of stress block to section centroid)
        lever_arm_c = centroid_y - (y_c / 2.0)
        
        # Moment from concrete
        Mc = Nc * lever_arm_c
    
    N_total += Nc
    M_total += Mc

    # 2. Steel Contribution
    for bar in reinforcement_bars:
        # Calculate strain in steel bar
        # Strain varies linearly from top fiber (epsilon_cu3 at top)
        # epsilon_s = epsilon_cu3 * (x_na - bar.y_coord) / x_na
        # This formula is correct if epsilon_cu3 is positive and x_na is positive.
        # Let's adjust for consistent sign convention (compression negative strain)
        
        # Strain at top fiber is -epsilon_cu3 (compression)
        # Strain at depth y: epsilon(y) = -epsilon_cu3 * (1 - y/x_na)
        
        # If neutral axis is at x_na, and top fiber is at y=0, then strain at y is:
        # epsilon_s = (-epsilon_cu3 / x_na) * (x_na - bar.y_coord)
        # This is for compression as negative.
        
        # More robust strain calculation:
        # Strain at top fiber is -epsilon_cu3. Strain at neutral axis is 0.
        # Linear interpolation:
        if x_na == 0: # Pure tension case or very small compression
            epsilon_s = 0.01 # Assume yielding in tension for all bars if x_na is 0 (pure tension)
            # This needs careful handling for pure tension/compression points,
            # often calculated separately. For now, let's assume x_na > 0.
        else:
            epsilon_s = -epsilon_cu3 * (bar.y_coord - x_na) / x_na
            
        # Calculate stress in steel
        fs = steel_stress(epsilon_s, fyd, Es)
        
        # Force in steel bar (positive for compression, negative for tension)
        Fs = fs * bar.area
        
        # Lever arm for steel force (distance from bar to section centroid)
        lever_arm_s = centroid_y - bar.y_coord
        
        # Moment from steel bar
        Ms = Fs * lever_arm_s
        
        N_total += Fs
        M_total += Ms

    # Convert to kN and kNm
    return N_total / 1000.0, M_total / 1000000.0

# =========================
# SECTION 5: Generate N-M Interaction Diagram
# =========================

def generate_nm_interaction_diagram(b, h, cover, bar_diameter, num_bars_top, num_bars_bottom, num_bars_side=0):
    """
    Generates the N-M interaction diagram points for a rectangular section.

    b: Section width (mm).
    h: Section height (mm).
    cover: Concrete cover (mm).
    bar_diameter: Diameter of reinforcing bars (mm).
    num_bars_top: Number of bars in the top layer.
    num_bars_bottom: Number of bars in the bottom layer.
    num_bars_side: Number of bars on each side (excluding corners, if applicable).
                   For uniaxial bending, these are typically ignored or added to top/bottom.
                   For simplicity, we'll assume they are placed at h/2 for this uniaxial diagram.
    """
    
    # Calculate area of a single bar
    bar_area = np.pi * (bar_diameter / 2)**2

    reinforcement_bars = []

    # Place top bars
    y_top = cover + bar_diameter / 2
    for _ in range(num_bars_top):
        reinforcement_bars.append(ReinforcementBar(y_top, bar_area))

    # Place bottom bars
    y_bottom = h - cover - bar_diameter / 2
    for _ in range(num_bars_bottom):
        reinforcement_bars.append(ReinforcementBar(y_bottom, bar_area))

    # Place side bars (simplified for uniaxial bending, treat as if at mid-height)
    # For a proper biaxial diagram, these would have x and y coordinates.
    # For a uniaxial N-Mx diagram, bars at mid-height contribute to N but not M.
    y_side = h / 2.0
    for _ in range(num_bars_side):
        reinforcement_bars.append(ReinforcementBar(y_side, bar_area))

    # Points for the N-M diagram
    N_points = []
    M_points = []

    # Define range of neutral axis depths
    # Iterate x_na from very small (tension failure) to very large (pure compression)
    # A good range covers all failure modes.
    # From 0 (pure tension) to a value beyond h (pure compression)
    x_na_values = np.linspace(0.01, 2.0 * h, 100) # From small positive to large
    
    # Add a point for pure tension (N_total = -As_total * fyd, M_total = 0)
    # This is a special case where concrete is ignored.
    N_tension = 0.0
    for bar in reinforcement_bars:
        N_tension += -fyd * bar.area # All steel in tension
    N_points.append(N_tension / 1000.0)
    M_points.append(0.0) # Pure tension, no moment

    for x_na in x_na_values:
        N, M = calculate_nm_point(x_na, reinforcement_bars, b, h, fcd, fyd, Es, epsilon_cu3)
        N_points.append(N)
        M_points.append(M)

    # Add a point for pure compression (all concrete, all steel in compression)
    # This is when x_na tends to infinity, or epsilon_c at bottom is -epsilon_c2
    # A simplified way is to calculate N for uniform compression:
    N_pure_comp_concrete = eta * fcd * b * h
    N_pure_comp_steel = 0.0
    for bar in reinforcement_bars:
        N_pure_comp_steel += fyd * bar.area # Assume all steel yields in compression
    N_points.append((N_pure_comp_concrete + N_pure_comp_steel) / 1000.0)
    M_points.append(0.0) # Pure compression, no moment

    # Sort points by N (axial force) for proper plotting
    sorted_indices = np.argsort(N_points)
    N_sorted = np.array(N_points)[sorted_indices]
    M_sorted = np.array(M_points)[sorted_indices]

    return N_sorted, M_sorted

# =========================
# SECTION 6: User Inputs for Section and Reinforcement
# =========================

# Section dimensions
b_section = 300.0 # mm
h_section = 600.0 # mm

# Reinforcement details
cover_val = 30.0 # mm
bar_diameter_val = 20.0 # mm (e.g., 20mm diameter bar)
num_bars_top_val = 3 # Number of bars in the top layer
num_bars_bottom_val = 3 # Number of bars in the bottom layer (for double reinforcement)
# Set num_bars_bottom_val = 0 for single reinforcement (only top bars in compression zone)
# For a column, usually both top and bottom layers are reinforced.

# Design axial load and moment (for checking)
N_design = 1000.0 # kN
M_design = 100.0 # kNm

# =========================
# SECTION 7: Generate and Plot Diagram
# =========================

# Generate the N-M interaction diagram points
N_diagram, M_diagram = generate_nm_interaction_diagram(
    b_section, h_section, cover_val, bar_diameter_val,
    num_bars_top_val, num_bars_bottom_val
)

# Plotting
plt.figure(figsize=(10, 8))
plt.plot(M_diagram, N_diagram, 'b-', linewidth=2, label='N-M Interaction Diagram')
plt.plot(M_design, N_design, 'ro', markersize=10, label='Design Point (N_Ed, M_Ed)')

plt.title('N-M Interaction Diagram (Eurocode 2)')
plt.xlabel('Bending Moment, M (kNm)')
plt.ylabel('Axial Force, N (kN) [Compression Positive]')
plt.grid(True)
plt.axhline(0, color='black', linewidth=0.5) # X-axis
plt.axvline(0, color='black', linewidth=0.5) # Y-axis
plt.legend()
plt.show()

# =========================
# SECTION 8: Check Design Point Safety
# =========================

# A simple check: if the design point is inside the curve.
# This is a basic visual check. For a rigorous check, you'd need to
# interpolate the curve or use a more advanced method to see if (N_design, M_design)
# falls within the envelope.

# For a uniaxial diagram, you can check if M_design is less than M_Rd for N_design.
# This requires finding M_Rd from the generated curve for the given N_design.
# This is typically done by interpolating the N-M curve.

# Find the M_Rd for the given N_design by interpolating the diagram
# This is a simplified interpolation; a more robust method would use scipy.interpolate
M_rd_at_n_design = np.interp(N_design, N_diagram, M_diagram)

# Check if the design moment is within the capacity
is_safe = abs(M_design) <= abs(M_rd_at_n_design) # Use absolute values for moment
print(f"\nDesign Axial Load (N_Ed): {N_design} kN")
print(f"Design Bending Moment (M_Ed): {M_design} kNm")
print(f"Moment Resistance (M_Rd) at N_Ed: {M_rd_at_n_design:.2f} kNm")
print(f"Is the design point SAFE? {'Yes' if is_safe else 'No'}")

