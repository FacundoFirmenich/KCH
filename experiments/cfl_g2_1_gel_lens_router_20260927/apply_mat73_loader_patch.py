#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: apply_mat73_loader_patch.py RUNNER_PATH")
path = Path(sys.argv[1])
text = path.read_text(encoding="utf-8")
start = text.index("def load_primary")
end = text.index("\ndef nrmse", start)
replacement = r'''def _h5_numeric(f: Any, obj: Any) -> np.ndarray:
    """Dereference one MATLAB v7.3 HDF5 numeric field."""
    if isinstance(obj, h5py.Reference):
        obj = f[obj]
    if isinstance(obj, h5py.Dataset) and obj.dtype == object:
        refs = obj[()].reshape(-1)
        if refs.size != 1:
            raise ValueError(f"expected scalar MATLAB reference, got {refs.size}")
        obj = f[refs[0]]
    if not isinstance(obj, h5py.Dataset):
        raise TypeError(f"expected numeric HDF5 dataset, got {type(obj)!r}")
    return np.asarray(obj[()], dtype=np.float64)


def _h5_angles_from_parameter_group(group: Any) -> np.ndarray:
    if "angles" not in group:
        raise KeyError(f"angles missing from HDF5 parameter group {group.name}")
    return np.asarray(group["angles"][()], dtype=np.float64).reshape(-1)


def load_primary(path: Path, key: str) -> tuple[np.ndarray, np.ndarray, dict[str, Any]]:
    """Return frames x angles x detectors and angles in degrees."""
    try:
        mat = _classic_mat(path)
        obj = mat[key]
        sino = np.asarray(_field(obj, "sinogram"), dtype=np.float64)
        params = _field(obj, "parameters")
        angles = np.asarray(_field(params, "angles"), dtype=np.float64).reshape(-1)
        meta = {"loader": "scipy.io.loadmat", "top_keys": sorted(k for k in mat if not k.startswith("__"))}
    except NotImplementedError:
        if h5py is None:
            raise
        with h5py.File(path, "r") as f:
            if key not in f or not isinstance(f[key], h5py.Group):
                raise KeyError(f"HDF5 MATLAB top-level struct {key!r} missing")
            group = f[key]
            if "sinogram" not in group or "parameters" not in group:
                raise KeyError(f"required HDF5 fields missing under {key!r}: {list(group.keys())}")
            sino_refs = group["sinogram"][()].reshape(-1)
            param_refs = group["parameters"][()].reshape(-1)
            if sino_refs.size != PRIMARY_FRAMES or param_refs.size != PRIMARY_FRAMES:
                raise ValueError(
                    f"expected {PRIMARY_FRAMES} HDF5 frame references, "
                    f"got sinogram={sino_refs.size}, parameters={param_refs.size}"
                )
            frame_arrays: list[np.ndarray] = []
            for ref in sino_refs:
                arr = _h5_numeric(f, ref)
                if arr.ndim != 2:
                    raise ValueError(f"expected 2D HDF5 frame, got {arr.shape}")
                frame_arrays.append(arr.T)  # MATLAB HDF5 stores detector x angle here.
            sino = np.stack(frame_arrays, axis=0)
            param0 = f[param_refs[0]]
            if not isinstance(param0, h5py.Group):
                raise TypeError("primary parameter reference is not a group")
            angles = _h5_angles_from_parameter_group(param0)
            meta = {
                "loader": "h5py_matlab_v7_3_references",
                "top_keys": sorted(f.keys()),
                "frame_reference_count": int(sino_refs.size),
            }
    if np.nanmax(np.abs(angles)) <= 2 * np.pi + 1e-6:
        angles = np.rad2deg(angles)
    angles = np.mod(angles, 360.0)
    if sino.ndim != 3:
        raise ValueError(f"expected 3D primary sinogram, got {sino.shape}")
    frame_axes = [i for i, n in enumerate(sino.shape) if n == PRIMARY_FRAMES]
    angle_axes = [i for i, n in enumerate(sino.shape) if n == angles.size]
    if not frame_axes or not angle_axes:
        raise ValueError(f"cannot identify frame/angle axes: shape={sino.shape}, angles={angles.size}")
    fa = frame_axes[0]
    aa = next((i for i in angle_axes if i != fa), angle_axes[0])
    da = next(i for i in range(3) if i not in (fa, aa))
    sino = np.moveaxis(sino, (fa, aa, da), (0, 1, 2))
    order = np.argsort(angles)
    angles = angles[order]
    sino = sino[:, order, :]
    if not np.isfinite(sino).all():
        raise ValueError("non-finite primary sinogram values")
    return sino, angles, meta


def load_extra(path: Path, key: str) -> tuple[np.ndarray, np.ndarray, dict[str, Any]]:
    try:
        mat = _classic_mat(path)
        obj = mat[key]
        sino = np.asarray(_field(obj, "sinogram"), dtype=np.float64)
        params = _field(obj, "parameters")
        angles = np.asarray(_field(params, "angles"), dtype=np.float64).reshape(-1)
        meta = {"loader": "scipy.io.loadmat", "top_keys": sorted(k for k in mat if not k.startswith("__"))}
    except NotImplementedError:
        if h5py is None:
            raise
        with h5py.File(path, "r") as f:
            if key not in f or not isinstance(f[key], h5py.Group):
                raise KeyError(f"HDF5 MATLAB extra-frame struct {key!r} missing")
            group = f[key]
            if "sinogram" not in group or "parameters" not in group:
                raise KeyError(f"required HDF5 fields missing under {key!r}: {list(group.keys())}")
            sino = _h5_numeric(f, group["sinogram"])
            params = group["parameters"]
            if not isinstance(params, h5py.Group):
                raise TypeError("extra-frame parameter field is not a group")
            angles = _h5_angles_from_parameter_group(params)
            meta = {"loader": "h5py_matlab_v7_3_direct", "top_keys": sorted(f.keys())}
    if np.nanmax(np.abs(angles)) <= 2 * np.pi + 1e-6:
        angles = np.rad2deg(angles)
    angles = np.mod(angles, 360.0)
    sino = np.squeeze(sino)
    if sino.ndim != 2:
        raise ValueError(f"expected 2D extra sinogram, got {sino.shape}")
    if sino.shape[0] == angles.size:
        pass
    elif sino.shape[1] == angles.size:
        sino = sino.T
    else:
        raise ValueError(f"cannot identify extra angle axis: {sino.shape}, angles={angles.size}")
    order = np.argsort(angles)
    angles = angles[order]
    sino = sino[order]
    if not np.isfinite(sino).all():
        raise ValueError("non-finite extra sinogram values")
    return sino, angles, meta

'''
text = text[:start] + replacement + text[end:]
path.write_text(text, encoding="utf-8")
