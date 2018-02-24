from dsl import *
import common


def cache_default(name, key_type, val_type, hash_value=False, var_size=False, release_type=[]):
    prefix = name + '_'

    if not var_size:
        for v in val_type:
            assert not common.is_pointer(v), "Cache with non-variable-size must not return any pointer value."

    n_buckets = 2**15
    class hash_table(State):
        buckets = Field(Array('cache_bucket', n_buckets))

        def init(self):
            self.buckets = lambda (x): 'cache_init(%s, %d)' % (x, n_buckets)

    hash_table.__name__ = prefix + hash_table.__name__
    my_hash_table = hash_table()

    # Key
    if common.is_pointer(key_type):
        key_arg = 'key'
        keylen_arg = 'keylen' if var_size else 'sizeof({0})'.format(key_type[0:-1])
    else:
        key_arg = '&key'
        keylen_arg = 'sizeof({0})'.format(key_type)

    # Value
    return_vals = []
    val_src = "uint8_t* p;"
    for i in range(len(val_type)):
        val_src += " {0} val{1} = 0;".format(val_type[i], i)
    val_src += r'''
if(it != NULL) {
    p = ((uint8_t*) it->content) + %s;
                ''' % keylen_arg

    val_base_type = []
    for i in range(len(val_type)):
        if common.is_pointer(val_type[i]):
            val_base_type.append(val_type[i][:-1])
        else:
            val_base_type.append(val_type[i])

    for i in range(len(val_type)):
        if common.is_pointer(val_type[i]):
            val_src += "val{1} = ({0}*) p;\n".format(val_base_type[i], i)
        else:
            val_src += "val{1} = *(({0}*) p);\n".format(val_base_type[i], i)
        val_src += "p += sizeof({0});\n".format(val_base_type[i])
        return_vals.append("val{0}".format(i))

    val_src += "}\n"


    class CacheGet(Element):
        this = Persistent(hash_table)

        def configure(self):
            if not var_size:
                self.inp = Input(key_type)
                self.hit = Output(key_type, *val_type)
                self.miss = Output(key_type)
            else:
                self.inp = Input(key_type, Int)
                self.hit = Output(key_type, Int, Int, *val_type)
                self.miss = Output(key_type, Int)
            self.this = my_hash_table

        def impl(self):
            if hash_value:
                compute_hash = "uint32_t hv = state->%s;" % hash_value
            else:
                compute_hash = "uint32_t hv = jenkins_hash(%s, %s);" % (key_arg, keylen_arg)

            if not var_size:
                self.run_c(r'''
                (%s key) = inp();
                %s
                citem* it = cache_get(this->buckets, %d, %s, %s, hv);
                %s
                cache_release(it);
                
                output switch { case it: hit(key, %s); else: miss(key); }
                ''' % (key_type, compute_hash, n_buckets, key_arg, keylen_arg, val_src, ','.join(return_vals)))
            else:
                self.run_c(r'''
                (%s key, int keylen) = inp();
                %s
                citem* it = cache_get(this->buckets, %d, %s, %s, hv);
                %s
                state->cache_item = it;
                
                output switch { case it: hit(key, keylen, it->last_vallen, %s); else: miss(key, keylen); }
                ''' % (key_type, compute_hash, n_buckets, key_arg, keylen_arg, val_src, ','.join(return_vals)))

    # Item
    type_vals = []
    vals = []
    item_size = 'sizeof(citem)'
    for i in range(len(val_type)):
        type_vals.append("{0} val{1}".format(val_type[i], i))
        vals.append("val{0}".format(i))

    for i in range(len(val_type)-1):
        item_size += ' + sizeof(%s)' % val_base_type[i]

    if not var_size:
        last_vallen_arg = ' + sizeof(%s)' % val_base_type[-1]
    else:
        last_vallen_arg = 'last_vallen'

    item_size += ' + %s + %s' % (last_vallen_arg, keylen_arg)

    item_src = r'''
    int item_size = %s;
    citem* it = malloc(item_size);
    it->hv = hv;
    it->keylen = keylen;
    it->last_vallen = last_vallen;
    uint8_t* p = it->content;
    ''' % (item_size)

    if common.is_pointer(key_type):
        item_src += "memcpy(p, key, keylen);\n"
    else:
        item_src += "memcpy(p, &key, keylen);\n"
    item_src += "p += keylen;\n"

    for i in range(len(val_type) - 1):
        if common.is_pointer(val_type[i]):
            item_src += "memcpy(p, val{0}, sizeof({1}));\n".format(i, val_base_type[i])
        else:
            item_src += "memcpy(p, &val{0}, sizeof({1}));\n".format(i, val_base_type[i])
        item_src += "p += sizeof({0});\n".format(val_base_type[i])

    if common.is_pointer(val_type[-1]):
        item_src += "memcpy(p, val{0}, last_vallen);\n".format(len(val_type) - 1)
    else:
        item_src += "memcpy(p, &val{0}, last_vallen);\n".format(len(val_type) - 1)

    item_src += "cache_put(this->buckets, %d, it, NULL);\n" % n_buckets


    class CacheSet(Element):
        this = Persistent(hash_table)

        def configure(self):
            if not var_size:
                self.inp = Input(key_type, *val_type)
                self.out = Output(key_type, *val_type)
            else:
                self.inp = Input(key_type, Int, Int, *val_type)
                self.out = Output(key_type, Int, Int, *val_type)
            self.this = my_hash_table

        def impl(self):
            if hash_value:
                compute_hash = "uint32_t hv = state->%s;" % hash_value
            else:
                compute_hash = "uint32_t hv = jenkins_hash(%s, %s);" % (key_arg, keylen_arg)

            extra_return = 'keylen, last_vallen,' if var_size else ''

            if not var_size:
                input_src = r'''
                (%s key, %s) = inp();
                int keylen = %s;
                int last_vallen = %s;
                ''' % (key_type, ','.join(type_vals), keylen_arg, last_vallen_arg)
            else:
                input_src = r'''
                (%s key, int keylen, int last_vallen, %s) = inp();
                '''% (key_type, ','.join(type_vals))

            output_src = r'''
            output { out(key, %s %s); }
            ''' % (extra_return, ','.join(return_vals))

            self.run_c(input_src + compute_hash + item_src + output_src)

    # Release
    release_args = []
    release_vals = []
    for i in range(len(release_type)):
        release_args.append('{0} rel{1}'.format(release_type[i], i))
        release_vals.append('rel{0}'.format(i))

    class CacheRelease(Element):

        def configure(self):
            self.inp = Input(*release_type)
            self.out = Output(*release_type)

        def impl(self):
            self.run_c(r'''
            (%s) = inp();
            cache_release(state->cache_item);
            output { out(%s); }
            ''' % (','.join(release_args), ','.join(release_vals)))

    CacheGet.__name__ = prefix + CacheGet.__name__
    CacheSet.__name__ = prefix + CacheSet.__name__
    CacheRelease.__name__ = prefix + CacheRelease.__name__

    return CacheGet, CacheSet, CacheRelease if var_size else None
