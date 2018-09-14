from dsl import *
import graph_ir


def smart_cache_with_state(name, key, vals,
                           var_size=False, hash_value=False, n_hashes=2**15,
                           write_policy=graph_ir.Cache.write_through, write_miss=graph_ir.Cache.no_write_alloc):
    if write_policy == graph_ir.Cache.write_back:
        assert write_miss == graph_ir.Cache.write_alloc, \
            "Cache: cannot use write-back policy with no write allocation on write misses."

    if not var_size:
        key_type, key_name = key
        keylen_name = None
    else:
        key_type, key_name, keylen_name = key

    val_type = [v[0] for v in vals]
    val_names = [v[1] for v in vals]

    if not var_size:
        vallen_name = None
    else:
        vallen_name = vals[-1][2]

    cache = graph_ir.Cache(name, key_type, val_type, var_size, hash_value,
                           state=True, n_hashes=n_hashes,
                           key_name=key_name, val_names=val_names, keylen_name=keylen_name, vallen_name=vallen_name,
                           write_policy=write_policy, write_miss=write_miss)

    class CacheBase(Element):
        def configure(self):
            self.special = cache
            self.inp = Input()
            self.out = Output()

        def __init__(self, name=None, create=True):
            Element.__init__(self, name=name, create=create)

    class CacheGetStart(CacheBase):
        def impl(self):
            self.run_c('output { out(); }')

        def __init__(self, name=None, create=True):
            CacheBase.__init__(self, name=name, create=create)
            cache.get_start = self.instance

    class CacheGetEnd(CacheBase):
        def impl(self):
            self.run_c('output { out(); }')

        def __init__(self, name=None, create=True):
            CacheBase.__init__(self, name=name, create=create)
            cache.get_end = self.instance

    class CacheSetStart(CacheBase):
        def impl(self):
            self.run_c('output { out(); }')

        def __init__(self, name=None, create=True):
            CacheBase.__init__(self, name=name, create=create)
            cache.set_start = self.instance

    class CacheSetEnd(CacheBase):
        def impl(self):
            self.run_c('output { out(); }')

        def __init__(self, name=None, create=True):
            CacheBase.__init__(self, name=name, create=create)
            cache.set_end = self.instance

    class CacheState(State):
        cache_item = Field('citem*')
        qid = Field(Uint(8))
        hash = Field(Uint(32))

    return CacheGetStart, CacheGetEnd, CacheSetStart, CacheSetEnd, CacheState


def smart_cache(name, key_type, val_type,
                var_size=False, hash_value=False, update_func='f',
                write_policy=graph_ir.Cache.write_through, write_miss=graph_ir.Cache.no_write_alloc):
    if write_policy == graph_ir.Cache.write_back:
        assert write_miss == graph_ir.Cache.write_alloc, \
            "Cache: cannot use write-back policy with no write allocation on write misses."

    cache = graph_ir.Cache(name, key_type, val_type, var_size, hash_value,
                           update_func=update_func,
                           write_policy=write_policy, write_miss=write_miss)

    args = []
    vals = []

    for i in range(len(val_type)):
        args.append('{0} val{1}'.format(val_type[i], i))
        vals.append('val{0}'.format(i))

    if not var_size:
        key_params = [key_type]
        kv_params =  [key_type] + val_type

        keys = ['key']
        kvs = ['key'] + vals

    else:
        key_params = [key_type, Int]
        kv_params = [key_type, Int, Int] + val_type

        keys = ['key', 'keylen']
        kvs = ['key', 'keylen', 'vallen'] + vals

    key_input = "(%s) = inp();\n" % ','.join(["{1} {0}".format(x, t) for x,t in zip(keys, key_params)])
    key_output = "output { out(%s); }\n" % ','.join(keys)
    key_src = key_input + key_output

    kv_input = "(%s) = inp();\n" % ','.join(["{1} {0}".format(x, t) for x, t in zip(kvs, kv_params)])
    kv_output = "output { out(%s); }\n" % ','.join(kvs)
    kv_src = kv_input + kv_output

    key2state = ' '.join(["state->{0} = {0};".format(x) for x in keys])
    kv2state = ' '.join(["state->{0} = {0};".format(x) for x in kvs])
    state2key = ' '.join(["{1} {0} = state->{0};".format(x, t) for x, t in zip(keys, key_params)])
    state2kv = ' '.join(["{1} {0} = state->{0};".format(x, t) for x, t in zip(kvs, kv_params)])

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

    class CacheSetEnd(CacheKeyValue):
        def __init__(self, name=None, create=True):
            CacheKeyValue.__init__(self, name=name, create=create)
            cache.set_end = self.instance

    class Key2State(Element):
        def configure(self):
            self.inp = Input(*key_params)
            self.out = Output()

        def impl(self):
            self.run_c(r'''
            %s
            %s
            output { out(); }
            ''' % (key_input, key2state))

    class KV2State(Element):
        def configure(self):
            self.inp = Input(*kv_params)
            self.out = Output()

        def impl(self):
            self.run_c(r'''
            %s
            %s
            output { out(); }
            ''' % (kv_input, kv2state))

    class State2Key(Element):
        def configure(self):
            self.inp = Input()
            self.out = Output(*key_params)

        def impl(self):
            self.run_c(r'''
            %s
            %s
            ''' % (state2key, key_output))

    class State2KV(Element):
        def configure(self):
            self.inp = Input()
            self.out = Output(*kv_params)

        def impl(self):
            self.run_c(r'''
            %s
            %s
            ''' % (state2kv, kv_output))

    sizes = []
    for type in val_type:
        if type[-1] == "*":
            non_pointer = type[:-1]
            sizes.append('sizeof(%s)' % non_pointer)
        else:
            sizes.append(None)

    if var_size:
        sizes[-1] = 'state->vallen'

    class CacheState(State):
        cache_item = Field('citem*')
        qid = Field(Uint(8))
        hash = Field(Uint(32))

        key = Field(key_type, size='state->keylen')
        if var_size:
            keylen = Field(Int)
            vallen = Field(Int)

        val0 = Field(val_type[0], size=sizes[0])
        if len(val_type) > 1:
            val1 = Field(val_type[1], size=sizes[1])
        if len(val_type) > 2:
            val2 = Field(val_type[2], size=sizes[2])
        if len(val_type) > 3:
            val3 = Field(val_type[3], size=sizes[3])

    assert len(val_type) <= 4

    return CacheGetStart, CacheGetEnd, CacheSetStart, CacheSetEnd, CacheState, Key2State, KV2State, State2Key, State2KV

