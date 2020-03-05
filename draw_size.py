from scipy.spatial import distance as dist
from imutils import perspective
from imutils import contours
import numpy as np
import argparse
import imutils
import cv2


class AppControl():
    def __init__(self):
        self.MINIMUN_SIZE_TOLERANCE = 100.0
        self.argument_parser = argparse.ArgumentParser()
        self.stop_video = False
        

    def get_arguments(self):
        self.argument_parser.add_argument('-c', '--camera', type=int, default=1,
                                          help='webcam source id')
        self.argument_parser.add_argument('-w', '--width', type=float, default=2.0,
                                          help='width of the left-most object in the image (in cm)')
        self.argument_parser.add_argument('-f', '--float', type=int, default=1,
                                          help='floating point precision')
        arguments = vars(self.argument_parser.parse_args())
        return arguments


class Color():
    RED = (255, 0, 0)
    GREEN = (0, 255, 0)
    BLUE = (0, 0, 255)
    YELLOW = (255, 255, 0)
    MAGENTA = (255, 0, 255)
    CYAN = (0, 255, 255)
    BLACK = (0, 0, 0)
    WHITE = (255, 255, 255)


class Geometry():
    @staticmethod
    def get_midpoint(point_a, point_b):
        return ((point_a[0] + point_b[0]) * 0.5, (point_a[1] + point_b[1]) * 0.5)


class Video(object):
    def __init__(self, camera_id):
        self._video_capture = cv2.VideoCapture(camera_id)
        # self._video_capture.set(cv2.CAP_PROP_FRAME_WIDTH, )
        # self._video_capture.set(cv2.CAP_PROP_FRAME_HEIGHT, )
        self._window_name = 'Video'
        cv2.namedWindow(self._window_name, cv2.WINDOW_AUTOSIZE)
        cv2.moveWindow(self._window_name, 0, 0)

    def get_frame(self):
        ret, frame = self._video_capture.read()
        return frame

    def update_window(self, frame):
        cv2.imshow(self._window_name, frame)

    def stop_when_key_press(self, key):
        stop = False
        if cv2.waitKey(1) & 0xFF == ord(key):
            stop = True
        return stop

    def finish(self):
        self._video_capture.release()
        cv2.destroyAllWindows()


