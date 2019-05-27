$(function() {
    function CameraViewModel(parameters) {
        var self = this;
        self.settings = parameters[0];

        self.host = "http://127.0.0.1:8091/";
        self.urlGET  = self.host + "plugin/camera/keep_alive";
        self.urlPOST = self.host + "api/plugin/camera";
        self.xApiKey = "E4F3542466FB461BBC372DA9411184B9";

        self.intervals = {};
        self.settings = parameters[0];
        self.imageNameHook = ko.observable();
        self.cameraStatusHook = ko.observable();
        self.recordingStatusHook = ko.observable();
        self.errorMessageHook = ko.observable();
        self.maxTempHook = ko.observable();

        self.cameraStatus = false;
        self.recordingStatus = false;
        self.imageFPS = 9;


        self.sendHTTPRequest = function(message, method = "POST", callback = self.updateState, errorCallback = null) {
            let xhr = new XMLHttpRequest();
            if (callback != null) {
                xhr.onreadystatechange = () => {
                    if (xhr.readyState === XMLHttpRequest.DONE) {
                        callback(xhr);
                    }
                }
            }
            if (errorCallback !== null) {
                xhr.onerror = function() {
                    errorCallback()
                };
            }

            xhr.open(method, method === "POST" ? self.urlPOST : self.urlGET, true);
            xhr.setRequestHeader('Content-Type', 'application/json');
            xhr.setRequestHeader('x-api-key', self.xApiKey);
            xhr.send(message === "" ? null : JSON.stringify(message));
        };

        self.printTemp = (xhr) => {
            let response = JSON.parse(xhr.responseText);
            // console.log(response["maxtemp"])
            self.maxTempHook(response["maxtemp"]);
            // document.getElementById("maxtemp").value = response["maxtemp"]
        };

        self.keepAlive = function() {
            self.sendHTTPRequest("", "GET", self.printTemp, self.handleServerError)
        };

        self.handleServerError = function() {
            // console.log("Server error!");
            Object.keys(self.intervals).forEach(function(intervalName) {
                clearInterval(self.intervals[intervalName]);
            });
            self.cameraStatusHook("Camera: Server Error");
            self.recordingStatusHook("Recording: Server Error");

        };

        self.reportMessage = function(status, errorMessage) {
            self.errorMessageHook(errorMessage);
            if (status > 0) {
            }
            let color = status ? "#f44336" : "#3CBD0D";
            document.getElementById("alert").style.backgroundColor = color;
            document.getElementById("alert").style.display = "block";
        };

        self.refreshImage = function() {
            self.imageNameHook(self.host + "plugin/camera/static/images/video_feed?stamp=" + Date.now() + "&apikey=" + self.xApiKey);
        };

        self.updateRecTime = function() {
            let currentTime = new Date().getTime();
            let duration = currentTime - self.recordingStartTime;

            let recSeconds = Math.floor((duration / 1000) % 60);
            let recMinutes = Math.floor((duration / (1000 * 60)) % 60);
            let recHours = Math.floor((duration / (1000 * 60 * 60)) % 24);

            recSeconds = recSeconds > 9 ? recSeconds : "0" + recSeconds;
            recMinutes = recMinutes > 9 ? recMinutes : "0" + recMinutes;
            recHours = recHours > 9 ? recHours : "0" + recHours;

            self.recordingStatusHook("Recording for: " + recHours + ":" + recMinutes + ":" + recSeconds);
        };

        self.updateState = function(xhr) {
            let response = JSON.parse(xhr.responseText);
            self.recordingStartTime = Math.floor(response["recordingStartTime"]*1000);
            self.calibrationTime = response["calibrationTime"];

            if (response["message"] !== "") {
                self.reportMessage(response["status"], response["message"]);
            }

            if (response["cameraStatus"] && !self.cameraStatus) {
                self.intervals.keepAlive = setInterval(self.keepAlive, 1000);
                self.intervals.refreshImage = setInterval(self.refreshImage, 1000 / self.imageFPS);
            } else if (!response["cameraStatus"] && self.cameraStatus) {
                clearInterval(self.intervals.keepAlive);
                clearInterval(self.intervals.refreshImage);
            }

            if (response["recordingStatus"] && !self.recordingStatus) {
                self.updateRecTime();
                self.intervals.recTime = setInterval(self.updateRecTime, 1000);
            } else if (!response["recordingStatus"] && self.recordingStatus) {
                clearInterval(self.intervals.recTime);
            }

            document.getElementById("correctTempsCheckbox").checked = response["correctTemps"];
            document.getElementById("threshold").value = response["actionThreshold"];
            document.getElementById("commands").value = response["gcodes"];

            self.cameraStatus = response["cameraStatus"];
            self.recordingStatus = response["recordingStatus"];
            self.cameraStatusHook(self.cameraStatus ? "Camera: Active" : "Camera: Inactive");
            if (self.recordingStatus) {
                self.updateRecTime();
            } else {
                self.recordingStatusHook("Recording: Inactive");
            }
        };

        self.startCam = () => self.sendHTTPRequest({ command: "start_camera" }, "POST", self.updateState);
        self.stopCam  = () => self.sendHTTPRequest({ command: "stop_camera" });
        self.startRecording = () => self.sendHTTPRequest({ command: "start_recording" });
        self.stopRecording  = () => self.sendHTTPRequest({ command: "stop_recording" });

        self.updateTempWatch = () => {
            let temp = parseInt(document.getElementById("threshold").value);
            let gcodes = document.getElementById("commands").value;
            if (isNaN(temp)) {
                temp = 0;
            }
            self.sendHTTPRequest({ command: "update_temperature_watch", threshold: temp, gcodes: gcodes })
        };

        self.correctTemps = () => self.sendHTTPRequest({
            command: "high_temp_correction", correct: document.getElementById("correctTempsCheckbox").checked
        });

        // self.pauseRecording = function() {
        //     self.sendHTTPRequest({ command: "pause_recording" });
        // };

        self.calibrateCam = function() {
            self.sendHTTPRequest({ command: "calibrate_camera" });
        };

        self.onBeforeBinding = function() {
            // console.log(self.settings.settings.camera.message());
            self.cameraStatusHook("Camera:");
            self.recordingStatusHook("Recording:");
            self.sendHTTPRequest({ command: "get_state" });
            self.imageNameHook(self.host + "plugin/camera/static/images/video_feed?apikey=" + self.xApiKey);
        }
    }

    OCTOPRINT_VIEWMODELS.push({
        construct: CameraViewModel,
        dependencies: ["settingsViewModel"],
        elements: ["#tab_plugin_camera"]
    });
});
