from dsl import *
import graph_ir

def smart_cache(name, key_type, val_type, var_size=False, hash_value=False, update_func='f'):
    prefix = name + "_"
    cache = graph_ir.Cache(name, key_type, val_type, var_size, hash_value, update_func)

    class CacheGetStart(Element):
        def configure(self):
            self.special = cache
            if not var_size:
                self.inp = Input(key_type)
                self.out = Output(key_type)
            else:
                self.inp = Input(key_type, Int)
                self.out = Output(key_type, Int)

        def impl(self):
            if not var_size:
                self.run_c(r'''
                (%s x) = inp();
                output { out(x); }
                ''' % key_type)
            else:
                self.run_c(r'''
                (%s x, int keylen) = inp();
                output { out(x, keylen); }
                ''' % key_type)

        def __init__(self, name=None, create=True):
            Element.__init__(self, name=name, create=create)
            cache.get_start = self.instance

    args = []
    vals = []

    for i in range(len(val_type)):
        args.append('{0} val{1}'.format(val_type[i], i))
        vals.append('val{0}'.format(i))


    class CacheGetEnd(Element):
        def configure(self):
            self.special = cache
            if not var_size:
                self.inp = Input(key_type, *val_type)
                self.out = Output(key_type, *val_type)
            else:
                self.inp = Input(key_type, Int, Int, *val_type)
                self.out = Output(key_type, Int, Int, *val_type)

        def impl(self):
            if not var_size:
                self.run_c(r'''
                (%s key, %s) = inp();
                output { out(key, %s); }
                ''' % (key_type, ','.join(args), ','.join(vals)))
            else:
                self.run_c(r'''
                (%s key, int keylen, int vallen, %s) = inp();
                output { out(key, keylen, vallen, %s); }
                ''' % (key_type, ','.join(args), ','.join(vals)))

        def __init__(self, name=None, create=True):
            Element.__init__(self, name=name, create=create)
            cache.get_end = self.instance


    CacheGetStart.__name__ = prefix + CacheGetStart.__name__
    CacheGetEnd.__name__ = prefix + CacheGetEnd.__name__

    return CacheGetStart, CacheGetEnd

