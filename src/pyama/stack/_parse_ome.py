import re
import xml.etree.ElementTree as ET

def _get_val(ep, name):
    """Get value of attribute 'name' from Pixels element 'ep'"""
    val = ep.attrib.get(name)
    try:
        val = int(val)
    except Exception:
        raise ValueError(f"Bad '{val}' value in OME description.")
    if val < 1:
        raise ValueError(f"Non-positive '{val}' value in OME description.")
    return val


def parse_ome(ome, n_images=None):
    """Extract stack information from description in OME format."""
    root = ET.fromstring(ome)

    # Find XML namespace
    # The namespace of an XML tag is prefixed to the tag name in
    # curly braces; see documentation of `xml.etree.ElementTree`.
    idx = root.tag.rfind('}')
    if idx == -1:
        xmlns = ''
    else:
        xmlns = root.tag[:idx+1]

    # Find "Image" tag
    tag_image = ''.join((xmlns, "Image"))
    for child in root:
        if child.tag == tag_image:
            element_image = child
            break
    else:
        raise TypeError("No 'Image' tag found in OME description.")

    # Find "Pixels" tag
    tag_pixels = ''.join((xmlns, "Pixels"))
    for child in element_image:
        if child.tag == tag_pixels:
            element_pixels = child
            break
    else:
        raise TypeError("No 'Pixels' tag found in OME description.")

    # Get image properties from attributes of "Pixels" tag
    # Number of frames
    sizeT = _get_val(element_pixels, 'SizeT')

    # Number of channels
    sizeC = _get_val(element_pixels, 'SizeC')

    # Number of slices
    sizeZ = _get_val(element_pixels, 'SizeZ')
    if sizeZ != 1:
        raise ValueError(f"Only images with one slice supported; found {sizeZ} slices.")

    # Check for inconsistent OME metadata
    # (and try to fix inconsistency)
    if n_images is not None and sizeT * sizeC != n_images:
        found_correct_size = False

        # Find "Description" tag
        desc = None
        tag_desc = ''.join((xmlns, "Description"))
        for child in element_image:
            if child.tag == tag_desc:
                desc = child.text
                break

        # Parse description
        if desc:
            for l in desc.splitlines():
                if l.startswith("Dimensions"):
                    try:
                        sizeT_desc = int(re.search(r'T\((\d+)\)', l)[1])
                    except TypeError:
                        sizeT_desc = None
                    try:
                        sizeC_desc = int(re.search(r'λ\((\d+)\)', l)[1])
                    except TypeError:
                        sizeC_desc = None
                    break
            if sizeT_desc is not None and sizeT_desc * sizeC == n_images:
                found_correct_size = True
                sizeT = sizeT_desc
            elif sizeC_desc is not None and sizeT * sizeC_desc == n_images:
                found_correct_size = True
                sizeC = sizeC_desc
            elif None not in (sizeT_desc, sizeC_desc) and sizeT_desc * sizeC_desc == n_images:
                found_correct_size = True
                sizeT = sizeT_desc
                sizeC = sizeC_desc
        if not found_correct_size:
            raise ValueError("Cannot determine image shape.")

    # Dimension order
    dim_order = element_pixels.attrib.get("DimensionOrder")
    if not dim_order:
        raise ValueError("No 'DimensionOrder' found in OME description.")

    return sizeT, sizeC, dim_order
