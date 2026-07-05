"""Vendored StepSimulation.srv — matches rosidl-generated interface."""


class _Result:
    RESULT_FEATURE_UNSUPPORTED = 0
    RESULT_OK = 1
    RESULT_NOT_FOUND = 2
    RESULT_INCORRECT_STATE = 3
    RESULT_OPERATION_FAILED = 4

    def __init__(self):
        self.result: int = 0
        self.error_message: str = ""


class StepSimulation:
    class Request:
        def __init__(self):
            self.steps: int = 1

    class Response:
        def __init__(self):
            self.result = _Result()
