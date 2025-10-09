
class DatabaseError(AttributeError):
    pass

class PlatformError(ValueError):
    pass

class UnderDefinedError(AttributeError):
    pass


class OverwriteError(ValueError):
    pass


class NoExperimentFound(ValueError):
    pass


class InputNotValid(AttributeError):
    pass


class IncompleteAnalysis(AttributeError):
    pass