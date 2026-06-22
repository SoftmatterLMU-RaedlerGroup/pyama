"""
This plugin implements functionality to select ROIs in a stack.
"""
import numpy as np
import skimage.draw as skid

SELECTION_OFF = 0
SELECTION_ANCHOR = 1
SELECTION_TILT = 2
SELECTION_RECT = 3
SELECTION_SPACE = 4
SELECTION_ABORT = 5

ROI_TYPE_RECT = 0
ROI_TYPE_SQU = 1 

class RoiReader:
    """Provide ROI selection functionality."""

    def __init__(self, sv):
        """
        Set up RoiReader.

        :param sv: The stack viewer to which this RoiReader belongs
        :type sv: :py:class:`StackViewer`
        """
        self.sv = sv
        self.canvas = self.sv.canvas

        # Configure selection
        self.sel_state = 0
        self.sel_coords = {}
        self.roi_type = ROI_TYPE_RECT


    def start_adjustment(self, *_):
        """Start the ROI adjustment"""
        if not self.sel_state:
            self.control_adjustment(target=SELECTION_ANCHOR)


    def stop_adjustment(self, *_):
        """Abort the ROI adjustment"""
        if self.sel_state:
            self.control_adjustment(target=SELECTION_ABORT)
        self.sv.notify_roi_adjustment_finished()


    def update_adjustment_button(self):
        """
        Update appearance of the ROI definition toggling button
        """
        if self.sel_state == SELECTION_OFF or self.sel_state == SELECTION_ABORT:
            self.sv.adjustment_button.config(text="Adjust ROIs")
        else:
            self.sv.adjustment_button.config(text="Stop ROI adjustment")


    def control_adjustment(self, target):
        """
        Control ROI definition.

        :param target: The requested ROI definition mode; one of:

            * ``SELECTION_OFF``: ROI definition mode is off
            * ``SELECTION_ANCHOR``: Set anchor point (corner of a ROI)
            * ``SELECTION_TILT``: Define ROI tilt
            * ``SELECTION_RECT``: Define ROI shape and size (rectangle)
            * ``SELECTION_SPACE``: Define ROI spacing and span ROI grid
            * ``SELECTION_ABORT``: Abort ROI selection, then switch to
              ``SELECTION_OFF``
        """
        # By default, toggle selection mode
        self.sel_state = target
        self.update_adjustment_button()

        if self.sel_state == SELECTION_ANCHOR:
            self.canvas.delete("roi")
            self.canvas.bind("<Button-1>", self.canvas_clicked)
        elif self.sel_state == SELECTION_TILT:
            self.canvas.bind("<Motion>", self.canvas_moved)
        elif self.sel_state == SELECTION_RECT:
            pass
        elif self.sel_state == SELECTION_SPACE:
            pass
        else:
            self.canvas.delete("roi_draft")
            self.canvas.unbind("<Button-1>")
            self.canvas.unbind("<Motion>")

            if self.sel_state == SELECTION_ABORT:
                self.canvas.delete("rule")
                self.canvas.delete("roi")
                self.sel_state = SELECTION_OFF
            elif 'polygon2' in self.sel_coords:
                self.sv.stack.set_rois(self.compute_roi_array(self.sel_coords['polygon2']), "rect", frame=Ellipsis)

            self.sv.notify_roi_adjustment_finished()
            self.sv.draw_rois()


    def canvas_clicked(self, evt):
        """Canvas "clicked" callback for ROI definition mode"""
        if self.sel_state == SELECTION_ANCHOR:
            self.sel_coords['x0'] = self.canvas.canvasx(evt.x)
            self.sel_coords['y0'] = self.canvas.canvasy(evt.y)
            self.control_adjustment(SELECTION_TILT)

        elif self.sel_state == SELECTION_TILT:
            # Clear rules
            self.canvas.delete("rule")
            self.control_adjustment(SELECTION_RECT)

        elif self.sel_state == SELECTION_RECT:
            # Sort polygon corners (clockwise from 0=top left)
            p = self.sel_coords['polygon']

            psi = p[:,0].argsort()
            if p[psi[0],1] > p[psi[1],1]:
                psi[[0,1]] = psi[[1,0]]
            if p[psi[2],1] < p[psi[3],1]:
                psi[[2,3]] = psi[[3,2]]

            p_new = np.empty_like(p)
            p_new[0,:] = p[psi[1]]
            p_new[1,:] = p[psi[2]]
            p_new[2,:] = p[psi[3]]
            p_new[3,:] = p[psi[0]]

            self.sel_coords['polygon'] = p_new

            self.control_adjustment(SELECTION_SPACE)

        elif self.sel_state == SELECTION_SPACE:
            self.canvas.delete("roi_draft")
            self.canvas.delete("roi")
            polygon2 = self.sel_coords['polygon2']
            if polygon2 is not None:
                for roi in self.compute_roi_array(polygon2):
                    self.canvas.create_polygon(*roi.corners.flat,
                        fill="", outline="yellow", tags="roi")
                
            self.control_adjustment(SELECTION_OFF)

        else:
            self.control_adjustment(SELECTION_OFF)
  

    def canvas_moved(self, evt):
        """Canvas "mouse moved" callback for ROI definition mode"""
        if self.sel_state == SELECTION_TILT: 
            # Clear rules
            self.canvas.delete("rule")

            # Get coordinates
            width, height = self.sv.canvas_bbox()
            x0 = self.sel_coords['x0']
            y0 = self.sel_coords['y0']
            x1 = self.canvas.canvasx(evt.x)
            y1 = self.canvas.canvasy(evt.y)

            # Calculate new rules
            dx = x1 - x0
            dy = y1 - y0

            # Naming: [se][12][xy]
            # start point (s) or end point (e) of rule
            # first rule (1) or second rule (2)
            # x-coordinate (x) or y-coordinate (y)
            if dx == 0:
                # First rule
                s1x = x1
                e1x = x1
                s1y = 0
                e1y = height - 1

                # Second rule
                s2y = y1
                e2y = y1
                s2x = 0
                e2x = width - 1

                # Third rule
                s3y = y0
                e3y = y0
                s3x = 0
                e3x = width - 1

                # Save slope
                self.sel_coords['slope'] = 0

            else:
                # First rule
                s1x = 0
                e1x = width - 1
                s1y = dy / dx * (s1x - x1) + y1
                e1y = dy / dx * (e1x - x1) + y1

                # Second rule
                s2y = 0
                e2y = height - 1
                s2x = - dy / dx * (s2y - y1) + x1
                e2x = - dy / dx * (e2y - y1) + x1

                # Third rule
                s3y = 0
                e3y = height - 1
                s3x = - dy / dx * (s3y - y0) + x0
                e3x = - dy / dx * (e3y - y0) + x0

                # Save (smaller of both) slopes
                if dy == 0:
                    self.sel_coords['slope'] = 0
                elif abs(dy / dx) <= abs(- dx / dy):
                    self.sel_coords['slope'] = dy / dx
                else:
                    self.sel_coords['slope'] = - dx / dy

            # Draw new rules
            self.canvas.create_line(s1x, s1y, e1x, e1y,
                fill="red", tags="rule")
            self.canvas.create_line(s2x, s2y, e2x, e2y,
                fill="red", tags="rule")
            self.canvas.create_line(s3x, s3y, e3x, e3y,
                fill="red", tags="rule")

        elif self.sel_state == SELECTION_RECT:
            # Delete old rectangles
            self.canvas.delete("roi")

            # Get coordinates
            x2 = self.canvas.canvasx(evt.x)
            y2 = self.canvas.canvasy(evt.y)

            x0 = self.sel_coords['x0']
            y0 = self.sel_coords['y0']
            a = self.sel_coords['slope']
            
            # Calculate rectangle
            if a == 0:
                x1 = x2
                y1 = y0

                x3 = x0
                y3 = y2

            else:
                x1 = (y2 - y0 + a * x0 + x2 / a) / (a + 1 / a)
                y1 = a * (x1 - x0) + y0

                x3 = (y0 - y2 + a * x2 + x0 / a) / (a + 1 / a)
                y3 = a * (x3 - x2) + y2

            # Save polygon corners
            polygon = np.array([[x0,y0], [x1,y1], [x2,y2], [x3,y3]])
            self.sel_coords['polygon'] = polygon

            # Draw rectangle
            self.canvas.create_polygon(x0, y0, x1, y1, x2, y2, x3, y3,
                fill="", outline="yellow", width=2.0, tags="roi")

        elif self.sel_state == SELECTION_SPACE:
            # Delete old ROI drafts
            self.canvas.delete("roi_draft")

            # Get coordinates
            ex = self.canvas.canvasx(evt.x)
            ey = self.canvas.canvasy(evt.y)
            width, height = self.sv.canvas_bbox()

            a = self.sel_coords['slope']
            polygon = self.sel_coords['polygon']
            x0 = polygon[0,0]
            y0 = polygon[0,1]

            # Difference between mouse and middle of anchor ROI
            delta = (ex, ey) - np.mean(polygon, axis=0)

            # Get new ROI by shifting and check for overlap with old ROI
            new_poly = polygon + delta
            in_poly = self.is_in_rectangle(new_poly, True)

            # For overlap in one projection, align new ROI 
            new_poly_aligned = new_poly.copy()
            if in_poly == 1:
                y_align = a * (new_poly[0,0] - x0) + y0
                new_poly_aligned[:,1] -= new_poly[0,1] - y_align
            elif in_poly == 2:
                x_align = -a * (new_poly[0,1] - y0) + x0
                new_poly_aligned[:,0] -= new_poly[0,0] - x_align

            # Check if aligned new ROI intersects with old ROI
            aligned_in_poly = self.is_in_rectangle(new_poly_aligned, False)

            # If aligned new ROI does not intersect with old ROI, update
            if in_poly != 0 and not aligned_in_poly:
                new_poly = new_poly_aligned

            # Check if new ROI position is valid
            is_new_pos_valid = True
            if aligned_in_poly or in_poly == 3:
                is_new_pos_valid = False
            elif np.any((new_poly <= 0) | (new_poly >= [width, height])):
                is_new_pos_valid = False

            # Paint new depending on overlap
            if is_new_pos_valid:
                roi_color = "yellow"
            else:
                roi_color = "red"

            self.canvas.create_polygon(*new_poly.flat,
                fill="", outline=roi_color, tags="roi_draft")
            self.canvas.create_line(*new_poly[0], *new_poly[2],
                fill=roi_color, tags="roi_draft")
            self.canvas.create_line(*new_poly[1], *new_poly[3],
                fill=roi_color, tags="roi_draft")

            # For valid ROI positions, show ROI array
            if is_new_pos_valid:
                self.sel_coords['polygon2'] = new_poly
                roi_arr = self.compute_roi_array(new_poly, True)
                for roi in roi_arr:
                    self.canvas.create_polygon(*roi.corners[:,::-1].flat,
                        fill="", outline=roi_color, tags="roi_draft")
            else:
                self.sel_coords['polygon2'] = None


    def compute_roi_array(self, poly2, omit_references=False, poly0=None, a=None):
        """
        Span the array of ROIs.

        :param poly2: The first reference rectangle
        :type poly2: numpy array of shape (4,2)
        :param omit_references: Flag whether to omit the reference rectangles

            from output (``True``) or not (``False``).
            This is useful when the reference rectangles, which are
            known before, are to be highlighted.

        :type omit_references: bool
        :param poly0: The second reference rectangle.
        
            If this is ``None``, the internally saved anchor rectangle
            is loaded.

        :type poly0: None or numpy array of shape (4,2)
        :param a: Slope of the grid. 0 is horizontal.
        
            If ``None``, the internally saved slope is used.
        :type a: None or float

        :return: The ROI array
        :rtype: list of (4,2)-shaped numpy arrays
        """
        # Get coordinates (slope and reference rectangles)
        if a is None:
            a = self.sel_coords['slope']
        if poly0 is None:
            poly0 = self.sel_coords['polygon']
        p0x = poly0[0,0]
        p0y = poly0[0,1]
        p2x = poly2[0,0]
        p2y = poly2[0,1]

        # Tolerance for detecting equal points, in pixels
        eps_x = 5
        eps_y = 5

        # Get auxiliary point
        if a == 0:
            aux_x = p2x
            aux_y = p0y
        else:
            aux_x = (p2y - p0y + a * p0x + p2x / a) / (a + 1 / a)
            aux_y = a * (aux_x - p0x) + p0y

        # Compute ROI grid vectors
        delta_x = np.array([aux_x - p0x, aux_y - p0y])
        delta_y = np.array([aux_x - p2x, aux_y - p2y])

        # Grid construction control variables
        ix = 0
        iy = 0
        new_col = True
        new_row = True
        multi_col = True
        multi_row = True

        # If both reference rectangles in same column: draw only one column
        # (since we do not know spacing between columns)
        if np.sqrt((delta_x**2).sum()) < eps_x:
            new_col = False
            multi_col = False

        # If both reference rectangles in same row: draw only one row
        # (since we do not know spacing between rows)
        if np.sqrt((delta_y**2).sum()) < eps_y:
            new_row = False
            multi_row = False

        # Optionally add second reference ROI
        if not omit_references:
            roi_arr = [RectRoi(poly0)]
        else:
            roi_arr = []

        # Span grid
        # TODO: Search for non-zero rows/columns if zero rows/columns
        #       are not in canvas
        while True:
            if multi_row and iy >= 0:
                # First, visit positive rows
                if new_row:
                    # Visit next row above
                    iy += 1
                else:
                    # If highest row in canvas is reached,
                    # continue visiting the negative rows
                    iy = -1
                    new_row = True
            elif new_row:
                # Climb further down, if possible
                iy -= 1
            else:
                # All possible rows have been visited, visit next column
                # (analog to rows)
                if multi_col and ix >= 0:
                    if new_col:
                        ix += 1
                    elif not new_col:
                        ix = -1
                        new_col = True
                elif new_col:
                    ix -= 1
                else:
                    # No more columns to visit: we are finished
                    break

                # Start at row 0 in this new column
                if multi_row:
                    iy = 0
                    new_row = True

            # Do not recalculate first reference rectangle
            if ix == 1 and iy == -1:
                if not omit_references:
                    roi_arr.append(RectRoi(poly2))
                continue
            
            # Get ROI rectangle at current grid site (ix, iy)
            pn = poly0 + ix * delta_x + iy * delta_y

            # Check if current grid site (ix, iy) fits in canvas
            if self.is_in_canvas(pn):
                # Current grid site fits in canvas, add it to list
                roi_arr.append(RectRoi(pn))
            elif iy == 0:
                # Row 0 does not fit in canvas: no more columns left
                new_col = False
            else:
                # No new rows in this direction:
                # continue with negative rows or visit next column
                new_row = False

        return roi_arr


    def is_in_canvas(self, P):
        """Check if a point or rectangle is in the canvas."""
        if P.ndim == 1:
            P = P.reshape((1,-1))
        width, height = self.sv.canvas_bbox()
        return not np.any((P <= 0) | (P >= [width, height]))


    def is_in_rectangle(self, P, check_projections=False):
        """Check if a point is in the anchor ROI.

        :param P: Point or polygon to be checked
        :type P: Numpy array of shape (2,) or (4,2)
        :param check_projections: Flag indicating whether to check overlap in projection.
        :type check_projections: bool

        If ``P`` is a polygon, its points must be arranged so that
        ``P[0]`` is the top-left point, and the other points are
        arranged clockwise.

        :return: Collision information:

            If ``check_projections == False``, return:
                * ``True`` if point is in the ROI and
                * ``False`` if point is outside of the ROI.

            If ``check_projections == True``, return:

                * 0 if point does not overlap with ROI in any projection
                * 1 if point overlaps with ROI in x-projection (``y_min <= y <= y_max``)
                * 2 if point overlaps with ROI in y-projection (``x_min <= x <= x_max``)
                * 3 if point overlaps with ROI in both projections
        """
        if P.ndim == 1:
            P = (P,)

        ret = 0
        for px, py in P:
            # Get coordinates
            a = self.sel_coords['slope']
            rect = self.sel_coords['polygon']
            x0 = rect[0,0]
            y0 = rect[0,1]
            x1 = rect[2,0]
            y1 = rect[2,1]

            # Upper and lower tangents of bounding box of rect
            y_horiz_up = a * (px - x0) + y0
            y_horiz_low = a * (px - x1) + y1

            # Left and right tangents of bounding box of rect
            if a == 0:
                x_vert_left = x0
                x_vert_right = x1
            else:
                x_vert_left = - a * (py - y0) + x0
                x_vert_right = - a * (py - y1) + x1

            # Collision detection
            if px >= x_vert_left and px <= x_vert_right:
                x_collision = True
            else:
                x_collision = False

            if py >= y_horiz_low and py <= y_horiz_up:
                y_collision = True
            else:
                y_collision = False

            # Determine collision result
            if y_collision:
                ret |= 1
            if x_collision:
                ret |= 2
            if ret == 3:
                break

        if check_projections:
            return ret
        else:
            return ret == 3


class RectRoi:
    def __init__(self, polygon):
       self.corners = polygon[:,::-1]
       self._coords = None
       self._area = None
       self._perimeter = None
       self.label = None

    @property
    def coords(self):
        if self._coords is None:
            pc = skid.polygon(self.corners[:,0], self.corners[:,1])
            self._coords = np.stack([pc[0], pc[1]], axis=1)
        return self._coords

    @property
    def area(self):
        if self._area is None:
            self._area = self.coords.shape[0]
        return self._area

    @property
    def perimeter(self):
        if self._perimeter is None:
            pc = skid.polygon_perimeter(self.corners[:,0], self.corners[:,1])
            self._perimeter = np.stack([pc[0], pc[1]], axis=1)
        return self._perimeter

    @property
    def rows(self):
        return self.coords[:,0]

    @property
    def cols(self):
        return self.coords[:,1]
