import nd2
import numpy as np

my_array = nd2.imread('some_file.nd2')                          # read to numpy array
my_array = nd2.imread('some_file.nd2', dask=True)               # read to dask array
my_array = nd2.imread('some_file.nd2', xarray=True)             # read to xarray
my_array = nd2.imread('some_file.nd2', xarray=True, dask=True)  # read to dask-xarray

# or open a file with nd2.ND2File
f = nd2.ND2File('some_file.nd2')

# (you can also use nd2.ND2File() as a context manager)
with nd2.ND2File('some_file.nd2') as ndfile:
    print(ndfile.metadata)
    ...


# ATTRIBUTES:   # example output
f.path          # 'some_file.nd2'
f.shape         # (10, 2, 256, 256)
f.ndim          # 4
f.dtype         # np.dtype('uint16')
f.size          # 1310720  (total voxel elements)
f.sizes         # {'T': 10, 'C': 2, 'Y': 256, 'X': 256}
f.is_rgb        # False (whether the file is rgb)
                # if the file is RGB, `f.sizes` will have
                # an additional {'S': 3} component

# ARRAY OUTPUTS
f.asarray()         # in-memory np.ndarray - or use np.asarray(f)
f.to_dask()         # delayed dask.array.Array
f.to_xarray()       # in-memory xarray.DataArray, with labeled axes/coords
f.to_xarray(delayed=True)   # delayed xarray.DataArray

# OME-TIFF OUTPUT (new in v0.10.0)
f.write_tiff('output.ome.tif')  # write to ome-tiff file

                    # see below for examples of these structures
# METADATA          # returns instance of ...
f.attributes        # nd2.structures.Attributes
f.metadata          # nd2.structures.Metadata
f.frame_metadata(0) # nd2.structures.FrameMetadata (frame-specific meta)
f.experiment        # List[nd2.structures.ExpLoop]
f.text_info         # dict of misc info
f.voxel_size()      # VoxelSize(x=0.65, y=0.65, z=1.0)

f.rois              # Dict[int, nd2.structures.ROI]
f.binary_data       # any binary masks stored in the file.  See below.
f.events()          # returns tabular "Recorded Data" view from in NIS Elements/Viewer
                    # with info for each frame in the experiment.
                    # output is passabled to pandas.DataFrame

f.ome_metadata()    # returns metadata as an ome_types.OME object
                    # (requires ome-types package)

# allll the metadata we can find...
# no attempt made to standardize or parse it
# look in here if you're searching for metadata that isn't exposed in the above
# but try not to rely on it, as it's not guaranteed to be stable
f.unstructured_metadata()

f.close()           # don't forget to close when not using a context manager!
f.closed            # boolean, whether the file is closed