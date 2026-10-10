# Fix STL — drag & drop mesh repair for macOS


A lightweight macOS utility to fix broken .stl and .3mf files before slicing.

On macOS, Bambu Studio lacks native mesh repair because the feature relies on Windows-only APIs (Netfabb). This app fills that gap: drop one or more files onto it to get clean, watertight copies ready for slicing.

## Download and use (prebuilt app)

1. Download `Fix Stl.app` (zipped) from the [Releases](../../releases) page and move it to `/Applications`.
2. Install the Python dependencies once (see [Requirements](#requirements)).
3. Drag one or more `.stl` / `.3mf` files onto the app icon.
4. For each `model.stl` you get `model_fixed.stl` in the same folder, ready to import into Bambu Studio.

**First launch:** the app is not signed, so macOS may refuse to open it. Right-click it → **Open** → **Open**, or run:

```bash
xattr -dr com.apple.quarantine "/Applications/Fix Stl.app"
```

## Requirements

- macOS with Python 3 (the one that ships with the Xcode Command Line Tools, python.org, or Homebrew all work)
- Python packages:

```bash
python3 -m pip install trimesh pymeshfix pyvista numpy-stl scipy
```

The app uses the first `python3` it finds (PATH, then `/opt/homebrew/bin`, `/usr/local/bin`, `/usr/bin`). If the app window shows `ModuleNotFoundError`, install the packages with the exact interpreter path printed in that error message, e.g.:

```bash
/path/shown/in/the/error/python3 -m pip install trimesh pymeshfix pyvista numpy-stl scipy
```

## Terminal usage (no app needed)

```bash
python3 fix_stl.py broken_model.stl another_model.3mf
```

Works on any OS where the dependencies install, not only macOS.

## How the repair works

1. Removes duplicate and degenerate faces, merges coincident vertices
2. Fixes normal orientation and face winding
3. Fills holes (`fill_holes`)
4. If the mesh is still not watertight (complex holes, self-intersections), a second pass runs the **MeshFix** algorithm, which is more aggressive

For `.3mf` files with several objects on the plate, each part is repaired separately and part names are preserved.

Tested on meshes with single and multiple holes: in both cases the result is watertight.

## ⚠️ Limitations with .3mf

The script reads and writes **geometry only** (meshes and part names). If your `.3mf` is a **Bambu Studio project** with multi-color painting, hand-drawn supports, per-part filament assignments or print settings, that data is **lost** in the repaired file — only the corrected 3D shape remains.

This is fine for downloaded models (Thingiverse, Printables, etc.) or when you only need the repaired geometry. If you need to keep project settings, export the repaired part as STL and re-import it into your original Bambu Studio project manually.

## Build the app yourself (Platypus)

[Platypus](https://sveinbjorn.org/platypus) is a free tool that wraps a script into a macOS `.app`.

1. Open Platypus and set:
   - **Script Type**: `sh` (`/bin/sh`)
   - **Script Path**: `fix_stl.sh` (the wrapper, not the `.py` file)
   - **Interface**: `Droplet`
   - Enable **Accept dropped items**, click **Settings** and add the suffixes `stl` and `3mf` (under **Suffixes**)
   - Optionally enable **Remain running after execution** to keep the log window open
2. Under **Bundled Files**, add `fix_stl.py` (it must end up next to the wrapper inside the app)
3. Leave **Create symlink to script and bundled files** unchecked, then click **Create App**

## Files

- `fix_stl.py` — the repair script (Python, uses trimesh + pymeshfix)
- `fix_stl.sh` — small wrapper that locates `python3` and runs `fix_stl.py` on the dropped files
