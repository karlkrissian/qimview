#
#
#

from qimview.image_viewers.image_filter_parameters import ImageFilterParameters
from qimview.utils.utils import get_time
from qimview.utils.qt_imports import QtGui, QtCore, QtWidgets
QtKeys  = QtCore.Qt.Key
QtMouse = QtCore.Qt.MouseButton

import cv2
import traceback
import abc
import inspect
import numpy as np
from typing import TYPE_CHECKING, Optional, Tuple
# if TYPE_CHECKING:
from qimview.utils.viewer_image import ViewerImage, ImageFormat

try:
    import qimview_cpp
except Exception as e:
    has_cppbind = False
    print("Failed to load qimview_cpp: {}".format(e))
else:
    has_cppbind = True
print("Do we have cpp binding ? {}".format(has_cppbind))


# copied from https://stackoverflow.com/questions/17065086/how-to-get-the-caller-class-name-inside-a-function-of-another-class-in-python
def get_class_from_frame(fr):
  args, _, _, value_dict = inspect.getargvalues(fr)
  # we check the first parameter for the frame function is
  # named 'self'
  if len(args) and args[0] == 'self':
    # in that case, 'self' will be referenced in value_dict
    instance = value_dict.get('self', None)
    if instance:
      # return its class name
      try:
          # return getattr(instance, '__class__', None)
          return getattr(instance, '__class__', None).__name__
      except:
          return None
  # return None otherwise
  return None


def get_function_name():
    return traceback.extract_stack(None, 2)[0][2]

class trace_method():
    def __init__(self, tab):
        self.tab = tab
        method = traceback.extract_stack(None, 2)[0][2]
        print(self.tab[0] + method)
        self.tab[0] += '  '

    def __del__(self):
        self.tab[0] = self.tab[0][:-2]


