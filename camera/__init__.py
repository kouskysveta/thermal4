# coding=utf-8
from __future__ import absolute_import

import octoprint.plugin
import flask
import cv2
import io
import os
import time
import numpy
from usb import USBError
from threading import Event, Thread, RLock
from scipy.ndimage import median_filter

from camera.thermocam import thermocam_driver


class ThermoAnalyzer:
    def __init__(self, lock, frames):
        # I set logger variable before calling start_stream() to be able to use Octoprint log from this class.
        # Normally I would pass reference to _logger into constructor, but for some reason _logger is not available
        # during ThermoAnalyzer initialization. I set logger = None to PyCharm from reporting errors (undefined ref).
        self.logger = None
        self.lock = lock
        self.frames = frames
        # Synchronization primitives to start/stop camera and recording.
        # Event is just smarter (thread-safe bool) Initially false, .set() to set True, .clear() to set False
        self.camera_calibrated = Event()
        self.camera_calibrated.set()
        self.run_camera_flag = Event()
        self.record_stream_flag = Event()
        self.files_initialized_flag = Event()
        self.high_temp_correction_flag = Event()
        # I want to CameraDriver provide following interface: init_camera, release_camera and get_frame.
        # self.camera_driver = WebcamDriver()
        self.camera = thermocam_driver.CameraDriver()
        # Calling cv2.VideoWriter(..args) immediately creates video file. That's ugly.
        self.video_writer = None
        self.csv_file = None
        self.last_csv_write = 0
        self.gcodes_fired = False
        self.gcodes = []
        self._printer = None

        # TODO: Extract to yaml file
        self.temp_action_threshold = 250
        self.high_temp_correction_threshold = 40
        self.corr_param_a = 2
        self.corr_param_b = 1000
        self.fps = 9

    def __del__(self):
        self.run_camera_flag.clear()

    def run(self):
        imgw = 206
        imgh = 156

        while self.run_camera_flag.is_set():
            start_time = time.time()

            if not self.camera_calibrated.is_set():
                self.camera.calibrating = 1
                while not self.camera_calibrated.is_set() and self.camera.calibrating == 1:
                    self.camera.get_temp_matrix()
                self.camera.calibrating = 1
                self.camera_calibrated.set()
                self.camera.readpixelcal()
                self.camera.readrefframe()

            try:
                temp_matrix = self.camera.get_temp_matrix()
                # temp_matrix = numpy.full(shape=(156*206), fill_value=50, dtype=numpy.float32)
            except USBError as e:
                print(e)
                self.run_camera_flag.clear()
                self.record_stream_flag.clear()
                return

            # reshape array and apply median filter
            temp_matrix = numpy.reshape(temp_matrix[0:imgh*imgw], newshape=(imgh, imgw))
            temp_matrix = median_filter(temp_matrix, size=(3, 3))
            max_temp = max(temp_matrix.flat)

            # correct for high temperatures
            if self.high_temp_correction_flag.is_set() and max_temp > self.high_temp_correction_threshold:
                temp_matrix = self.corr_param_a * temp_matrix + self.corr_param_b
                max_temp = max(temp_matrix.flat)

            # check threshold for sending commands
            if max_temp > self.temp_action_threshold and not self.gcodes_fired and len(self.gcodes) > 0:
                print("temperature threshold %d exceeded (%d), sending gcodes: [%s]" % (self.temp_action_threshold, max_temp, ', '.join(self.gcodes)))
                self.gcodes_fired = True
                tags = {"source:api", "api:printer.command"}
                try:
                    self._printer.commands(self.gcodes, tags=tags)
                except Exception as e:
                    print(e)

            # create gray-scale image
            temp_matrix = temp_matrix[0:imgw*imgh]
            temp_matrix_img = temp_matrix / max_temp
            temp_matrix_img *= 255
            temp_matrix_img = abs(temp_matrix_img)

            temp_matrix_ints = temp_matrix_img.astype(numpy.uint8)
            temp_matrix_ints = numpy.reshape(temp_matrix_ints, newshape=(imgh, imgw))

            temp_matrix_png = numpy.empty((156, 206, 3))
            temp_matrix_png[:, :, 0] = temp_matrix_ints
            temp_matrix_png[:, :, 1] = temp_matrix_ints
            temp_matrix_png[:, :, 2] = temp_matrix_ints

            self.lock.acquire()
            self.frames['current'] = io.BytesIO(cv2.imencode('.png', temp_matrix_png)[1])
            self.frames['maxtemp'] = max_temp
            self.lock.release()


            if self.record_stream_flag.is_set():
                if not self.files_initialized_flag.is_set():
                    # Create octoprint-recordings dir in ~
                    rec_dir = os.path.expanduser('~/octoprint-recordings/')
                    print('dir: ' + rec_dir)
                    if not os.path.isdir(rec_dir):
                        os.mkdir(rec_dir)

                    # Open CSV file in append mode (pause compatibility)
                    timestamp = str(int(time.time()))
                    self.csv_file = open(rec_dir + timestamp + "_temp_rec.csv", "a")

                    # Open video file
                    self.video_writer = cv2.VideoWriter()
                    if not self.video_writer.open(filename=rec_dir + timestamp + "_temp_rec.avi",
                                                  fourcc=cv2.VideoWriter_fourcc(*'XVID'), fps=self.fps,
                                                  frameSize=(imgw, imgh), isColor=False):
                        self.record_stream_flag.clear()

                    self.files_initialized_flag.set()


                # Write to csv file
                if time.time() - self.last_csv_write > 1:
                    csv_time_start = time.time()

                    self.csv_file.write(str(int(time.time())) + ": ")
                    for temp in temp_matrix.flat[0:-1]:
                        self.csv_file.write(str(temp) + ",")
                    self.csv_file.write(str(temp_matrix.flat[-1]) + "\n")
                    self.last_csv_write = time.time()

                    # print("CSV write: " + str(time.time()-csv_time_start))

                # Write to video file
                video_time_start = time.time()
                self.video_writer.write(temp_matrix_ints)
                # print("VIDEO write: " + str(time.time() - video_time_start))

            # Sleep to maintain FPS
            exec_time = time.time()-start_time
            # print(exec_time)
            sleep_time = 0.0 if (1.0/self.fps)-exec_time < 0.0 else (1.0/self.fps)-exec_time
            time.sleep(sleep_time)

        if self.video_writer and self.video_writer.isOpened():
            self.video_writer.release()

        if self.csv_file and not self.csv_file.closed:
            self.csv_file.close()

        self.camera.release()


    def calibrate_camera(self):
        self.camera_calibrated.clear()
        success = self.camera_calibrated.wait(8.0)
        if not success:
            self.camera_calibrated.set()
            return 1
        else:
            return 0

    def start_stream(self, printer):
        self._printer = printer
        if not self.run_camera_flag.is_set():
            try:
                self.camera.init()
            except Exception as e:
                return 1, str(e)

            self.run_camera_flag.set()
            self.t = Thread(target=self.run)
            self.t.start()
        return 0, ""

    def stop_stream(self):
        if self.run_camera_flag.is_set():
            self.run_camera_flag.clear()
            self.record_stream_flag.clear()
            self.t.join()
            self.frames['current'] = self.frames['not_recording']

    def start_recording(self, printer):
        status, msg = self.start_stream(printer)
        if status > 0:
            return status, msg
        else:
            self.record_stream_flag.set()
            return 0, ""

    def stop_recording(self):
        self.record_stream_flag.clear()


