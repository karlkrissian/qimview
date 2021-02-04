
from .ViewerImage import *
from .utils import get_time
import sys
import time
import cv2
import numpy as np
from collections import deque
import rawpy
import math
import os

# check for module, needs python >= 3.4
# https://stackoverflow.com/questions/14050281/how-to-check-if-a-python-module-exists-without-importing-it
import importlib

has_simplejpeg = importlib.util.find_spec("simplejpeg") is not None
has_turbojpeg = importlib.util.find_spec("turbojpeg") is not None
print(
    f" ***  has_simplejpeg {has_simplejpeg}  has_turbojpeg {has_turbojpeg}   ***")

if has_simplejpeg:
    import simplejpeg
if has_turbojpeg:
    from turbojpeg import TurboJPEG, TJPF_RGB, TJPF_BGR, TJFLAG_FASTDCT


def read_libraw(image_filename, read_size='full', use_RGB=True, verbose=False):
    raw = rawpy.imread(image_filename)
    height, width = raw.raw_image.shape
    print(f"height, width {(height, width)}")
    # Transform Bayer image
    im1 = np.empty((height >> 1, width >> 1, 4), dtype=raw.raw_image.dtype)
    bayer_desc = raw.color_desc.decode('utf-8')
    bayer_pattern = raw.raw_pattern
    # not perfect, we may switch Gr and Gb
    bayer_desc = bayer_desc.replace('G', 'g', 1)
    # Detect the green channels?
    channel_pos = {'R': 0, 'g': 1, 'G': 2, 'B': 3}
    for i in range(2):
        for j in range(2):
            print("str(bayer_desc[bayer_pattern[i,j]]) {}".format(
                str(bayer_desc[bayer_pattern[i, j]])))
            pos = channel_pos[str(bayer_desc[bayer_pattern[i, j]])]
            im1[:, :, pos] = raw.raw_image[i::2, j::2]
    prec = math.ceil(math.log2(raw.white_level+1))
    viewer_image = ViewerImage(im1, precision=prec, downscale=1, channels=CH_RGGB)
    print("viewer_image channels {}".format(viewer_image.channels))
    return viewer_image


def libraw_supported_formats():
    # Need to find the complete list of supported formats
    return [".ARW", ".GPR"]


def read_jpeg_turbojpeg(image_filename, read_size='full', use_RGB=True, verbose=False):
    try:
        if verbose:
            start = get_time()
        # using default library installation
        jpeg = TurboJPEG()
        # decoding input.jpg to BGR array
        in_file = open(image_filename, 'rb')
        downscale = {'full': 1, '1/2': 2, '1/4': 4, '1/8': 8}[read_size]
        scale = (1, downscale)

        # do we need the fast DCT?
        flags = TJFLAG_FASTDCT
        pixel_format = TJPF_RGB if use_RGB else TJPF_BGR

        start1 = get_time()
        if verbose:
            im_header = jpeg.decode_header(in_file.read())
            print(f" header {im_header} {int(get_time() - start1) * 1000} ms")
        in_file.seek(0)
        im = jpeg.decode(in_file.read(), pixel_format=pixel_format, scaling_factor=scale, flags=flags)
        in_file.close()

        if verbose:
            print(f" turbojpeg read ...{image_filename[-15:]} took {get_time() - start:0.3f} sec.")
        viewer_image = ViewerImage(im, precision=8, downscale=downscale, channels=CH_RGB if use_RGB else CH_BGR)
        return viewer_image
    except Exception as e:
        print("read_jpeg: Failed to load image with turbojpeg {0}: {1}".format(image_filename, e))
        return None


def read_jpeg_simplejpeg(image_filename, read_size='full', use_RGB=True, verbose=False):
    if verbose:
        start_time = get_time()
    format = 'RGB' if use_RGB else 'BGR'
    with open(image_filename, 'rb') as d:
        im = simplejpeg.decode_jpeg(d.read(), format)

    if verbose:
        end_time = get_time()
        print(f" simplejpeg.decode_jpeg() {format} {os.path.basename(image_filename)} "
                f"took {int((end_time-start_time)*1000+0.5)} ms")
    viewer_image = ViewerImage(im, precision=8, downscale=1, channels=CH_RGB if use_RGB else CH_BGR)
    return viewer_image


