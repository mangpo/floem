from dsl import *
import common




def cache_default(name, key_type, val_type, hash_value, var_size=False):
    prefix = name + '_'

    n_buckets = 2**15
    class hash_table(State):
        buckets = Field(Array('hash_bucket', n_buckets))

        def init(self):
            self.buckets = lambda (x): 'hasht_init(%s, %d)' % (x, n_buckets)

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
if(p != NULL) {
    p = ((uint8_t*) it) + %s;
                ''' % keylen_arg

    val_base_type = []
    for i in range(len(val_type)):
        if common.is_pointer(val_type[i]):
            val_base_type.append(val_type[i][:-1])
        else:
            val_base_type.append(val_type)

    for i in range(len(val_type)):
        val_src += "val{1} = *({0}* p);\n".format(val_base_type[i], i)
        val_src += "p += sizeof({0});\n".format(val_base_type[i])
        return_vals.append("val{0}".format(i))

    val_src += "}\n"


    class CacheGet(Element):
        this = Persistent(hash_table)

        def configure(self):
            if not var_size:
                self.inp = Input(key_type)
                self.out = Output(key_type, *val_type)
            else:
                self.inp = Input(key_type, Int)
                self.out = Output(key_type, Int, Int, *val_type)
            self.this = my_hash_table

        def impl(self):
            if hash_value:
                compute_hash = "uint32_t hv = state.%s;" % hash_value
            else:
                compute_hash = "uint32_t hv = hash(%s, %s);" % (key_arg, keylen_arg)

            if not var_size:
                self.run_c(r'''
                (%s key) = inp();
                %s
                hitem* it = hasht_get(this->buckets, %s, %s, hv);
                %s
                
                output { out(%s); }
                ''' % (key_type, compute_hash, key_arg, keylen_arg, val_src, ','.join(return_vals)))
            else:
                self.run_c(r'''
                (%s key, int keylen) = inp();
                %s
                hitem* it = hasht_get(this->buckets, %s, %s, hv);
                %s
                
                output { out(key, keylen, it->last_vallen, %s); }
                ''' % (key_type, compute_hash, key_arg, keylen_arg, val_src, ','.join(return_vals)))

    # Item
    type_vals = []
    vals = []
    item_size = 'sizeof(hitem)'
    for i in range(len(val_type)):
        type_vals.append("{0} val{1}".format(val_type[i], i))
        vals.append("val{1}".format(i))

    for i in range(len(val_type-1)):
        item_size += ' + sizeof(%s)' % val_base_type[i]

    if not var_size:
        last_vallen_arg = ' + sizeof(%s)' % val_base_type[-1]
    else:
        last_vallen_arg = 'last_vallen'

    item_size += ' + %s + %s' % (last_vallen_arg, keylen_arg)

    item_src = r'''
    int item_size = %s;
    hitem* it = malloc(item_size);
    it->hv = hv;
    it->keylen = keylen;
    it->last_vallen = last_vallen;
    uint8_t* p = it->content;
    hasht_put(this->buckets, it);
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
                compute_hash = "uint32_t hv = state.%s;" % hash_value
            else:
                compute_hash = "uint32_t hv = hash(%s, %s);" % (key_arg, keylen_arg)

            extra_return = 'keylen, last_vallen,' if var_size else ''

            self.run_c(r'''
            (%s key, %s) = inp();
            int keylen = %s;
            int last_vallen = %s;
            %s
            %s
            
            output { out(key, %s %s); }
            ''' % (key_type, ','.join(type_vals),
                   keylen_arg, last_vallen_arg, compute_hash,
                   item_src, extra_return, return_vals))


    CacheGet.__name__ = prefix + CacheGet.__name__
    CacheSet.__name__ = prefix + CacheSet.__name__

    return CacheGet, CacheSet
