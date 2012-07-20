from abc import ABCMeta, abstractmethod

class IExporter(object):
    __metaclass__ = ABCMeta

    @abstractmethod
    def getData(self, since=None, until=None):
        pass
