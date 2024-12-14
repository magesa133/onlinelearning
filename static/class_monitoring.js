// Class monitoring functionality for online sessions

window.onload = function () {
    // Utility to parse URL parameters
    function getUrlParams(url) {
        let urlStr = url.split('?')[1];
        const urlSearchParams = new URLSearchParams(urlStr);
        const result = Object.fromEntries(urlSearchParams.entries());
        return result;
    }

    // ZEGOCLOUD SDK Initialization
    const roomID = getUrlParams(window.location.href)['roomID'] || (Math.floor(Math.random() * 10000) + "");
    const userID = Math.floor(Math.random() * 10000) + "";
    const userName = "{{username}}"; // Replace with the actual username from the backend
    const appID = 1271126531; // Replace with your ZEGOCLOUD App ID
    const serverSecret = "5261b8e7778bf38bbe00c844ca26b988"; // Replace with your ZEGOCLOUD Server Secret
    const kitToken = ZegoUIKitPrebuilt.generateKitTokenForTest(appID, serverSecret, roomID, userID, userName);

    const zp = ZegoUIKitPrebuilt.create(kitToken);

    // Join Room Configuration
    zp.joinRoom({
        container: document.querySelector("#root"),
        sharedLinks: [{
            name: 'Personal link',
            url: window.location.protocol + '//' + window.location.host + window.location.pathname + '?roomID=' + roomID,
        }],
        scenario: {
            mode: ZegoUIKitPrebuilt.VideoConference,
        },
        turnOnMicrophoneWhenJoining: true,
        turnOnCameraWhenJoining: true,
        showMyCameraToggleButton: true,
        showMyMicrophoneToggleButton: true,
        showAudioVideoSettingsButton: true,
        showScreenSharingButton: true,
        showTextChat: true,
        showUserList: true,
        maxUsers: 50,
        layout: "Sidebar",
        showLayoutButton: true,
    });

    // Real-Time Monitoring Tools

    // Monitor user mic/camera statuses
    zp.on('onUserStateUpdate', (users) => {
        users.forEach(user => {
            console.log(`User ${user.userID} - Mic: ${user.micStatus}, Camera: ${user.cameraStatus}`);
        });
    });

    // Network quality monitoring
    zp.on('onNetworkQuality', (userID, quality) => {
        console.log(`User ${userID} has network quality: ${quality}`);
    });

    // Real-time attendance tracking
    zp.on('onUserJoin', (user) => {
        console.log(`User ${user.userID} joined.`);
        // Update attendance UI
    });
    
    zp.on('onUserLeave', (user) => {
        console.log(`User ${user.userID} left.`);
        // Update attendance UI
    });

    // Quiz Integration During Session
    const quizButton = document.getElementById("create-quiz");

    quizButton.addEventListener("click", () => {
        const quiz = {
            type: 'quiz',
            questions: [
                { id: 1, text: "What is 2+2?", options: ["3", "4", "5"], correct: 1 },
                { id: 2, text: "What is the capital of France?", options: ["Berlin", "Paris", "Rome"], correct: 1 }
            ]
        };
        zp.sendMessage({ text: JSON.stringify(quiz) });
        console.log("Quiz sent to participants.");
    });

    zp.on('onMessageReceived', (message) => {
        const quiz = JSON.parse(message.text);
        if (quiz.type === 'quiz') {
            displayQuiz(quiz.questions);
        }
    });

    function displayQuiz(questions) {
        console.log("Quiz Questions:", questions);
        // Add functionality to display quiz UI to users
    }

    // Fullscreen toggle logic
    const fullscreenButton = document.getElementById("fullscreen-toggle");
    const rootContainer = document.getElementById("root");

    fullscreenButton.addEventListener("click", () => {
        if (!document.fullscreenElement) {
            rootContainer.requestFullscreen()
                .then(() => {
                    rootContainer.classList.add("fullscreen");
                })
                .catch(err => {
                    console.error(`Error attempting to enable fullscreen mode: ${err.message}`);
                });
        } else {
            document.exitFullscreen()
                .then(() => {
                    rootContainer.classList.remove("fullscreen");
                })
                .catch(err => {
                    console.error(`Error attempting to exit fullscreen mode: ${err.message}`);
                });
        }
    });

    // Handle ESC key to exit fullscreen
    document.addEventListener("fullscreenchange", () => {
        if (!document.fullscreenElement) {
            rootContainer.classList.remove("fullscreen");
        }
    });
};
