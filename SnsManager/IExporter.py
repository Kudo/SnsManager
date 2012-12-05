from abc import ABCMeta, abstractmethod

class IExporter(object):
    __metaclass__ = ABCMeta

    @abstractmethod
    def getData(self, **kwargs):
        pass
