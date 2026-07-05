"""Vendored SetSimulationState.srv — matches rosidl-generated interface."""


class _SimulationState:
    STATE_STOPPED = 0
    STATE_PLAYING = 1
    STATE_PAUSED = 2
    STATE_QUITTING = 3
    STATE_NO_WORLD = 4
    STATE_LOADING_WORLD = 5

    def __init__(self):
        self.state: int = 0


class _Result:
    RESULT_FEATURE_UNSUPPORTED = 0
    RESULT_OK = 1
    RESULT_NOT_FOUND = 2
    RESULT_INCORRECT_STATE = 3
    RESULT_OPERATION_FAILED = 4

    def __init__(self):
        self.result: int = 0
        self.error_message: str = ""


class SetSimulationState:
    ALREADY_IN_TARGET_STATE = 101
    STATE_TRANSITION_ERROR = 102
    INCORRECT_TRANSITION = 103

    class Request:
        def __init__(self):
            self.state = _SimulationState()

    class Response:
        def __init__(self):
            self.result = _Result()
