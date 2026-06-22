class AppException(Exception):
    def __init__(self, message: str, code: int = 400):
        self.message = message
        self.code = code


class NotFoundError(AppException):
    def __init__(self, message: str = "Resource not found"):
        super().__init__(message, code=404)


class ValidationError(AppException):
    def __init__(self, message: str = "Validation failed"):
        super().__init__(message, code=422)


class AgentError(AppException):
    def __init__(self, message: str = "Agent execution failed"):
        super().__init__(message, code=500)
