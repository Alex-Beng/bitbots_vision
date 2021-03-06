#! /usr/bin/env python2


from bitbots_vision_common.vision_modules import lines, horizon, color, debug, live_classifier, classifier, ball, \
    lines2, fcnn_handler, live_fcnn_03, dummy_ballfinder, obstacle
from humanoid_league_msgs.msg import BallInImage, BallsInImage, LineInformationInImage, LineSegmentInImage, ObstaclesInImage, ObstacleInImage
from sensor_msgs.msg import Image
from cv_bridge import CvBridge
import rospy
import rospkg
import cv2
import os
from dynamic_reconfigure.server import Server
from bitbots_vision.cfg import VisionConfig


class Vision:

    def __init__(self):
        rospack = rospkg.RosPack()
        self.package_path = rospack.get_path('bitbots_vision')

        self.bridge = CvBridge()

        rospy.init_node('bitbots_vision')
        rospy.loginfo('Initializing vision...')

        self.config = {}
        self.debug_image_dings = debug.DebugImage()
        # register config callback and set config
        srv = Server(VisionConfig, self._dynamic_reconfigure_callback)

        rospy.spin()

    def _image_callback(self, img):
        self.handle_image(img)

    def handle_image(self, image_msg):
        # converting the ROS image message to CV2-image
        image = self.bridge.imgmsg_to_cv2(image_msg, 'bgr8')

        # setup detectors
        self.horizon_detector.set_image(image)
        self.obstacle_detector.set_image(image)
        self.line_detector.set_image(image)

        if (self.config['vision_ball_classifier'] == 'cascade'):
            self.ball_finder.set_image(image)
            self.ball_detector.set_image(image,
                                         self.horizon_detector.
                                         balls_under_horizon(
                                             self.ball_finder.get_ball_candidates(),
                                             self._ball_candidate_y_offset))

        elif (self.config['vision_ball_classifier'] == 'fcnn'):
            self.ball_detector.set_image(image)

        top_ball_candidate = self.ball_detector.get_top_candidate()

        # create ball msg
        if top_ball_candidate and top_ball_candidate.rating > self._ball_candidate_threshold:
            balls_msg = BallsInImage()
            balls_msg.header.frame_id = image_msg.header.frame_id
            balls_msg.header.stamp = image_msg.header.stamp

            ball_msg = BallInImage()
            ball_msg.center.x = top_ball_candidate.get_center_x()
            ball_msg.center.y = top_ball_candidate.get_center_y()
            ball_msg.diameter = top_ball_candidate.get_diameter()
            ball_msg.confidence = 1

            balls_msg.candidates.append(ball_msg)
            rospy.loginfo('found a ball! \o/')
            self.pub_balls.publish(balls_msg)

        # create obstacle msg
        obstacles_msg = ObstaclesInImage()
        obstacles_msg.header.frame_id = image_msg.header.frame_id
        obstacles_msg.header.stamp = image_msg.header.stamp
        for red_obs in self.obstacle_detector.get_red_obstacles():
            obstacle_msg = ObstacleInImage()
            obstacle_msg.color = ObstacleInImage.ROBOT_MAGENTA
            obstacle_msg.top_left.x = red_obs.get_upper_left_x()
            obstacle_msg.top_left.y = red_obs.get_upper_left_y()
            obstacle_msg.height = red_obs.get_height()
            obstacle_msg.width = red_obs.get_width()
            obstacle_msg.confidence = 1.0
            obstacle_msg.playerNumber = 42
            obstacles_msg.obstacles.append(obstacle_msg)
        for blue_obs in self.obstacle_detector.get_blue_obstacles():
            obstacle_msg = ObstacleInImage()
            obstacle_msg.color = ObstacleInImage.ROBOT_CYAN
            obstacle_msg.top_left.x = blue_obs.get_upper_left_x()
            obstacle_msg.top_left.y = blue_obs.get_upper_left_y()
            obstacle_msg.height = blue_obs.get_height()
            obstacle_msg.width = blue_obs.get_width()
            obstacle_msg.confidence = 1.0
            obstacle_msg.playerNumber = 42
            obstacles_msg.obstacles.append(obstacle_msg)
        for other_obs in self.obstacle_detector.get_other_obstacles():
            obstacle_msg = ObstacleInImage()
            obstacle_msg.color = ObstacleInImage.UNDEFINED
            obstacle_msg.top_left.x = other_obs.get_upper_left_x()
            obstacle_msg.top_left.y = other_obs.get_upper_left_y()
            obstacle_msg.height = other_obs.get_height()
            obstacle_msg.width = other_obs.get_width()
            obstacle_msg.confidence = 1.0
            obstacles_msg.obstacles.append(obstacle_msg)
        self.pub_obstacle.publish(obstacles_msg)

        # create line msg
        line_msg = LineInformationInImage()  # Todo: add lines
        line_msg.header.frame_id = image_msg.header.frame_id
        line_msg.header.stamp = image_msg.header.stamp
        for lp in self.line_detector.get_linepoints():
            ls = LineSegmentInImage()
            ls.start.x = lp[0]
            ls.start.y = lp[1]
            ls.end = ls.start
            line_msg.segments.append(ls)
        self.pub_lines.publish(line_msg)

        # do debug stuff
        if self.debug:
            self.debug_image_dings.set_image(image)
            self.debug_image_dings.draw_obstacle_candidates(
                self.obstacle_detector.get_candidates(),
                (0, 0, 0),
                thickness=3
            )
            self.debug_image_dings.draw_obstacle_candidates(
                self.obstacle_detector.get_red_obstacles(),
                (0, 0, 255),
                thickness=3
            )
            self.debug_image_dings.draw_obstacle_candidates(
                self.obstacle_detector.get_blue_obstacles(),
                (255, 0, 0),
                thickness=3
            )
            self.debug_image_dings.draw_obstacle_candidates(
                self.obstacle_detector.get_white_obstacles(),
                (255, 255, 255),
                thickness=3
            )
            self.debug_image_dings.draw_horizon(
                self.horizon_detector.get_horizon_points(),
                (0, 0, 255))
            self.debug_image_dings.draw_ball_candidates(
                self.ball_detector.get_candidates(),
                (0, 0, 255))
            self.debug_image_dings.draw_ball_candidates(
                self.horizon_detector.balls_under_horizon(
                    self.ball_detector.get_candidates(),
                    self._ball_candidate_y_offset),
                (0, 255, 255))
            # draw top candidate in
            self.debug_image_dings.draw_ball_candidates([top_ball_candidate],
                                                        (0, 255, 0))
            # draw linepoints in black
            self.debug_image_dings.draw_points(
                self.line_detector.get_linepoints(),
                (0, 0, 255))
            # debug_image_dings.draw_line_segments(line_detector.get_linesegments(), (180, 105, 255))
            if self.debug_image:
                self.debug_image_dings.imshow()
            if self.debug_image_msg:
                self.pub_debug_image.publish(self.bridge.cv2_to_imgmsg(self.debug_image_dings.get_image(), 'bgr8'))


    def _dynamic_reconfigure_callback(self, config, level):

        self._ball_candidate_threshold = config['vision_ball_candidate_rating_threshold']
        self._ball_candidate_y_offset = config['vision_ball_candidate_horizon_y_offset']

        self.debug_image = config['vision_debug_image']
        self.debug_image_msg = config['vision_debug_image_msg']
        self.debug = self.debug_image or self.debug_image_msg
        if self.debug:
            rospy.logwarn('Debug windows are enabled')
        else:
            rospy.loginfo('Debug windows are disabled')


        # set up ball config for cascade
        self.ball_config = {
            'classify_threshold': config['ball_finder_classify_threshold'],
            'scale_factor': config['ball_finder_scale_factor'],
            'min_neighbors': config['ball_finder_min_neighbors'],
            'min_size': config['ball_finder_min_size'],
        }

        # load cascade
        if (config['vision_ball_classifier'] == 'cascade'):
            self.cascade_path = self.package_path + config['cascade_classifier_path']
            if 'cascade_classifier_path' not in self.config or \
                    self.config['cascade_classifier_path'] != config['cascade_classifier_path'] or \
                    self.config['vision_ball_classifier'] != config['vision_ball_classifier']:
                if os.path.exists(self.cascade_path):
                    self.cascade = cv2.CascadeClassifier(self.cascade_path)
                else:
                    rospy.logerr(
                        'AAAAHHHH! The specified cascade config file doesn\'t exist!')
            if 'classifier_model_path' not in self.config or \
                    self.config['classifier_model_path'] != config['classifier_model_path'] or \
                    self.config['vision_ball_classifier'] != config['vision_ball_classifier']:
                self.ball_classifier = live_classifier.LiveClassifier(
                    self.package_path + config['classifier_model_path'])
                rospy.logwarn(config['vision_ball_classifier'] + " vision is running now")
            self.ball_detector = classifier.ClassifierHandler(self.ball_classifier)

            self.ball_finder = ball.BallFinder(self.cascade, self.ball_config)


        # set up ball config for fcnn
        self.ball_fcnn_config = {
            'debug': config['ball_fcnn_debug'] and self.debug_image,
            'threshold': config['ball_fcnn_threshold'],
            'expand_stepsize': config['ball_fcnn_expand_stepsize'],
            'pointcloud_stepsize': config['ball_fcnn_pointcloud_stepsize'],
            'shuffle_candidate_list': config['ball_fcnn_shuffle_candidate_list'],
            'min_candidate_diameter': config['ball_fcnn_min_ball_diameter'],
            'max_candidate_diameter': config['ball_fcnn_max_ball_diameter'],
            'candidate_refinement_iteration_count': config['ball_fcnn_candidate_refinement_iteration_count'],
        }


        # load fcnn
        if (config['vision_ball_classifier'] == 'fcnn'):
            if 'ball_fcnn_model_path' not in self.config or \
                    self.config['ball_fcnn_model_path'] != config['ball_fcnn_model_path'] or \
                    self.config['vision_ball_classifier'] != config['vision_ball_classifier']:
                ball_fcnn_path = self.package_path + config['ball_fcnn_model_path']
                if not os.path.exists(ball_fcnn_path):
                    rospy.logerr('AAAAHHHH! The specified fcnn model file doesn\'t exist!')
                self.ball_fcnn = live_fcnn_03.FCNN03(ball_fcnn_path)
                rospy.logwarn(config['vision_ball_classifier'] + " vision is running now")
            self.ball_detector = fcnn_handler.FcnnHandler(self.ball_fcnn,
                                                          self.ball_fcnn_config)


        if (config['vision_ball_classifier'] == 'dummy'):
            self.ball_detector = dummy_ballfinder.DummyClassifier(None, None)
        # color config
        self.white_color_detector = color.HsvSpaceColorDetector(
            [config['white_color_detector_lower_values_h'], config['white_color_detector_lower_values_s'],
             config['white_color_detector_lower_values_v']],
            [config['white_color_detector_upper_values_h'], config['white_color_detector_upper_values_s'],
             config['white_color_detector_upper_values_v']])

        self.red_color_detector = color.HsvSpaceColorDetector(
            [config['red_color_detector_lower_values_h'], config['red_color_detector_lower_values_s'],
             config['red_color_detector_lower_values_v']],
            [config['red_color_detector_upper_values_h'], config['red_color_detector_upper_values_s'],
             config['red_color_detector_upper_values_v']])

        self.blue_color_detector = color.HsvSpaceColorDetector(
            [config['blue_color_detector_lower_values_h'], config['blue_color_detector_lower_values_s'],
             config['blue_color_detector_lower_values_v']],
            [config['blue_color_detector_upper_values_h'], config['blue_color_detector_upper_values_s'],
             config['blue_color_detector_upper_values_v']])

        self.field_color_detector = color.PixelListColorDetector(
            self.package_path +
            config['field_color_detector_path'])

        # set up horizon config
        self.horizon_config = {
            'x_steps': config['horizon_finder_horizontal_steps'],
            'y_steps': config['horizon_finder_vertical_steps'],
            'precise_pixel': config['horizon_finder_precision_pix'],
            'min_precise_pixel': config['horizon_finder_min_precision_pix'],
        }
        self.horizon_detector = horizon.HorizonDetector(
            self.field_color_detector,
            self.horizon_config)

        # set up lines config
        self.lines_config = {
            'horizon_offset': config['line_detector_horizon_offset'],
            'linepoints_range': config['line_detector_linepoints_range'],
            'blur_kernel_size': config['line_detector_blur_kernel_size'],
            'line_detector2_line_len': config['line_detector2_line_len'],
            'line_detector2_red': config['line_detector2_red'],
            'line_detector2_green': config['line_detector2_green'],
            'line_detector2_blue': config['line_detector2_blue'],
            'line_detector2_subtract': config['line_detector2_subtract'],
            'line_detector2_magic_value': config['line_detector2_magic_value'],
            'line_detector2_horizon_offset': config['line_detector2_horizon_offset'],
        }

        self.line_detector = lines.LineDetector(self.white_color_detector,
                                                self.field_color_detector,
                                                self.horizon_detector,
                                                self.lines_config)

        self.obstacles_config = {
            'color_threshold': config['obstacle_color_threshold'],
            'white_threshold': config['obstacle_white_threshold'],
            'horizon_diff_threshold': config['obstacle_horizon_diff_threshold'],
            'candidate_horizon_offset': config['obstacle_candidate_horizon_offset'],
        }
        self.obstacle_detector = obstacle.ObstacleDetector(
            self.red_color_detector,
            self.blue_color_detector,
            self.white_color_detector,
            self.horizon_detector,
            self.obstacles_config
        )

        # subscribers
        if 'ROS_img_msg_topic' not in self.config or \
                self.config['ROS_img_msg_topic'] != config['ROS_img_msg_topic']:
            if hasattr(self, 'image_sub'):
                self.image_sub.unregister()
            self.image_sub = rospy.Subscriber(config['ROS_img_msg_topic'],
                                              Image,
                                              self._image_callback,
                                              queue_size=config['ROS_img_queue_size'],
                                              tcp_nodelay=True,
                                              buff_size=60000000)
            # https://github.com/ros/ros_comm/issues/536

        # publishers
        if 'ROS_ball_msg_topic' not in self.config or \
                self.config['ROS_ball_msg_topic'] != config['ROS_ball_msg_topic']:
            if hasattr(self, 'pub_balls'):
                self.pub_balls.unregister()
            self.pub_balls = rospy.Publisher(
                config['ROS_ball_msg_topic'],
                BallsInImage,
                queue_size=1)

        if 'ROS_line_msg_topic' not in self.config or \
                self.config['ROS_line_msg_topic'] != config['ROS_line_msg_topic']:
            if hasattr(self, 'pub_lines'):
                self.pub_lines.unregister()
            self.pub_lines = rospy.Publisher(
                config['ROS_line_msg_topic'],
                LineInformationInImage,
                queue_size=5)

        if 'ROS_obstacle_msg_topic' not in self.config or \
                self.config['ROS_obstacle_msg_topic'] != config['ROS_obstacle_msg_topic']:
            if hasattr(self, 'pub_obstacle'):
                self.pub_obstacle.unregister()
            self.pub_obstacle = rospy.Publisher(
                config['ROS_obstacle_msg_topic'],
                ObstaclesInImage,
                queue_size=3)

        self.pub_debug_image = rospy.Publisher(
            'debug_image',
            Image,
            queue_size=1,
        )
        self.config = config
        return config

if __name__ == '__main__':
    Vision()
