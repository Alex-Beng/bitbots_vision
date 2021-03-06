
import sys
from random import randint
from .horizon import HorizonDetector
from .candidate import Candidate
from .color import ColorDetector
import math
import numpy as np
import cv2


class LineDetector:
    def __init__(self, white_detector, field_color_detector, horizon_detector, config):
        # type: (np.matrix, list, ColorDetector, ColorDetector, HorizonDetector, dict) -> None
        self._image = None
        self._preprocessed_image = None
        self._linepoints = None
        self._linesegments = None
        self._white_detector = white_detector
        self._field_color_detector = field_color_detector
        self._horizon_detector = horizon_detector
        # init config
        self._horizon_offset = config['horizon_offset']
        self._linepoints_range = config['linepoints_range']
        self._blur_kernel_size = config['blur_kernel_size']

    def set_image(self, image):
        self._image = image
        self._preprocessed_image = None
        self._linepoints = None
        self._linesegments = None

    def set_candidates(self, candidates):
        # type: (list) -> None
        self._candidates = candidates

    def get_linepoints(self):
        if self._linepoints is None:
            self._linepoints = list()
            imgshape = self._get_preprocessed_image().shape
            white_masked_image = self._white_detector.mask_image(
                self._get_preprocessed_image())

            x_list = np.random.randint(0, imgshape[1],
                                       size=self._linepoints_range, dtype=int)
            y_list = np.random.randint(self._horizon_detector.get_upper_bound(self._horizon_offset), imgshape[0],
                                       size=self._linepoints_range, dtype=int)
            for p in zip(x_list, y_list):
                if white_masked_image[p[1]][p[0]]:
                    self._linepoints.append(p)
        return self._linepoints

    def get_linesegments(self):

        img = self._white_detector.mask_image(self._get_preprocessed_image())
        lines = cv2.HoughLinesP(img,
                                1,
                                math.pi / 180,
                                80,
                                30,
                                minLineLength=10)
        self._linesegments = []
        if lines is None:
            return self._linesegments
        for l in lines:
            for x1, y1, x2, y2 in l:
                # check if start or end is in any of the candidates
                in_candidate = False
                for candidate in self._candidates:
                    if candidate and (
                            candidate.point_in_candidate((x1, x2)) or
                            candidate.point_in_candidate((x2, y2))):
                        in_candidate = True
                        break

                # check if start and end is under horizon
                under_horizon = self._horizon_detector.point_under_horizon(
                    (x1, y1), self._horizon_offset) and \
                                self._horizon_detector.point_under_horizon(
                                    (x1, y1), self._horizon_offset)

                if not in_candidate and under_horizon:
                    self._linesegments.append((x1, y1, x2, y2))

        return self._linesegments

    def _get_preprocessed_image(self):
        if self._preprocessed_image is None:
            # bilateral filter for bluring areas while protecting edges (noise reduction)
            #self._preprocessed_image = cv2.bilateralFilter(self._image, 9, 75, 75)
            self._preprocessed_image = self._image.copy()
            # fill everything above horizon black
            hpoints = np.array([[(0, 0)] +
                                self._horizon_detector.get_horizon_points() +
                                [(self._preprocessed_image.shape[1] - 1, 0)]])
            cv2.fillPoly(self._preprocessed_image, hpoints, 000000)

            # get negated green mask
            green_mask = self._field_color_detector.mask_image(self._image)
            green_mask = cv2.morphologyEx(green_mask, cv2.MORPH_CLOSE, kernel=np.ones((3, 3)), iterations=1)

            green_mask = (np.ones_like(green_mask) - (green_mask/255))
            self._preprocessed_image = cv2.bitwise_and(self._preprocessed_image, self._preprocessed_image, mask=green_mask)

            # cv2.imshow('', self._preprocessed_image)
            # cv2.waitKey(1)
        return self._preprocessed_image

    @staticmethod
    def filter_points_with_candidates(linepoints, candidates):
        filtered_linepoints = linepoints
        for candidate in candidates:
            filtered_linepoints = [linepoint for linepoint in linepoints if not candidate.point_in_candidate(linepoint)]
        return filtered_linepoints