class ImageViewer:

    def __init__(self, parent=None):
        self.data = None
        self._width = 500
        self._height = 500
        self.lastPos = None # Last mouse position before mouse click
        self.mouse_dx = self.mouse_dy = 0
        self.mouse_zx = 0
        self.mouse_zy = 0
        self.mouse_x = 0
        self.mouse_y = 0
        self.current_dx = self.current_dy = 0
        self.current_scale = 1
        self._image     : Optional[ViewerImage] = None
        self._image_ref : Optional[ViewerImage] = None
        self.synchronize_viewer = None
        self.tab = ["--"]
        self.trace_calls  = False
        self._image_name = ""
        self.active_window = False
        self.filter_params = ImageFilterParameters()
        self.save_image_clipboard = False
        self.clipboard = None
        self._display_timing = False
        self._verbose = False
        self.start_time = dict()
        self.timings = dict()
        self.replacing_widget = None
        self.before_max_parent = None
        self.show_histogram         : bool = True
        self.show_cursor            : bool = False
        self.show_overlay           : bool = False
        self.show_stats             : bool = False
        self.show_image_differences : bool = False
        self.show_intensity_line    : bool = False
        self.antialiasing           : bool = True
        # We track an image counter, changed by set_image, to help reducing same calculations
        self.image_id       = -1
        self.image_ref_id   = -1
        # Rectangle in which the histogram is displayed
        self._histo_rect : Optional[QtCore.QRect] = None
        # Histogram displayed scale
        self._histo_scale : int = 1
        # Widget dimensions to be defined in child resize event
        self.evt_width : int
        self.evt_height : int

    @property
    def display_timing(self):
        return self._display_timing

    @display_timing.setter
    def display_timing(self, v):
        self._display_timing = v

    @property
    def verbose(self):
        return self._verbose

    @verbose.setter
    def verbose(self, v):
        self._verbose = v

    def set_image(self, image : Optional[ViewerImage]):
        is_different = (self._image is None) or (self._image is not image)
        if image is not None:
            self.print_log('set_image({}): is_different = {}'.format(image.data.shape, is_different))
        if is_different:
            self._image = image
            self.image_id += 1
        return is_different

    def set_image_ref(self, image_ref : Optional[ViewerImage] = None):
        is_different = (self._image_ref is None) or (self._image_ref is not image_ref)
        if is_different:
            self._image_ref = image_ref
            self.image_ref_id += 1

    def set_clipboard(self, clipboard, save_image):
        self.clipboard = clipboard
        self.save_image_clipboard = save_image

    def print_log(self, mess, force=False):
        if self.verbose or force:
            caller_name = inspect.stack()[1][3]
            print("{}{}: {}".format(self.tab[0], caller_name, mess))

    def start_timing(self, title=None):
        if not self.display_timing: return
        if title is None:
            # it seems that inspect is slow
            caller_name = inspect.stack()[1][3]
            class_name = get_class_from_frame(inspect.stack()[1][0])
            if class_name is not None:
                caller_name = "{}.{}".format(class_name, caller_name)
        else:
            caller_name = title
        self.start_time[caller_name] = get_time()
        self.timings[caller_name] = ''

    def add_time(self, mess, current_start, force=False, title=None):
        if not self.display_timing: return
        if self.display_timing or force:
            if title is None:
                caller_name = inspect.stack()[1][3]
                class_name = get_class_from_frame(inspect.stack()[1][0])
                if class_name is not None:
                    caller_name = "{}.{}".format(class_name, caller_name)
            else:
                caller_name = title
            if caller_name in self.start_time:
                total_start = self.start_time[caller_name]
                ctime = get_time()
                mess = "{} {:0.1f} ms, total {:0.1f} ms".format(mess, (ctime -current_start)*1000, (ctime-total_start)*1000)
                self.timings[caller_name] += "{}{}: {}\n".format(self.tab[0], caller_name, mess)

    def print_timing(self, add_total=False, force=False, title=None):
        if not self.display_timing: return
        if title is None:
            caller_name = inspect.stack()[1][3]
            class_name = get_class_from_frame(inspect.stack()[1][0])
            if class_name is not None:
                caller_name = "{}.{}".format(class_name, caller_name)
        else:
            caller_name = title
        if add_total:
            self.add_time("total", self.start_time[caller_name], force)
        if self.timings[caller_name] != '':
            print(self.timings[caller_name])

    def set_synchronize(self, viewer):
        self.synchronize_viewer = viewer

    def synchronize_data(self, other_viewer):
        other_viewer.current_scale = self.current_scale
        other_viewer.current_dx = self.current_dx
        other_viewer.current_dy = self.current_dy
        other_viewer.mouse_dx   = self.mouse_dx
        other_viewer.mouse_dy   = self.mouse_dy
        other_viewer.mouse_zx   = self.mouse_zx
        other_viewer.mouse_zy   = self.mouse_zy
        other_viewer.mouse_x    = self.mouse_x
        other_viewer.mouse_y    = self.mouse_y

        other_viewer.show_histogram      = self.show_histogram
        other_viewer.show_cursor         = self.show_cursor
        other_viewer.show_intensity_line = self.show_intensity_line
        other_viewer._histo_scale        = self._histo_scale

    def synchronize(self, event_viewer):
        """
        This method needs to be overloaded with call to self.synchronize_viewer.synchronize()
        :param event_viewer: the viewer that started the synchronization
        :return:
        """
        if self==event_viewer:
            if self.display_timing:
                start_time = get_time()
                if self.display_timing:
                    print("[ --- Start sync")
        if self.synchronize_viewer is not None and self.synchronize_viewer is not event_viewer:
            self.synchronize_data(self.synchronize_viewer)
            self.synchronize_viewer.viewer_update()
            self.synchronize_viewer.synchronize(event_viewer)
        if self==event_viewer:
            if self.display_timing:
                print('       End sync --- {:0.1f} ms'.format((get_time()-start_time)*1000))

    def set_active(self, active=True):
        self.active_window = active

    def is_active(self):
        return self.active_window

    @property
    def image_name(self) -> str:
        return self._image_name

    @image_name.setter
    def image_name(self, v : str):
        self._image_name = v

    def get_image(self):
        return self._image

    def new_scale(self, mouse_zy, height):
        return max(1, self.current_scale * (1 + mouse_zy * 5.0 / self._height))
        # return max(1, self.current_scale  + mouse_zy * 5.0 / height)

    def new_translation(self):
        dx = self.current_dx + self.mouse_dx/self.current_scale
        dy = self.current_dy + self.mouse_dy/self.current_scale
        return dx, dy

    def check_translation(self):
        return self.new_translation()

    @abstractmethod
    def viewer_update(self):
        pass

    def mouse_press_event(self, event):
        self.lastPos = event.pos()
        if event.buttons() & QtMouse.RightButton:
            event.accept()

    def mouse_move_event(self, event):
        self.mouse_x = event.x()
        self.mouse_y = event.y()
        if self.show_overlay:
            self.viewer_update()
        if event.buttons() & QtMouse.LeftButton:
            self.mouse_dx = event.x() - self.lastPos.x()
            self.mouse_dy = - (event.y() - self.lastPos.y())
            self.viewer_update()
            self.synchronize(self)
            event.accept()
        else:
            if event.buttons() & QtMouse.RightButton:
                # right button zoom
                self.mouse_zx = event.x() - self.lastPos.x()
                self.mouse_zy = - (event.y() - self.lastPos.y())
                self.viewer_update()
                self.synchronize(self)
                event.accept()
            else:
                modifiers = QtWidgets.QApplication.keyboardModifiers()
                if self.show_cursor:
                    self.viewer_update()
                    self.synchronize(self)

    def mouse_release_event(self, event):
        if event.button() & QtMouse.LeftButton:
            self.current_dx, self.current_dy = self.check_translation()
            self.mouse_dy = 0
            self.mouse_dx = 0
            event.accept()
        if event.button() & QtMouse.RightButton:
            if self._image is not None:
                self.current_scale = self.new_scale(self.mouse_zy, self._image.data.shape[0])
            self.mouse_zy = 0
            self.mouse_zx = 0
            event.accept()
        self.synchronize(self)

    def mouse_double_click_event(self, event):
        self.print_log("double click ")
        # Check if double click is on histogram, if so, toggle histogram size
        if self._histo_rect and self._histo_rect.contains(event.x(), event.y()):
            # scale loops from 1 to 3 
            self._histo_scale = (self._histo_scale % 3) + 1 
            self.viewer_update()
            event.accept()
            return
        # Else set current viewer active
        self.set_active()
        self.viewer_update()
        if self.synchronize_viewer is not None:
            v = self.synchronize_viewer
            while v != self:
                v.set_active(False)
                v.viewer_update()
                if v.synchronize_viewer is not None:
                    v = v.synchronize_viewer

    def mouse_wheel_event(self,event):
        # Zoom by applying a factor to the distances to the sides
        if hasattr(event, 'delta'):
            delta = event.delta()
        else:
            delta = event.angleDelta().y()
        # print("delta = {}".format(delta))
        coeff = delta/5
        # coeff = 20 if delta > 0 else -20
        if self._image:
            self.current_scale = self.new_scale(coeff, self._image.data.shape[0])
            self.viewer_update()
            self.synchronize(self)

    def find_in_layout(self, layout: QtWidgets.QLayout) -> Optional[QtWidgets.QLayout]:
        """ Search Recursivement in Layouts for the current widget

        Args:
            layout (QtWidgets.QLayout): input layout for search

        Returns:
            layout containing the current widget or None if not found
        """
        if layout.indexOf(self) != -1: return layout
        for i in range(layout.count()):
            item = layout.itemAt(i)
            if item.widget() == self: return layout
            if (l := item.layout()) and (found:=self.find_in_layout(l)): return l
        return None

    def toggle_fullscreen(self, event):
        print(f"toggle_fullscreen")
        if not issubclass(self.__class__,QtWidgets.QWidget):
            print(f"Cannot use toggle_fullscreen on a class that is not a QWidget")
            return
        # Should be inside a layout
        if self.before_max_parent is None:
            if self.parent() is not None and (playout := self.parent().layout()) is not None:
                if self.find_in_layout(playout):
                    self.before_max_parent = self.parent()
                    self.replacing_widget = QtWidgets.QWidget(self.before_max_parent)
                    self.parent().layout().replaceWidget(self, self.replacing_widget)
                    # We need to go up from the parent widget to the main window to get its geometry
                    # so that the fullscreen is display on the same monitor
                    toplevel_parent : Optional[QtWidgets.QWidget] = self.parentWidget()
                    while toplevel_parent.parentWidget(): toplevel_parent = toplevel_parent.parentWidget()
                    self.setParent(None)
                    if toplevel_parent: self.setGeometry(toplevel_parent.geometry())
                    self.showFullScreen()
                    event.accept()
                    return
        if self.before_max_parent is not None:
            self.setParent(self.before_max_parent)
            self.parent().layout().replaceWidget(self.replacing_widget, self)
            self.replacing_widget = self.before_max_parent = None
            # self.resize(self.before_max_size)
            self.show()
            self.parent().update()
            self.setFocus()
            event.accept()
            return

    # def mouseDoubleClickEvent(self, event):

    def key_press_event(self, event, wsize):
        self.print_log(f"ImageViewer: key_press_event {event.key()}")
        if type(event) == QtGui.QKeyEvent:

            if event.key() == QtKeys.Key_F1:
                import qimview
                mb = QtWidgets.QMessageBox(self)
                mb.setWindowTitle(f"qimview {qimview.__version__}: MultiView help")
                mb.setTextFormat(QtCore.Qt.TextFormat.RichText)
                mb.setText(
                    "<a href='https://github.com/qimview/qimview/wiki'>qimview</a><br>"
                    "<a href='https://github.com/qimview/qimview/wiki/3.-Image-Viewers'>Image Viewer</a>")
                mb.exec()
                event.accept()

            if event.key() == QtKeys.Key_F11:
                self.toggle_fullscreen(event)
                return

            # allow to switch between images by pressing Alt+'image position' (Alt+0, Alt+1, etc)
            key_list = []

            # # select upper left crop
            # key_list.append(QtCore.Qt.Key_A)
            # if event.key() == QtCore.Qt.Key_A:
            #     self.current_dx = wsize.width()/4
            #     self.current_dy = -wsize.height()/4
            #     self.current_scale = 2

            # select upper left crop
            key_list.append(QtKeys.Key_B)
            if event.key() == QtKeys.Key_B:
                self.current_dx = -wsize.width() / 4
                self.current_dy = -wsize.height() / 4
                self.current_scale = 2

            # # select lower left crop
            # key_list.append(QtCore.Qt.Key_C)
            # if event.key() == QtCore.Qt.Key_C:
            #     self.current_dx = wsize.width() / 4
            #     self.current_dy = wsize.height() / 4
            #     self.current_scale = 2

            # # select lower right crop
            # key_list.append(QtCore.Qt.Key_D)
            # if event.key() == QtCore.Qt.Key_D:
            #     self.current_dx = -wsize.width() / 4
            #     self.current_dy = wsize.height() / 4
            #     self.current_scale = 2

            # select full crop
            key_list.append(QtKeys.Key_F)
            if event.key() == QtKeys.Key_F:
                self.output_crop = (0., 0., 1., 1.)
                self.current_dx = 0
                self.current_dy = 0
                self.current_scale = 1

            # toggle antialiasing
            key_list.append(QtKeys.Key_A)
            if event.key() == QtKeys.Key_A:
                self.antialiasing = not self.antialiasing
                print(f"antialiasing {self.antialiasing}")

            # toggle histograph
            key_list.append(QtKeys.Key_H)
            if event.key() == QtKeys.Key_H:
                self.show_histogram = not self.show_histogram

            # toggle overlay
            key_list.append(QtKeys.Key_O)
            if event.key() == QtKeys.Key_O:
                self.show_overlay = not self.show_overlay

            # C: toggle cursor
            key_list.append(QtKeys.Key_C)
            if event.key() == QtKeys.Key_C:
                self.show_cursor = not self.show_cursor

            # D: toggle image differences
            key_list.append(QtKeys.Key_D)
            if event.key() == QtKeys.Key_D:
                self.show_image_differences = not self.show_image_differences

            # S: display stats on currrent image
            key_list.append(QtKeys.Key_S)
            if event.key() == QtKeys.Key_S:
                self.show_stats = not self.show_stats

            # I: display intensity line
            key_list.append(QtKeys.Key_I)
            if event.key() == QtKeys.Key_I:
                self.show_intensity_line = not self.show_intensity_line

            if event.key() in key_list:
                self.viewer_update()
                self.synchronize(self)
                event.accept()
                return
            event.ignore()
        else:
            event.ignore()

    def display_message(self, im_pos: Optional[Tuple[int,int]], scale = None) -> str:
        text : str = self.image_name
        if self.show_cursor and im_pos:
            text +=  f"\n {self._image.data.shape} {self._image.data.dtype} prec:{self._image.precision}"
            if scale is not None:
                text += f"\n x{scale:0.2f}"
            im_x, im_y = im_pos
            values = self._image.data[im_y, im_x]
            text += f"\n pos {im_x:4}, {im_y:4} \n rgb {values}"

        if self.show_overlay:
            text += "\n ref | im " 
        if self.show_image_differences:
            text += "\n im - ref" 
        return text

    def display_text(self, painter: QtGui.QPainter, text: str) -> None:
        self.start_timing()
        color = QtGui.QColor(255, 50, 50, 255) if self.is_active() else QtGui.QColor(50, 50, 255, 255)
        painter.setPen(color)
        font = QtGui.QFont('Decorative', 12)
        # font.setBold(True)
        painter.setFont(font)
        painter.setBackground(QtGui.QColor(250, 250, 250, int(0.75*255)))
        painter.setBackgroundMode(QtGui.Qt.BGMode.OpaqueMode)
        text_options = \
            QtCore.Qt.AlignmentFlag.AlignTop  | \
            QtCore.Qt.AlignmentFlag.AlignLeft | \
            QtCore.Qt.TextFlag.TextWordWrap
        area_width = 400
        area_height = 200
        # boundingRect is interesting but slow to be called at each display
        # bounding_rect = painter.boundingRect(0, 0, area_width, area_height, text_options, self.display_message)
        margin_x = 8
        margin_y = 5
        painter.drawText(
            margin_x, 
            # self.evt_height-margin_y-bounding_rect.height(), area_width, area_height,
            margin_y, area_width, area_height,
            text_options,
            text
            )
        self.print_timing()

    def compute_histogram(self, current_image, show_timings=False):
        # print(f"compute_histogram show_timings {show_timings}")
        if show_timings: h_start = get_time()
        # Compute steps based on input image resolution
        im_w, im_h = current_image.shape[1], current_image.shape[0]
        target_w = 800
        target_h = 600
        hist_x_step = max(1, int(im_w/target_w+0.5))
        hist_y_step = max(1, int(im_h/target_h+0.5))
        input_image = current_image
        # print(f"current_image {current_image.shape} _image {self._image.shape}")
        # input_image = self._image
        resized_im = input_image[::hist_y_step, ::hist_x_step, :]
        resized_im = input_image
        if self.verbose:
            print(f"qtImageViewer.compute_histograph() steps are {hist_x_step, hist_y_step} "
                f"shape {current_image.shape} --> {resized_im.shape}")
        if show_timings: resized_time = get_time()-h_start

        calc_hist_time = 0

        # First compute all histograms
        if show_timings: start_hist = get_time()
        hist_all = np.empty((3, 256), dtype=np.float32)
        # print(f"{resized_im[::100,::100,:]}")
        for channel, im_ch in enumerate(cv2.split(resized_im)):
            # hist = cv2.calcHist(resized_im[:, :, channel], [0], None, [256], [0, 256])
            hist = cv2.calcHist([im_ch], [0], None, [256], [0, 256])
            # print(f"max diff {np.max(np.abs(hist-hist2))}")
            hist_all[channel, :] = hist[:, 0]

        hist_all = hist_all / np.max(hist_all)
        if show_timings: end_hist = get_time()
        if show_timings: calc_hist_time += end_hist-start_hist
        if show_timings: gauss_start = get_time()
        hist_all = cv2.GaussianBlur(hist_all, (7, 1), sigmaX=1.5, sigmaY=0.2)
        if show_timings: gauss_time = get_time() - gauss_start

        if show_timings: 
            print(f"compute_histogram took {(get_time()-h_start)*1000:0.1f} msec. ", end="")
            print(f"from which calchist:{calc_hist_time*1000:0.1f}, "
              f"resizing:{resized_time*1000:0.1f}, "
              f"gauss:{gauss_time*1000:0.1f}")

        return hist_all

    def compute_histogram_Cpp(self, current_image, show_timings=False):
        # print(f"compute_histogram show_timings {show_timings}")
        if show_timings: h_start = get_time()
        # Compute steps based on input image resolution
        im_w, im_h = current_image.shape[1], current_image.shape[0]
        target_w = 800
        target_h = 600
        hist_x_step = max(1, int(im_w/target_w+0.5))
        hist_y_step = max(1, int(im_h/target_h+0.5))
        output_histogram = np.empty((3,256), dtype=np.uint32)
        qimview_cpp.compute_histogram(current_image, output_histogram, int(hist_x_step), int(hist_y_step))
        if show_timings: t1 = get_time()
        hist_all = output_histogram.astype(np.float32)
        hist_all = hist_all / np.max(hist_all)
        hist_all = cv2.GaussianBlur(hist_all, (7, 1), sigmaX=1.5, sigmaY=0.2)
        if show_timings: print(f"qimview_cpp.compute_histogram took {(get_time()-h_start)*1000:0.1f} ms, "
                                f"{(get_time()-t1)*1000:0.1f} ms")
        return hist_all

    def display_histogram(self, hist_all, id, painter, im_rect, show_timings=False):
        """
        :param painter:
        :param rect: displayed image area
        :return:
        """
        if hist_all is None:
            return
        histo_timings = show_timings
        #if histo_timings:
        h_start = get_time()
        # Histogram: keep constant width/height ratio
        display_ratio : float = 2.0
        # print(f'im_rect = {im_rect}')
        w, h = self.evt_width, self.evt_height
        width   : int = int( min(w/4*self._histo_scale, h/3*self._histo_scale))
        height  : int = int( width/display_ratio)
        start_x : int = w - width*id - 10
        start_y : int = h - 10
        margin  : int = 3

        if histo_timings: rect_start = get_time()
        rect = QtCore.QRect(start_x-margin, start_y-margin-height, width+2*margin, height+2*margin)
        self._histo_rect = rect
        # painter.fillRect(rect, QtGui.QBrush(QtGui.QColor(255, 255, 255, 128+64)))
        # Transparent light grey
        painter.fillRect(rect, QtGui.QColor(205, 205, 205, 128+32))
        if histo_timings: rect_time = get_time()-rect_start

        # print(f"current_image {current_image.shape} _image {self._image.shape}")
        # input_image = self._image
        path_time = 0

        pen = QtGui.QPen()
        pen.setWidth(2)

        qcolors = {
            0: QtGui.QColor(255, 50, 50, 255),
            1: QtGui.QColor(50, 255, 50, 255),
            2: QtGui.QColor(50, 50, 255, 255)
        }

        step_x = float(width) / 256
        step = 2
        x_range = np.array(range(0, 256, step))
        x_pos = start_x + x_range*step_x

        for channel in range(3):
            pen.setColor(qcolors[channel])
            painter.setPen(pen)
            # painter.setBrush(color)
            # print(f"histogram painting 1 took {get_time() - h_start} sec.")

            # print(f"histogram painting 2 took {get_time() - h_start} sec.")

            if histo_timings: start_path = get_time()

            # apply a small Gaussian filtering to histogram curve
            path = QtGui.QPainterPath()

            y_pos = start_y - hist_all[channel, x_range]*height
            # polygon = QtGui.QPolygonF([QtCore.QPointF(x_pos[n], y_pos[n]) for n in range(len(x_range))])
            # path.addPolygon(polygon)
            path.moveTo(x_pos[0], y_pos[0])
            for n in range(1,len(x_range)):
                path.lineTo(x_pos[n], y_pos[n])
            painter.drawPath(path)
            if histo_timings: path_time += get_time()-start_path

        if histo_timings: 
            print(f"display_histogram took {(get_time()-h_start)*1000:0.1f} msec. ", end='')
            print(f"from which path:{int(path_time*1000)}, rect:{int(rect_time*1000)}")


    def display_intensity_line(self, 
                               painter: QtGui.QPainter, 
                               im_rect: QtCore.QRect, 
                               line: np.ndarray,
                               channels : ImageFormat,
                                ) -> None:
        #if histo_timings:
        h_start = get_time()
        # print(f'im_rect = {im_rect}')
        w, h = self.evt_width, self.evt_height
        width    : int = im_rect.width()
        height   : int = int( h/5)
        start_x  : int = im_rect.x()
        margin_y : int = 2
        start_y  : int = h-margin_y

        rect = QtCore.QRect(start_x, start_y-height, width, height)
        self._line_rect = rect
        painter.fillRect(rect, QtGui.QColor(205, 205, 205, 128+32))

        pen = QtGui.QPen()
        pen.setWidth(1)

        # Adapt for Bayer, Y, etc ...
        qcolors = {
            'R' : QtGui.QColor(240,  30,  30, 255),
            'G' : QtGui.QColor( 30, 240,  30, 255),
            'Gr': QtGui.QColor(130, 240,  30, 255),
            'Gb': QtGui.QColor( 30, 240, 130, 255),
            'B' : QtGui.QColor( 30,  30, 240, 255),
            'Y' : QtGui.QColor( 30,  30,  30, 255),
        }
        colors = {
            ImageFormat.CH_RGB  : ['R','G','B'],
            ImageFormat.CH_BGR  : ['B','G','R'],
            ImageFormat.CH_RGGB : ['R','Gr','Gb','B'],
            ImageFormat.CH_GRBG : ['Gr','R','B','Gb'],
            ImageFormat.CH_GBRG : ['Gb','B','R','Gr'],
            ImageFormat.CH_BGGR : ['B','Gb','Gr','R'],
        }[channels]
        assert line.shape[1] == len(colors), f"Error: Mismatch between imageformat and number of channels"

        nb_values = line.shape[0]
        step_x = float(width) / nb_values
        x_range = np.array(range(0, nb_values))
        x_pos = start_x + (x_range+0.5)*step_x

        max_val = np.max(line)
        line = line.astype(np.float32)
        in_margin = 2
        in_start_y = start_y - in_margin
        in_height  = height - 2*in_margin
        for channel in range(len(colors)):
            pen.setColor(qcolors[colors[channel]])
            painter.setPen(pen)
            # apply a small Gaussian filtering to histogram curve
            path = QtGui.QPainterPath()
            y_pos = (in_start_y - line[:,channel]*(in_height/max_val)+0.5).astype(np.uint32)
            path.moveTo(x_pos[0], y_pos[0])
            for n in range(1,len(x_range)):
                path.lineTo(x_pos[n], y_pos[n])
            painter.drawPath(path)


