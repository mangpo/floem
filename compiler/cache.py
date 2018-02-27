from dsl import *
import common, graph_ir


def cache_default(name, key_type, val_type, hash_value=False, var_size=False, release_type=[], update_func='f',
                  write_policy=graph_ir.Cache.write_through, write_miss=graph_ir.Cache.no_write_alloc):
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

    if not var_size:
        key_params = [key_type]
        kv_params =  [key_type] + val_type
    else:
        key_params = [key_type, Int]
        kv_params = [key_type, Int, Int] + val_type

    # Key
    if common.is_pointer(key_type):
        key_arg = 'key'
        keylen_arg = 'keylen' if var_size else 'sizeof({0})'.format(key_type[0:-1])
    else:
        key_arg = '&key'
        keylen_arg = 'sizeof({0})'.format(key_type)

    # Value base type
    val_base_type = []
    for i in range(len(val_type)):
        if common.is_pointer(val_type[i]):
            val_base_type.append(val_type[i][:-1])
        else:
            val_base_type.append(val_type[i])

    # Value
    return_vals = []
    val_assign_src = r'''
    uint8_t* p;
    p = ((uint8_t*) it->content) + %s;
    ''' % keylen_arg

    for i in range(len(val_type)):
        if common.is_pointer(val_type[i]):
            val_assign_src += "val{1} = ({0}*) p;\n".format(val_base_type[i], i)
        else:
            val_assign_src += "val{1} = *(({0}*) p);\n".format(val_base_type[i], i)
            val_assign_src += "p += sizeof({0});\n".format(val_base_type[i])
        return_vals.append("val{0}".format(i))


    val_src = ""
    for i in range(len(val_type)):
        val_src += " {0} val{1} = 0;".format(val_type[i], i)
    val_src += r'''
    if(it != NULL) {
        %s
    }
                ''' % val_assign_src

    # Update
    pointer_vals = []
    update_vals = []
    update_src = "uint8_t* p;"
    update_after = ""
    for i in range(len(val_type)):
        update_src += " {0}* p{1} = 0;".format(val_base_type[i], i)
        update_src += " {0} update{1} = 0;".format(val_type[i], i)

    update_src += r'''
    if(it != NULL) {
        p = ((uint8_t*) it->content) + %s;
        ''' % keylen_arg

    for i in range(len(val_type)):
        update_src += "p{1} = ({0}*) p;\n".format(val_base_type[i], i)
        update_src += "p += sizeof({0});\n".format(val_base_type[i])
        pointer_vals.append("p{0}".format(i))

        if common.is_pointer(val_type[i]):
            update_after += "update{0} = p{0};\n".format(i)
        else:
            update_after += "update{0} = *p{0};\n".format(i)
        update_vals.append("update{0}".format(i))

    if not var_size:
        update_src += "%s(%s, %s);\n" % (update_func, ','.join(pointer_vals), ','.join(return_vals))
    else:
        update_src += "%s(last_vallen, %s, %s);\n" % (update_func, ','.join(pointer_vals), ','.join(return_vals))
    update_src += update_after
    update_src += "}\n"

    class CacheGet(Element):
        this = Persistent(hash_table)

        def configure(self):
            self.inp = Input(*key_params)
            self.hit = Output(*kv_params)
            self.miss = Output(*key_params)
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

    item_src2 = item_src
    replace = 'true' if write_miss==graph_ir.Cache.write_alloc else 'false'
    item_src += r'''
    it->evicted = 1; 
    citem *rit = cache_put(this->buckets, %d, it, %s);
    ''' % (n_buckets, replace)

    if write_policy == graph_ir.Cache.write_back and write_miss == graph_ir.Cache.no_write_alloc:
        item_src += r'''
        if(rit && rit->evicted == 3) state->cache_item = rit;  // to be evict, release, & free.
        else if(rit) cache_release(rit);
        '''
    else:
        item_src += r'''
        if(rit) cache_release(rit);
        '''

        if write_policy == graph_ir.Cache.write_back and write_miss == graph_ir.Cache.write_alloc:
            item_src += r'''
            if(rit && rit->evicted & 2) free(rit);
            '''

    cache_release = "state->cache_item = it;" if var_size else ''
    item_src2 += r'''
    it->evicted = 0; 
    citem* rit = cache_put_or_get(this->buckets, %d, it);
    if(rit) {
        free(it);
        it = rit;
        %s
        %s
    }
    ''' % (n_buckets, cache_release, val_assign_src)


    class CacheSet(Element):
        this = Persistent(hash_table)

        def configure(self):
            self.inp = Input(*kv_params)
            self.out = Output(*kv_params)
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

    class CacheSetGet(Element):
        this = Persistent(hash_table)

        def configure(self):
            self.inp = Input(*kv_params)
            self.out = Output(*kv_params)
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

            self.run_c(input_src + compute_hash + item_src2 + output_src)

    class CacheUpdate(Element):
        this = Persistent(hash_table)

        def configure(self):
            if not var_size:
                self.inp = Input(key_type, *val_type)
                self.hit = Output(key_type, *val_type)
                self.miss = Output(key_type, *val_type)
            else:
                self.inp = Input(key_type, Int, Int, *val_type)
                self.hit = Output(key_type, Int, Int, *val_type)
                self.miss = Output(key_type, Int, Int, *val_type)
            self.this = my_hash_table

        def impl(self):
            if hash_value:
                compute_hash = "uint32_t hv = state->%s;" % hash_value
            else:
                compute_hash = "uint32_t hv = jenkins_hash(%s, %s);" % (key_arg, keylen_arg)

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

            get_src = "citem *it = cache_get(this->buckets, %d, %s, %s, hv);\n" % (n_buckets, key_arg, keylen_arg)

            if not var_size:
                rel_src = "cache_release(it);\n"
            else:
                rel_src = "state->cache_item = it;\n"


            if not var_size:
                output_src = r'''
                output switch { 
                    case it: hit(key, %s); 
                    else: miss(key, %s); 
                }
                ''' % (','.join(update_vals), ','.join(return_vals))
            else:
                output_src = r'''
                output switch { 
                    case it: hit(key, keylen, last_vallen, %s); 
                    else: miss(key, keylen, last_vallen, %s); 
                }
                ''' % (','.join(update_vals), ','.join(return_vals))

            self.run_c(input_src + compute_hash + get_src + update_src + rel_src + output_src)

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
            state->cache_item = NULL;
            output { out(%s); }
            ''' % (','.join(release_args), ','.join(release_vals)))

    CacheGet.__name__ = prefix + CacheGet.__name__
    CacheSet.__name__ = prefix + CacheSet.__name__
    CacheUpdate.__name__ = prefix + CacheUpdate.__name__
    CacheRelease.__name__ = prefix + CacheRelease.__name__

    return CacheGet, CacheSet, CacheSetGet, CacheUpdate, CacheRelease if var_size else None