# CameraPlugin inherits functions and variables from classes listed in parentheses
class CameraPlugin(octoprint.plugin.TemplatePlugin,
                   octoprint.plugin.SettingsPlugin,
                   octoprint.plugin.AssetPlugin,
                   octoprint.plugin.SimpleApiPlugin,
                   octoprint.plugin.BlueprintPlugin,
                   octoprint.plugin.ShutdownPlugin):

    def __init__(self):
        # Calls parent init_functions. (Basically all init_funcs of octoprint.plugin.TemplatePlugin, SettingsPlugin...)
        super(CameraPlugin, self).__init__()
        # Lock that will synchronize writing and reading from 'current_frame'
        self.lock = RLock()
        # Dictionary allows to modify (rewrite) 'current_frame' which is otherwise immutable
        self.frames = {}
        # Instance of ThermoAnalyzer class.
        self.thermo_analyzer = ThermoAnalyzer(self.lock, self.frames)
        # Default image. You'll need to change absolute path to some plugin_folder prefix + local dir.
        tmp_img = cv2.imread(os.path.dirname(os.path.realpath(__file__)) + '/static/images/not_recording.png')
        # io.BytesIO is a string wrapper with file interface. String loaded from memory defines content;
        # object itself can be used as regular file in any other function.
        # cv2.imencode encodes cv2 tmp_img image object (see cv::mat) into '.png' format;
        # first returned value is "success (conversion) status", second value contains data
        self.frames['not_recording'] = io.BytesIO(cv2.imencode('.png', tmp_img)[1])
        self.frames['current'] = io.BytesIO(cv2.imencode('.png', tmp_img)[1])
        self.frames['maxtemp'] = 0
        # self.cameraStatus = False
        # self.recordingStatus = False
        self.recordingStartTime = 0
        self.calibrationTime = 0
        self.correctForHighTemps = False

    # __del__ is destructor; https://en.wikipedia.org/wiki/Destructor_(computer_programming)
    # if OctoPrint crashes or is killed by SIGTERM (ctrl+c) it will call stop_stream() to release camera device
    def __del__(self):
         self.thermo_analyzer.stop_stream()

    def get_settings_defaults(self):
        return dict(message="Default message")

    def get_template_vars(self):
        return dict(message=self._settings.get(["message"]),
                    image=self._settings.get(["image"]))

    # Imports static files into plugin.
    # From docs: The assets will be made available by OctoPrint under the URL ``/plugin/<plugin identifier>/static/<path>``
    # js, css, less files are automatically imported into html page
    def get_assets(self):
        return dict(
            less=["less/camera.less"],
            js=["js/camera.js"],
            png=["images/not_recording.png"],
        )

    # This functions generates response (flask.Response()) for HTTP request.
    # Such request is generated - among others - by HTML TAG <img src="path">
    # Full path to access this resource is: <octoprint address+port>/plugin/<plugin identifier>/<route specified below>
    # e.g.: http://localhost:8091/plugin/camera/static/images/video_feed
    # Caller must also provide API key (well... in most cases). You can pass it in URL as:
    # e.g.: http://localhost:8091/plugin/camera/static/images/video_feed?apikey=E4F3542466FB461BBC372DA9411184B9s
    @octoprint.plugin.BlueprintPlugin.route("/static/images/video_feed", methods=["GET"])
    def video_feed(self):
        # Lock to prevent Analyzer thread overwrite image while function is reading it.
        self.lock.acquire()
        img = io.BytesIO(self.frames['current'].getvalue())
        # Normally you would send image saved on disk. io.BytesIO is just wrapper to mimic this behavior.
        # img = '/home/gnome/Devel/octoprint-project/camera/camera/static/images/img1.png'
        self.lock.release()
        return flask.send_file(filename_or_fp=img, mimetype='image/png')

    @octoprint.plugin.BlueprintPlugin.route("/keep_alive", methods=["GET"])
    def keep_alive(self):
        return flask.jsonify(maxtemp=self.frames['maxtemp'])

    # Defines a set of allowed commands for on_api_command.
    def get_api_commands(self):
        return dict(
            keep_alive=[],
            get_state=[],
            start_camera=[],
            stop_camera=[],
            start_recording=[],
            stop_recording=[],
            calibrate_camera=[],
            update_temperature_watch=["threshold", "gcodes"],
            high_temp_correction=["correct"]
        )

    def plugin_state(self, status, message):
        return flask.jsonify(status=status, message=message, correctTemps=self.thermo_analyzer.high_temp_correction_flag.is_set(),
                             actionThreshold=self.thermo_analyzer.temp_action_threshold, gcodes=self.thermo_analyzer.gcodes,
                             cameraStatus=self.thermo_analyzer.run_camera_flag.is_set(),
                             recordingStatus=self.thermo_analyzer.record_stream_flag.is_set(),
                             recordingStartTime=self.recordingStartTime, calibrationTime=self.calibrationTime)

    # POST HTTP requests are automatically parsed into 'data' dictionary.
    # Value with key 'command' is extracted and stored in command variable.
    def on_api_command(self, command, data):
        status = 0
        message = ""

        if command == "start_camera":
            self._logger.info("api command received: start camera")
            self.thermo_analyzer.logger = self._logger
            status, msg = self.thermo_analyzer.start_stream(self._printer)
            if status > 0:
                message = "Camera failed to start: " + msg

        elif command == "stop_camera":
            self._logger.info("api command received: stop camera")
            self.thermo_analyzer.stop_stream()

        elif command == "start_recording":
            self._logger.info("api command received: start recording")
            status, msg = self.thermo_analyzer.start_recording(self._printer)

            if status > 0:
                message = "Camera failed to start: " + msg
            else:
                self.recordingStartTime = time.time()

        elif command == "stop_recording":
            self._logger.info("api command received: stop recording")
            self.thermo_analyzer.stop_recording()

        elif command == "calibrate_camera":
            self._logger.info("api command received: calibrate camera")
            if not self.thermo_analyzer.run_camera_flag.is_set():
                status = 1
                message = "Camera not running!"
            else:
                status = self.thermo_analyzer.calibrate_camera()
                if status > 0:
                    message = "Calibration failed!"
                else:
                    message = "Calibrated!"

        elif command == "update_temperature_watch":
            self.thermo_analyzer.temp_action_threshold = int(data["threshold"])
            gcodes = data["gcodes"].encode("utf-8").split(",")
            gcodes = map(str.strip, gcodes)
            gcodes = filter(len, gcodes)
            self.thermo_analyzer.gcodes = gcodes
            self._logger.info(self.thermo_analyzer.gcodes)

        elif command == "high_temp_correction":
            if data["correct"]:
                self._logger.info("Temperature correction ON")
                self.thermo_analyzer.high_temp_correction_flag.set()
            else:
                self._logger.info("Temperature correction OFF")
                self.thermo_analyzer.high_temp_correction_flag.clear()

        return self.plugin_state(status, message)

        # elif command == "pause_recording":
        # 	self._logger.info("Pause record")
        # 	self.recordingStatus = 0
        # 	return self.plugin_state()


__plugin_name__ = "Thermo Analyzer"
__plugin_implementation__ = CameraPlugin()


if __name__ == "__main__":
    lock = RLock()
    frames = {}

    tmp_img = cv2.imread(os.path.dirname(os.path.realpath(__file__)) + '/static/images/not_recording.png')
    frames['not_recording'] = io.BytesIO(cv2.imencode('.png', tmp_img)[1])
    frames['current'] = io.BytesIO(cv2.imencode('.png', tmp_img)[1])

    thermo_analyzer = ThermoAnalyzer(lock=lock, frames=frames)
    thermo_analyzer.start_stream(self._printer)
    time.sleep(10)
    thermo_analyzer.stop_stream()
    time.sleep(1)
