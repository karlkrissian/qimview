import cppimport.import_hook
from qimview.CppBind import wrap_numpy
import numpy as np
import cv2
import timeit 

w, h   = 5000, 4000
w2, h2 = 2500, 2000

# w, h   = 4, 2
# w2, h2 = 2, 1

a = (np.random.rand(h,w,3)*256).astype(np.uint8)
b = np.zeros((h2,w2,a.shape[2]), dtype=np.uint8)


# %timeit wrap_numpy.image_binning_2x2(a,b)
# %timeit c = cv2.resize(a, (w2, h2), interpolation=cv2.INTER_AREA)

wrap_numpy.image_binning_2x2_test1(a,b)
c = cv2.resize(a, (w2, h2), interpolation=cv2.INTER_AREA)

print(f" diff min {np.min(c-b)} max {np.max(c-b)}")