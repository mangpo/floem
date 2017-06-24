import copy


class InstancesCollection:
    def __init__(self):
        self.spec = set()
        self.impl = None

    def add(self, x):
        self.spec.add(x)
        if self.impl:
            self.impl.add(x)

    def union(self, other):
        self.spec = self.spec.union(other.spec)
        if self.impl and other.impl:
            self.impl = self.impl.union(other.impl)
        elif self.impl:
            self.impl = self.impl.union(other.spec)
        elif other.impl:
            self.impl = copy.copy(other.impl)


    def union_spec(self, other):
        self.spec = self.spec.union(other.spec)

    def union_impl(self, other):
        if self.impl:
            self.impl = self.impl.union(other.spec)
        else:
            self.impl = copy.copy(other.spec)

    def get_spec(self):
        return self.spec

    def get_impl(self):
        return self.impl