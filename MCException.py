class MCError(Exception):
    pass


class MCSystemError(MCError):
    pass


class MCUserError(MCError):
    pass


class MCInternalError(MCSystemError):
    pass


class MCNotFoundError(MCSystemError):
    pass


class MCFetchError(MCSystemError):
    pass


class MCInvalidOperationError(MCUserError):
    pass
