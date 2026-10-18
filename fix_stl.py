#!/usr/bin/env python3
"""
Fix STL - ripara file STL rotti (buchi, normali invertite, non-manifold).
Uso: python3 fix_stl.py file1.stl [file2.stl ...]
Output: file1_fixed.stl accanto all'originale.

Pensato per essere avvolto in un'app drag&drop (es. con Platypus) su macOS,
per rimpiazzare la funzione "Fix STL" assente in Bambu Studio su Mac.

Mesh molto grandi (> BIG_MESH_FACES facce): salta i passaggi lenti di trimesh
e usa direttamente MeshFix. Consiglio: decimare prima la mesh (500k-1M facce).
"""
import sys
import os
import time
import traceback

BIG_MESH_FACES = 1_000_000


def log(msg):
    print(msg, flush=True)


def timed(label, fn, *args, **kwargs):
    """Esegue fn, stampando la fase e il tempo impiegato."""
    log(f"  [{label}]...")
    t0 = time.time()
    result = fn(*args, **kwargs)
    log(f"  [{label}] fatto in {time.time() - t0:.1f}s")
    return result


def repair_with_trimesh(mesh):
    import trimesh
    timed("rimozione facce duplicate", lambda: mesh.update_faces(mesh.unique_faces()))
    timed("rimozione facce degeneri", lambda: mesh.update_faces(mesh.nondegenerate_faces()))
    mesh.remove_unreferenced_vertices()
    timed("unione vertici", mesh.merge_vertices)
    timed("normali", trimesh.repair.fix_normals, mesh)
    timed("orientamento facce", trimesh.repair.fix_winding, mesh)
    timed("riempimento buchi", mesh.fill_holes)
    return mesh


def repair_with_pymeshfix(mesh):
    """MeshFix lavora direttamente su vertici/facce, senza file temporanei."""
    import pymeshfix
    import trimesh
    mf = pymeshfix.MeshFix(mesh.vertices.copy(), mesh.faces.copy())
    # remove_smallest_components=False: senza questo MeshFix butta via tutti i
    # corpi separati tranne il più grande (es. modelli a più pezzi).
    timed("pymeshfix", mf.repair, remove_smallest_components=False)
    return trimesh.Trimesh(vertices=mf.points, faces=mf.faces, process=True)


def repair_mesh(mesh, label=""):
    """Ripara una singola mesh scegliendo il percorso in base alla dimensione."""
    n = len(mesh.faces)
    log(f"{label}prima: facce={n} watertight={mesh.is_watertight}")

    if mesh.is_watertight and mesh.is_winding_consistent:
        log(f"{label}mesh già a posto, nessuna riparazione necessaria")
        return mesh

    if n > BIG_MESH_FACES:
        log(f"{label}mesh molto grande ({n} facce): uso direttamente pymeshfix, "
            "può richiedere diversi minuti e parecchia RAM...")
        try:
            fixed = repair_with_pymeshfix(mesh)
            if len(fixed.faces) > 0:
                mesh = fixed
        except Exception as e:
            log(f"{label}pymeshfix non riuscito ({e}), lascio la mesh originale")
    else:
        mesh = repair_with_trimesh(mesh)
        if not mesh.is_watertight:
            try:
                log(f"{label}mesh ancora non chiusa, provo repair avanzato (pymeshfix)...")
                mesh2 = repair_with_pymeshfix(mesh)
                mesh2 = repair_with_trimesh(mesh2)
                if len(mesh2.faces) > 0:
                    mesh = mesh2
            except Exception as e:
                log(f"{label}pymeshfix non riuscito ({e}), tengo il risultato trimesh")

    log(f"{label}dopo:  facce={len(mesh.faces)} watertight={mesh.is_watertight}")
    return mesh


def fix_file(path):
    import trimesh
    ext = os.path.splitext(path)[1].lower()
    size_mb = os.path.getsize(path) / 1e6
    log(f"\n== {os.path.basename(path)} ({size_mb:.1f} MB) ==")
    if ext == ".3mf" and size_mb > 30:
        log("  File 3MF grande: il caricamento può richiedere diversi minuti. "
            "Se possibile esporta come STL da Bambu Studio e usa quello.")

    loaded = timed("caricamento", trimesh.load, path, force="mesh" if ext == ".stl" else None)

    if isinstance(loaded, trimesh.Scene):
        # file multi-oggetto (tipico dei .3mf con più parti sulla piastra)
        # i nomi "veri" delle parti stanno nei nodi del grafo, non nelle chiavi di .geometry
        fixed_scene = trimesh.Scene()
        for node_name in loaded.graph.nodes_geometry:
            transform, geom_key = loaded.graph[node_name]
            geom = loaded.geometry[geom_key]
            geom = repair_mesh(geom, label=f"  parte '{node_name}': ")
            fixed_scene.add_geometry(geom, node_name=node_name)
        mesh = fixed_scene
    else:
        mesh = repair_mesh(loaded)

    base, orig_ext = os.path.splitext(path)
    out_path = base + "_fixed" + orig_ext
    timed("salvataggio", mesh.export, out_path)
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