class ObjectDetector(object):
    def __init__(self, *args, **kwargs):
        return super().__init__(*args, **kwargs)

    def get_edges(self, frame):
        gray_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray_frame = cv2.GaussianBlur(gray_frame, (7, 7), 0)
        edged_frame = cv2.Canny(gray_frame, 50, 100)
        edged_frame = cv2.dilate(edged_frame, None, iterations=1)
        edged_frame = cv2.erode(edged_frame, None, iterations=1)
        return edged_frame

    def get_contours(self, edged_frame):
        shapes_contours = None
        all_contours = cv2.findContours(
            edged_frame.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if len(all_contours) == 2:
            grabed_contours = imutils.grab_contours(all_contours)
            if len(grabed_contours) > 0:
                (sorted_contours, _) = contours.sort_contours(grabed_contours)
                shapes_contours = sorted_contours
        return shapes_contours

    def get_shapes_contours(self, frame):
        edged_frame = self.get_edges(frame)
        shapes_contours = self.get_contours(edged_frame)
        return shapes_contours

    def detect(self, c):
        shape = "desconhecido"
        peri = cv2.arcLength(c, True)
        approx = cv2.approxPolyDP(c, 0.04 * peri, True)

        if len(approx) <= 2:
            shape = "linha"

        elif len(approx) == 3:
            shape = "triangulo"

        elif len(approx) == 4:
            (x, y, w, h) = cv2.boundingRect(approx)
            ar = w / float(h)
            shape = "quadrado" if ar >= 0.95 and ar <= 1.05 else "retangulo"

        elif len(approx) == 5:
            shape = "pentagono"

        else:
            shape = "circulo"

        return shape


class Box(object):
    def __init__(self, shape_contour):
        min_area_rect = cv2.minAreaRect(shape_contour)
        points = cv2.cv.BoxPoints(min_area_rect) if imutils.is_cv2(
        ) else cv2.boxPoints(min_area_rect)
        points_int = np.array(points, dtype="int")
        self.points = perspective.order_points(points_int)


class ResultFrame(object):
    def paint(self, frame, box_points, reference_width, float_precision, shape_name):
        cv2.drawContours(
            frame, [box_points.astype("int")], -1, Color.GREEN, 2)

        for (x, y) in box_points:
            cv2.circle(frame, (int(x), int(y)), 5, Color.BLUE, -1)

        (tl, tr, br, bl) = box_points
        (tltrX, tltrY) = Geometry.get_midpoint(tl, tr)
        (blbrX, blbrY) = Geometry.get_midpoint(bl, br)
        (tlblX, tlblY) = Geometry.get_midpoint(tl, bl)
        (trbrX, trbrY) = Geometry.get_midpoint(tr, br)

        # draw lines between the midpoints
        cv2.line(frame, (int(tltrX), int(tltrY)), (int(blbrX), int(blbrY)),
                 Color.MAGENTA, 2)
        cv2.line(frame, (int(tlblX), int(tlblY)), (int(trbrX), int(trbrY)),
                 Color.MAGENTA, 2)

        # draw the midpoints on the image
        cv2.circle(frame, (int(tltrX), int(tltrY)), 5, Color.RED, -1)
        cv2.circle(frame, (int(blbrX), int(blbrY)), 5, Color.RED, -1)
        cv2.circle(frame, (int(tlblX), int(tlblY)), 5, Color.RED, -1)
        cv2.circle(frame, (int(trbrX), int(trbrY)), 5, Color.RED, -1)

        # compute the Euclidean distance between the midpoints
        dA = dist.euclidean((tltrX, tltrY), (blbrX, blbrY))
        dB = dist.euclidean((tlblX, tlblY), (trbrX, trbrY))

        pixelsPerMetric = dB / reference_width

        # compute the size of the object
        dimA = dA / pixelsPerMetric
        dimB = dB / pixelsPerMetric

        # draw the object sizes on the image
        if float_precision <= 0:
            text_dimA = f'{dimA:.0f}cm'
            text_dimB = f'{dimB:.0f}cm'
        elif float_precision == 1:
            text_dimB = f'{dimB:.1f}cm'
            text_dimA = f'{dimA:.1f}cm'
        elif float_precision == 2:
            text_dimA = f'{dimA:.2f}cm'
            text_dimB = f'{dimB:.2f}cm'
        else:
            text_dimA = f'{dimA:.3f}cm'
            text_dimB = f'{dimB:.3f}cm'

        cv2.putText(frame, text_dimA,
                    (int(tltrX - 15), int(tltrY - 10)), cv2.FONT_HERSHEY_SIMPLEX,
                    0.65, Color.WHITE, 2)
        cv2.putText(frame, text_dimB,
                    (int(trbrX + 10), int(trbrY)), cv2.FONT_HERSHEY_SIMPLEX,
                    0.65, Color.WHITE, 2)

        cv2.putText(frame, shape_name,
                    (int(tr[0] + 10), int(tr[1]) - 20), cv2.FONT_HERSHEY_SIMPLEX,
                    0.65, Color.RED, 2)
        return frame


def main():
    app_control = AppControl()
    arguments = app_control.get_arguments()
    camera_id = arguments['camera']
    reference_width = arguments['width']
    float_precision = arguments['float']
    video = Video(camera_id)
    object_detector = ObjectDetector()
    result_frame = ResultFrame()
    while not app_control.stop_video:
        frame = video.get_frame()
        shapes_contours = object_detector.get_shapes_contours(frame)
        painted_frame = frame.copy()
        if shapes_contours != None:
            for shape_contour in shapes_contours:
                if cv2.contourArea(shape_contour) <= app_control.MINIMUN_SIZE_TOLERANCE:
                    continue
                shape_name = object_detector.detect(shape_contour)
                box = Box(shape_contour)
                painted_frame = result_frame.paint(
                    painted_frame, box.points, reference_width, float_precision, shape_name)
        video.update_window(painted_frame)
        app_control.stop_video = video.stop_when_key_press('q')


if __name__ == '__main__':
    main()
