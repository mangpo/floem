from dsl import *
import graph_ir


def smart_cache(name, key_type, val_type,
                var_size=False, hash_value=False, update_func='f', set_return_value=False,
                write_policy=graph_ir.Cache.write_through, write_miss=graph_ir.Cache.no_write_alloc):
    prefix = name + "_"
    cache = graph_ir.Cache(name, key_type, val_type, var_size, hash_value, update_func, write_policy, write_miss)

    args = []
    vals = []

    for i in range(len(val_type)):
        args.append('{0} val{1}'.format(val_type[i], i))
        vals.append('val{0}'.format(i))

    if not var_size:
        key_src = r'''
                (%s x) = inp();
                output { out(x); }
                ''' % key_type
        kv_src = r'''
                (%s key, %s) = inp();
                output { out(key, %s); }
                ''' % (key_type, ','.join(args), ','.join(vals))
        key_params = [key_type]
        kv_params =  [key_type] + val_type
    else:
        key_src = r'''
                (%s x, int keylen) = inp();
                output { out(x, keylen); }
                ''' % key_type
        kv_src = r'''
                (%s key, int keylen, int vallen, %s) = inp();
                output { out(key, keylen, vallen, %s); }
                ''' % (key_type, ','.join(args), ','.join(vals))
        key_params = [key_type, Int]
        kv_params = [key_type, Int, Int] + val_type

    class CacheKey(Element):
        def configure(self):
            self.special = cache
            self.inp = Input(*key_params)
            self.out = Output(*key_params)

        def impl(self):
            self.run_c(key_src)

        def __init__(self, name=None, create=True):
            Element.__init__(self, name=name, create=create)

    class CacheKeyValue(Element):
        def configure(self):
            self.special = cache
            self.inp = Input(*kv_params)
            self.out = Output(*kv_params)

        def impl(self):
            self.run_c(kv_src)

        def __init__(self, name=None, create=True):
            Element.__init__(self, name=name, create=create)

    class CacheGetStart(CacheKey):
        def __init__(self, name=None, create=True):
            CacheKey.__init__(self, name=name, create=create)
            cache.get_start = self.instance

    class CacheGetEnd(CacheKeyValue):
        def __init__(self, name=None, create=True):
            CacheKeyValue.__init__(self, name=name, create=create)
            cache.get_end = self.instance

    class CacheSetStart(CacheKeyValue):
        def __init__(self, name=None, create=True):
            CacheKeyValue.__init__(self, name=name, create=create)
            cache.set_start = self.instance

    SetEndType = CacheKeyValue if set_return_value else CacheKey
    class CacheSetEnd(SetEndType):
        def __init__(self, name=None, create=True):
            SetEndType.__init__(self, name=name, create=create)
            cache.set_end = self.instance

    CacheGetStart.__name__ = prefix + CacheGetStart.__name__
    CacheGetEnd.__name__ = prefix + CacheGetEnd.__name__
    CacheSetStart.__name__ = prefix + CacheSetStart.__name__
    CacheSetEnd.__name__ = prefix + CacheSetEnd.__name__

    return CacheGetStart, CacheGetEnd, CacheSetStart, CacheSetEnd

