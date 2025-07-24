import streamlit as st
import pandas as pd
import numpy as np
from io import BytesIO

# Check if streamlit exists
$streamlitPath = where.exe streamlit 2>$null

if (-not $streamlitPath) {
    # Try to find it via Python
    $pythonPath = python -c "import sys; print(sys.executable)" 2>$null
    if ($pythonPath) {
        $pythonDir = [System.IO.Path]::GetDirectoryName($pythonPath)
        $streamlitPath = Join-Path $pythonDir "Scripts\streamlit.exe"
        
        if (Test-Path $streamlitPath) {
            & $streamlitPath run your_app.py
        } else {
            Write-Host "Streamlit not found. Installing..."
            python -m pip install streamlit
            & $streamlitPath run your_app.py
        }
    } else {
        Write-Host "Python not found. Please install Python first."
    }
} else {
    & $streamlitPath run your_app.py
}