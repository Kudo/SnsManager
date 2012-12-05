from abc import ABCMeta, abstractmethod

class IExporter(object):
    __metaclass__ = ABCMeta

    EXPORT_DIRECTION_FORWARD = 'forward'            # From older to newer
    EXPORT_DIRECTION_BACKWARD = 'backword'          # From newer to older

    @abstractmethod
    def getData(self, **kwargs):
        pass
