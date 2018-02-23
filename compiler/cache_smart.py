from dsl import *
import graph_ir

def smart_cache(name, key_type, val_type):
    prefix = name + "_"
    cache = graph_ir.Cache(name, key_type, val_type)

    class CacheGetStart(Element):
        def configure(self):
            self.special = cache
            self.inp = Input(key_type)
            self.out = Output(key_type)

        def impl(self):
            self.run_c(r'''
            (%s x) = inp();
            output { out(x); }
            ''' % key_type)

        def __init__(self, name=None, create=True):
            Element.__init__(self, name=name, create=create)
            cache.get_start = self.instance

    args = ['{0} key'.format(key_type)]
    vals = ['key']

    for i in range(len(val_type)):
        args.append('{0} val{1}'.format(val_type[i], i))
        vals.append('val{0}'.format(i))


    class CacheGetEnd(Element):
        def configure(self):
            self.special = cache
            self.inp = Input(key_type, *val_type)
            self.out = Output(key_type, *val_type)

        def impl(self):
            self.run_c(r'''
            (%s) = inp();
            output { out(%s); }
            ''' % (','.join(args), ','.join(vals)))

        def __init__(self, name=None, create=True):
            Element.__init__(self, name=name, create=create)
            cache.get_start = self.instance


    CacheGetStart.__name__ = prefix + CacheGetStart.__name__
    CacheGetEnd.__name__ = prefix + CacheGetEnd.__name__

    return CacheGetStart, CacheGetEnd

