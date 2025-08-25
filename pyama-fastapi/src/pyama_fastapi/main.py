from __future__ import annotations

import multiprocessing as mp
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from pyama_core.io.nd2_loader import load_nd2_metadata
from .services.workflow import run_complete_workflow_headless


app = FastAPI(title="PyAMA API", version="0.1.0")


class ProcessRequest(BaseModel):
    nd2_path: str
    output_dir: str
    pc_channel: int
    fl_channel: int | None = None
    fov_start: int | None = None
    fov_end: int | None = None
    batch_size: int = 4
    n_workers: int = 4
    mask_size: int = 3
    binarization_method: str = "log-std"
    background_correction_method: str = "schwarzfischer"
    div_horiz: int = 7
    div_vert: int = 5
    footprint_size: int = 25
    min_trace_length: int = 20
    delete_raw_after_processing: bool = False


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/process")
def process(req: ProcessRequest) -> JSONResponse:
    metadata = load_nd2_metadata(req.nd2_path)
    data_info: dict[str, Any] = {
        "filename": metadata["filename"],
        "metadata": metadata,
        "pc_channel": req.pc_channel,
        "fl_channel": req.fl_channel,
    }

    success, message = run_complete_workflow_headless(
        nd2_path=req.nd2_path,
        data_info=data_info,
        output_dir=Path(req.output_dir),
        params=req.model_dump(),
        fov_start=req.fov_start,
        fov_end=req.fov_end,
        batch_size=req.batch_size,
        n_workers=req.n_workers,
    )

    status = 200 if success else 500
    return JSONResponse(status_code=status, content={"success": success, "message": message})


def main() -> None:
    mp.freeze_support()
    mp.set_start_method("spawn", True)
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)



