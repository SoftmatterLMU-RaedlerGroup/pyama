import pickle
import numpy as np

def get_selected_bboxes(session, filename):
    """Create a dict of bboxes of all cells"""
    bboxes = {}
    with session.lock:
        bboxes[None] = dict(n_frames=session.stack.n_frames,
                            width=session.stack.width,
                            height=session.stack.height,
                           )
        for name, tr in session.traces.items():
            if not tr['select']:
                continue
            bboxes[name] = {}
            x_min = None
            x_max = None
            y_min = None
            y_max = None
            coords = []
            for fr, roi in enumerate(tr['roi']):
                r = session.rois[fr][roi]
                bb = r.bbox
                if x_min is None or bb.x_min < x_min:
                    x_min = bb.x_min
                if x_max is None or bb.x_max > x_max:
                    x_max = bb.x_max
                if y_min is None or bb.y_min < y_min:
                    y_min = bb.y_min
                if y_max is None or bb.y_max > y_max:
                    y_max = bb.y_max
                coords.append(r.coords)
                centroid = r.centroid
                bboxes[name][fr] = dict(
                                        x_min=bb.x_min,
                                        x_max=bb.x_max,
                                        y_min=bb.y_min,
                                        y_max=bb.y_max,
                                        x_mean=centroid[r.X],
                                        y_mean=centroid[r.Y],
                                        area=r.area,
                                        )
            coords = np.concatenate(coords)
            bboxes[name][...] = dict(
                                     x_min=x_min,
                                     x_max=x_max,
                                     y_min=y_min,
                                     y_max=y_max,
                                     x_mean=np.mean(coords[:, r.X]),
                                     y_mean=np.mean(coords[:, r.Y]),
                                     area=np.unique(coords, axis=0).shape[0],
                                     )
    with open(filename, 'wb') as f:
        pickle.dump(bboxes, f)
    print(f"{len(bboxes)-1} bounding boxes written to {filename}")

