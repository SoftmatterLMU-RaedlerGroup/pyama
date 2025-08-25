import numpy as np
import pandas as pd


def get_trace(df: pd.DataFrame, cell_id: int) -> tuple[np.ndarray, np.ndarray]:
    time_data = df.index.values.astype(np.float64)
    trace_data = df.iloc[:, cell_id].values.astype(np.float64)
    return time_data, trace_data