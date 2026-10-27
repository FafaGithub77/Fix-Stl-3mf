#!/usr/bin/env python3
"""
Fix STL - repairs broken STL files (holes, inverted normals, non-manifold).
Usage: python3 fix_stl.py file1.stl [file2.stl ...]
Output: file1_fixed.stl next to the original.

Designed to be wrapped in a drag & drop app (e.g., with Platypus) on macOS, to replace the "Fix STL" feature missing in Bambu Studio on Mac.

Very large meshes (> BIG_MESH_FACES faces): skips slow trimesh steps and uses MeshFix directly. Tip: decimate the mesh first (500k–1M faces).

"""
import sys
import os
import time
import traceback

BIG_MESH_FACES = 1_000_000


def log(msg):
    print(msg, flush=True)


def timed(label, fn, *args, **kwargs):
    """Runs fn, printing the phase name and the time it took."""
    log(f"  [{label}]...")
    t0 = time.time()
    result = fn(*args, **kwargs)
    log(f"  [{label}] done in {time.time() - t0:.1f}s")
    return result


def repair_with_trimesh(mesh):
    import trimesh
    timed("removing duplicate faces", lambda: mesh.update_faces(mesh.unique_faces()))
    timed("removing degenerate faces", lambda: mesh.update_faces(mesh.nondegenerate_faces()))
    mesh.remove_unreferenced_vertices()
    timed("merging vertices", mesh.merge_vertices)
    timed("normals", trimesh.repair.fix_normals, mesh)
    timed("face orientation", trimesh.repair.fix_winding, mesh)
    timed("filling holes", mesh.fill_holes)
    return mesh


def repair_with_pymeshfix(mesh):
    """MeshFix works directly on vertices/faces, no temporary files."""
    import pymeshfix
    import trimesh
    mf = pymeshfix.MeshFix(mesh.vertices.copy(), mesh.faces.copy())
    # remove_smallest_components=False: without this, MeshFix discards all
    # separate bodies except the largest one (e.g. multi-part models).
    timed("pymeshfix", mf.repair, remove_smallest_components=False)
    return trimesh.Trimesh(vertices=mf.points, faces=mf.faces, process=True)


def repair_mesh(mesh, label=""):
    """Repairs a single mesh, choosing the approach based on its size."""
    n = len(mesh.faces)
    log(f"{label}before: faces={n} watertight={mesh.is_watertight}")

    if mesh.is_watertight and mesh.is_winding_consistent:
        log(f"{label}mesh is already fine, no repair needed")
        return mesh

    if n > BIG_MESH_FACES:
        log(f"{label}very large mesh ({n} faces): using pymeshfix directly, "
            "this may take several minutes and a lot of RAM...")
        try:
            fixed = repair_with_pymeshfix(mesh)
            if len(fixed.faces) > 0:
                mesh = fixed
        except Exception as e:
            log(f"{label}pymeshfix failed ({e}), keeping the original mesh")
    else:
        mesh = repair_with_trimesh(mesh)
        if not mesh.is_watertight:
            try:
                log(f"{label}mesh still not closed, trying advanced repair (pymeshfix)...")
                mesh2 = repair_with_pymeshfix(mesh)
                mesh2 = repair_with_trimesh(mesh2)
                if len(mesh2.faces) > 0:
                    mesh = mesh2
            except Exception as e:
                log(f"{label}pymeshfix failed ({e}), keeping the trimesh result")

    log(f"{label}after:  faces={len(mesh.faces)} watertight={mesh.is_watertight}")
    return mesh


def fix_file(path):
    import trimesh
    ext = os.path.splitext(path)[1].lower()
    size_mb = os.path.getsize(path) / 1e6
    log(f"\n== {os.path.basename(path)} ({size_mb:.1f} MB) ==")
    if ext == ".3mf" and size_mb > 30:
        log("  Large 3MF file: loading may take several minutes. "
            "If possible, export as STL from Bambu Studio and use that instead.")

    loaded = timed("loading", trimesh.load, path, force="mesh" if ext == ".stl" else None)

    if isinstance(loaded, trimesh.Scene):
        # multi-object file (typical of .3mf with several parts on the plate)
        # the "real" part names are in the graph nodes, not in the .geometry keys
        fixed_scene = trimesh.Scene()
        for node_name in loaded.graph.nodes_geometry:
            transform, geom_key = loaded.graph[node_name]
            geom = loaded.geometry[geom_key]
            geom = repair_mesh(geom, label=f"  part '{node_name}': ")
            fixed_scene.add_geometry(geom, node_name=node_name)
        mesh = fixed_scene
    else:
        mesh = repair_mesh(loaded)

    base, orig_ext = os.path.splitext(path)
    out_path = base + "_fixed" + orig_ext
    timed("saving", mesh.export, out_path)
    log(f"saved: {out_path}")
    return out_path


def main():
    args = sys.argv[1:]
    if not args:
        log("Drag one or more .stl / .3mf files onto this app, or:")
        log("  python3 fix_stl.py file1.stl [file2.3mf ...]")
        sys.exit(1)

    ok, errors = 0, []
    for path in args:
        if not path.lower().endswith((".stl", ".3mf")):
            log(f"skipping (not .stl/.3mf): {path}")
            continue
        try:
            fix_file(path)
            ok += 1
        except Exception as e:
            errors.append((path, str(e)))
            log(f"ERROR on {path}: {e}")
            traceback.print_exc()

    log(f"\nDone: {ok} files repaired, {len(errors)} errors.")
    if errors:
        sys.exit(1)


if __name__ == "__main__":
    main()