def read_opencv(image_filename, read_size='full', use_RGB=True, verbose=False):
    if verbose:
        open_cv2_start = get_time()
    cv_size = {'full': cv2.IMREAD_COLOR,
                '1/2': cv2.IMREAD_REDUCED_COLOR_2,
                '1/4': cv2.IMREAD_REDUCED_COLOR_4,
                '1/8': cv2.IMREAD_REDUCED_COLOR_8,
                }
    cv2_im = cv2.imread(image_filename, cv_size[read_size])
    open_cv2_start2 = get_time()
    # transform default opencv BGR to RGB
    if use_RGB:
        im = cv2.cvtColor(cv2_im, cv2.COLOR_BGR2RGB)
    else:
        im = cv2_im
    if verbose:
        last_time = get_time()
        print(" cv2 imread {0} took {1:0.3f} ( {2:0.3f} + {3:0.3f} ) sec.".format(image_filename, last_time - open_cv2_start,
                                                                    open_cv2_start2 - open_cv2_start,
                                                                    last_time - open_cv2_start2),
                )
    downscale = {'full': 1, '1/2': 2, '1/4': 4, '1/8': 8}[read_size]
    viewer_image = ViewerImage(im, precision=8, downscale=downscale, channels=CH_RGB if use_RGB else CH_BGR)
    return viewer_image


def opencv_supported_formats():
    # according to the doc, opencv supports the following formats
    # Windows bitmaps - *.bmp, *.dib (always supported)
    # JPEG files - *.jpeg, *.jpg, *.jpe (see the Note section)
    # JPEG 2000 files - *.jp2 (see the Note section)
    # Portable Network Graphics - *.png (see the Note section)
    # WebP - *.webp (see the Note section)
    # Portable image format - *.pbm, *.pgm, *.ppm *.pxm, *.pnm (always supported)
    # PFM files - *.pfm (see the Note section)
    # Sun rasters - *.sr, *.ras (always supported)
    # TIFF files - *.tiff, *.tif (see the Note section)
    # OpenEXR Image files - *.exr (see the Note section)
    # Radiance HDR - *.hdr, *.pic (always supported)
    # Raster and Vector geospatial data supported by GDAL (see the Note section)    
    return [ '.bmp', '.dib', '.jpeg', '.jpg', '.jpe', '.jp2', '.png', '.webp', '.pbm', '.ppm', '.pxm', 
            '.pnm', '.pfm', '.sr', '.ras', '.tiff', '.tif', '.exr', '.hdr', '.pic']


def read_jpeg(image_filename, read_size='full', use_RGB=True, verbose=False):
    # verbose = True
    downscales = {'full': 1, '1/2': 2, '1/4': 4, '1/8': 8}
    if has_simplejpeg and read_size == 'full':
        return read_jpeg_simplejpeg(image_filename, read_size, use_RGB, verbose)
    if has_turbojpeg:
        return  read_jpeg_turbojpeg(image_filename, read_size=read_size, verbose=verbose, use_RGB=use_RGB)
        if im is not None:
            viewer_image = ViewerImage(im, precision=8, downscale=downscales[read_size],
                                        channels=CH_RGB if use_RGB else CH_BGR)
            return viewer_image
    return read_opencv(image_filename, read_size, use_RGB, verbose)


class ImageReader:
    def __init__(self):
        # set default plugins
        self._plugins = {
            ".JPG":read_jpeg,
            ".JPEG":read_jpeg,
        }
        # add libraw supported extensions
        for ext in libraw_supported_formats():
            if ext.upper() not in self._plugins:
                self._plugins[ext.upper()] = read_libraw
        # add all opencv supposedly supported extensions
        for ext in opencv_supported_formats():
            if ext.upper() not in self._plugins:
                self._plugins[ext.upper()] = read_opencv

    def extensions(self):
        return list(self._plugins.keys())

    def set_plugin(self, extensions, callback):
        """ Set support to a image format based on list of extensions and callback

        Args:
            extensions ([type]): [description]
            callback (function): callback has signature (image_filename, read_size='full', use_RGB=True, verbose=False) 
            and returns a ViewerImage object
        """
        for ext in extensions:
            self._plugins[ext.upper()] = callback

    def read(self, filename, read_size='full', use_RGB=True, verbose=False):
        extension = os.path.splitext(filename)[1].upper()
        if extension not in self._plugins:
            print(  f"ERROR: ImageRead.read({filename}) extension not supported, "
                    f"supported extensions are {self._plugins.keys()}")
            return None

        try:
            res = self._plugins[extension](filename, read_size, verbose, use_RGB)
            return res
        except Exception as e:
            print(f"Exception while reading image {filename}: {e}")
            return None

# unique instance of ImageReader for the application
image_reader = ImageReader()