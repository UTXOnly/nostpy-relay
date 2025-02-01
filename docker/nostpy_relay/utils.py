from collections import OrderedDict


class LimitedDict(OrderedDict):
    """
    A dictionary with a maximum size limit. When the maximum size is reached,
    the oldest item (in insertion order) is automatically removed to make room
    for new entries.

    This is used for tracking metrics where memory
    usage needs to be controlled, and only the most recent items are relevant.

    Attributes:
        max_size (int): The maximum number of items allowed in the dictionary.
    """

    def __init__(self, *args, max_size=1000, **kwargs):
        super().__init__(*args, **kwargs)
        self.max_size = max_size

    def __setitem__(self, key, value):
        if len(self) >= self.max_size:
            self.popitem(last=False)  # Remove the oldest item
        super().__setitem__(key, value)
