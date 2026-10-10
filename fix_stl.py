#!/usr/bin/env python3
"""
Fix STL - ripara file STL rotti (buchi, normali invertite, non-manifold).
Uso: python3 fix_stl.py file1.stl [file2.stl ...]
Output: file1_fixed.stl accanto all'originale.

Pensato per essere avvolto in un'app drag&drop (es. con Platypus) su macOS,
per rimpiazzare la funzione "Fix STL" assente in Bambu Studio su Mac.
"""
import sys
import os
import traceback

def log(msg):
    print(msg, flush=True)

def repair_with_trimesh(mesh):
    import trimesh
    mesh.update_faces(mesh.unique_faces())
    mesh.update_faces(mesh.nondegenerate_faces())
    mesh.remove_unreferenced_vertices()
    mesh.merge_vertices()
    trimesh.repair.fix_normals(mesh)
    trimesh.repair.fix_winding(mesh)
    mesh.fill_holes()
    return mesh

def repair_with_pymeshfix(path):
    import pymeshfix
    from pymeshfix import _meshfix
    import trimesh
    mf = pymeshfix.MeshFix(path)
    mf.repair()
    v, f = mf.points, mf.faces
    return trimesh.Trimesh(vertices=v, faces=f, process=True)

def fix_file(path):
    import trimesh
    ext = os.path.splitext(path)[1].lower()
    log(f"\n== {os.path.basename(path)} ==")
    loaded = trimesh.load(path, force='mesh' if ext == '.stl' else None)

    if isinstance(loaded, trimesh.Scene):
        # file multi-oggetto (tipico dei .3mf con più parti sulla piastra)
        # i nomi "veri" delle parti stanno nei nodi del grafo, non nelle chiavi di .geometry
        fixed_scene = trimesh.Scene()
        for node_name in loaded.graph.nodes_geometry:
            transform, geom_key = loaded.graph[node_name]
            geom = loaded.geometry[geom_key]
            log(f"  parte '{node_name}': facce={len(geom.faces)} watertight={geom.is_watertight}")
            geom = repair_with_trimesh(geom)
            if not geom.is_watertight:
                try:
                    tmp = os.path.join(os.path.dirname(path) or ".", f"__tmp_{node_name}.stl")
                    geom.export(tmp)
                    geom2 = repair_with_pymeshfix(tmp)
                    geom2 = repair_with_trimesh(geom2)
                    os.remove(tmp)
                    if len(geom2.faces) > 0:
                        geom = geom2
                except Exception as e:
                    log(f"  pymeshfix non riuscito su '{node_name}' ({e}), tengo il risultato trimesh")
            log(f"  -> facce={len(geom.faces)} watertight={geom.is_watertight}")
            fixed_scene.add_geometry(geom, node_name=node_name)
        mesh = fixed_scene
    else:
        mesh = loaded
        log(f"prima: facce={len(mesh.faces)} watertight={mesh.is_watertight}")
        mesh = repair_with_trimesh(mesh)
        if not mesh.is_watertight:
            try:
                log("mesh ancora non chiusa, provo repair avanzato (pymeshfix)...")
                mesh2 = repair_with_pymeshfix(path)
                mesh2 = repair_with_trimesh(mesh2)
                if mesh2.is_watertight or len(mesh2.faces) > 0:
                    mesh = mesh2
            except Exception as e:
                log(f"pymeshfix non riuscito ({e}), tengo il risultato trimesh")
        log(f"dopo:  facce={len(mesh.faces)} watertight={mesh.is_watertight}")

    base, orig_ext = os.path.splitext(path)
    out_path = base + "_fixed" + orig_ext
    mesh.export(out_path)
    log(f"salvato: {out_path}")
    return out_path

def main():
    args = sys.argv[1:]
    if not args:
        log("Trascina uno o più file .stl / .3mf su questa app, oppure:")
        log("  python3 fix_stl.py file1.stl [file2.3mf ...]")
        sys.exit(1)

    ok, errors = 0, []
    for path in args:
        if not path.lower().endswith((".stl", ".3mf")):
            log(f"salto (non è .stl/.3mf): {path}")
            continue
        try:
            fix_file(path)
            ok += 1
        except Exception as e:
            errors.append((path, str(e)))
            log(f"ERRORE su {path}: {e}")
            traceback.print_exc()

    log(f"\nCompletato: {ok} file riparati, {len(errors)} errori.")
    if errors:
        sys.exit(1)

if __name__ == "__main__":
    main()
