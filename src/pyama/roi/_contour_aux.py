#! /usr/bin/env python3
import numpy as np
np.seterr(invalid='raise') #DEBUG


class CornerFinder:
    """
Find the coordinates of the coordinates.

The recommended usage is to call the ``go`` method of this class.
    """
    def __init__(self, contour, metric="manhattan"):
        self.contour = contour
        self.nNodes = contour.shape[0]
        self.dist = None
        self.chain = None
        self.corner_idcs = None

        if metric == "manhattan" or metric == "euclidean":
            self.metric = metric
        else:
            raise ValueError("Unknown metric: {}".format(metric))

    @classmethod
    def go(cls, contour, metric="manhattan", indices=False, simplify=True):
        """
Return the coordinates of the contours.

@param contour The coordinates of the contour
<!-- :type contour: --> (2,N)-shaped numpy array with x-values in column 1 and y-values in column 0
@param metric The distance metric to be used for neighbor search; may be "manhattan" (default) or "euclidean"
<!-- :type metric: --> str
@param indices Flag wheter to return the coordinates themself or an index array for indexing the rows in ``contour``.
<!-- :type indices: --> bool
@param simplify Flag whether to omit unnecessary (non-corner) coordinates from the output (default: True)
<!-- :type simplify: --> bool

@return  corner coordinates or index array, depending on setting of ``indices``
        """
        cf = cls(contour, metric)
        cf.make_dist()
        cf.build_chain()
        cf.sort_corners(simplify=simplify)

        if indices:
            return cf.corner_idcs
        return cf.contour[cf.corner_idcs, :]


    def make_dist(self):
        """Calculate the distance matrix.

The distance matrix ``self.dist`` is symmetric.
Diagonal elements are 0.
        """
        self.dist = np.empty([self.nNodes, self.nNodes], dtype=np.float)
        for i in range(self.nNodes-1):
            d = self.contour[i+1:, :] - self.contour[i, :]
            if self.metric == "manhattan":
                d = np.abs(d).sum(axis=1)
            elif self.metric == "euclidean":
                d = np.sqrt((d**2).sum(axis=1))
            else:
                raise ValueError("Unknown metric: {}".format(self.metric))

            self.dist[i, i+1:] = d
            self.dist[i+1:, i] = d
            self.dist[i, i] = 0.


    def find_nearest_node(self, i, mode="free", allow=None):
        """
Return the index of the node with smallest distance to node ``i``.

There are three search modes:
* "free" (default mode): find only nodes that have no neighbors yet
* "half-free": find only nodes that have zero or one neighbor
* "half": find only nodes that have one neighbor
* "half-used" find only nodes that have one or two neighbors
* "used": find only nodes that have two neighbors already
* None: find nearest node, regardless of number of neighbors
If no neighbor is found for the search mode, ``None`` is returned.

@param i The node whose neighbors are sought
<!-- :type i: --> int
@param mode The search mode
@param allow Iterable of indices to be allowed
@return  The index of the nearest neighbor node of ``i``, or ``None`` if there is no neighbor for this search mode
        """
        # Process mode
        if mode is None:
            idx = np.ones_like(self.dist[i], dtype=np.bool)
        elif mode == "free":
            idx = (self.chain['prev'] < 0) & (self.chain['next'] < 0)
        elif mode == "half-free":
            idx = (self.chain['prev'] < 0) | (self.chain['next'] < 0)
        elif mode == "half":
            idx = (self.chain['prev'] >= 0) ^ (self.chain['next'] >= 0)
        elif mode == "half-used":
            idx = (self.chain['prev'] >= 0) | (self.chain['next'] >= 0)
        elif mode == "used":
            idx = (self.chain['prev'] >= 0) & (self.chain['next'] >= 0)
        else:
            raise ValueError("Unknown mode: {}".format(mode))

        # Exclude invalid edges
        idx[i] = False
        idx[~np.isfinite(self.dist[i])] = False
        idx[idx] &= self.dist[i,idx] > 0.
        if allow is not None:
            idx[allow] = True

        if idx.sum() == 0:
            return None

        # Find index of node with smallest distance to node `i`
        return np.flatnonzero(idx)[np.argmin(self.dist[i, idx])]


    def build_chain(self, i0=0):
        """
Construct the chain of coordinates in correct order.

@param i0 The index of the coordinate at which to start
<!-- :type i0: --> int
        """
        self.chain = np.full(self.nNodes, -1, dtype=[('prev', np.intp), ('next', np.intp)])

        # Walk through nodes by taking the nearest node, starting at node 0
        # `i` is the current node, `j` is the nearest node
        # If we obtain a `j == 0`, the cycle is closed.
        # TODO: check if it is possible that `j == 0` is not obtained
        i = i0
        j = -1
        searchmode = "free"
        while j != i0:
            # Find nearest node
            j = self.find_nearest_node(i, mode=searchmode)

            # Check if all nodes are consumed
            if j is None:
                break

            # Set reference to nearest node
            self.chain[j]['prev'] = i
            self.chain[i]['next'] = j

            # Check when to unblock start node `i0`
            if searchmode == "free":
                if self.find_nearest_node(j, mode="half-free") != i0:
                    searchmode = "half-free"

            # Proceed to nearest node
            i = j

        # Integrate nodes not visited yet into path
        for i, neighbors in enumerate(self.chain):
            neighbors = neighbors[np.newaxis].view(np.intp)
            if (neighbors >= 0).all():
                continue
            elif (neighbors >= 0).any():
                raise ValueError("Half-connected node: {:d}".format(i))
            elif (self.dist[i] == 0).sum() > 1:
                continue
            self.integrate_into_chain(i)


    def integrate_into_chain(self, i):
        """
Integrate node with index `i` into the chain.

This method integrates coordinates into the chain that are not
integrated yet.

Requires an existing chain in ``self.chain``.
        """
        j = self.find_nearest_node(i, mode="used")
        j_prev = self.chain[j]['prev']
        j_next = self.chain[j]['next']

        if self.dist[i, j_prev] < self.dist[i, j_next]:
            self.chain[i] = (j_prev, j)
            self.chain[j_prev]['next'] = i
            self.chain[j]['prev'] = i
        else:
            self.chain[i] = (j, j_next)
            self.chain[j]['next'] = i
            self.chain[j_next]['prev'] = i


    def sort_corners(self, j0=0, simplify=True):
        """
Return the sorted indices of the coordinates.

@param j0 The index of the coordinate to start at
<!-- :type j0: --> int
@param simplify Flag wheter to omit redundant coordinates (default: True)
<!-- :type simplify: --> bool

@return  A sorted array of indices
<!-- :rtype: --> (M,)-shaped numpy array of dtype ``intp``
        """
        while (self.chain[j0, None].view(dtype=np.intp) < 0).any():
            j0 += 1
        idcs = []
        i = self.chain[j0]['prev']
        j = j0
        prev_diff = self.contour[j] - self.contour[i]

        while True:
            this_diff = self.contour[self.chain[j]['next']] - self.contour[j]
            if not simplify or (this_diff != prev_diff).any():
                idcs.append(j)

            i = j
            j = self.chain[i]['next']
            if j == j0:
                break
            prev_diff = this_diff

        self.corner_idcs = np.array(idcs, dtype=np.intp)


if __name__ == "__main__":
    import tkinter as tk

    # Set up test coordinates
    coords = np.array([[2,2], [2,3], [2,4], [2,5], [2,6], [2,7], [3,7], [4,7],
                       [5,7], [6,7], [7,7], [7,6], [8,6], [8,5], [8,4], [7,4],
                       [7,3], [7,2], [6,2], [5,2], [4,2], [3,2]])

    # Find the corners
    corners = CornerFinder.go(coords)

    # Print info
    print("Coordinates:")
    print(coords)
    print("Corners:")
    print(corners)

    # Show the test coordinates (red points) and the contour (black)
    root = tk.Tk()
    canvas = tk.Canvas(root, highlightthickness=0, background="white")
    canvas.pack()

    canvas.create_polygon(*corners.flat, fill="", outline="black", tags="p")
    for c in coords:
        canvas.create_oval(c[0], c[1], c[0], c[1],
                           width=.5, fill="red", outline="red", tags="p")
    canvas.scale("p", 0, 0, 8, 8)

    root.mainloop()
