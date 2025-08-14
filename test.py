# %% imports
import numpy as np
from pathlib import Path

# %% load data
npy_path = Path(r"D:\fov_0001\250115_HuH7 - Kopie_fov0001_fluorescence_corrected.npy")
img = np.load(npy_path)
print(img[0][:5,:5])
